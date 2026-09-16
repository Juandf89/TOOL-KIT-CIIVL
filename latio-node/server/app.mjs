// app.mjs — punto de entrada Express. Cablea los módulos ya portados
// (reasoning, labeling, models, data, ratelimit) en las mismas rutas HTTP
// que src/api.py (Python, oracle de referencia — ver ese archivo para el
// contrato exacto de cada endpoint, incluidos los mensajes de error).
//
// Fidelidad deliberada con el original en dos puntos no obvios:
//
//   1. ORDEN DE MIDDLEWARE. src/api.py agrega el rate limiter ANTES que
//      CORS a propósito (Starlette ejecuta el último `add_middleware` como
//      el más EXTERNO, así que CORS envuelve al limitador y un 429/413
//      también lleva Access-Control-Allow-*). Express no tiene semántica de
//      "cebolla": cada middleware llamado con `app.use(...)` corre en el
//      orden de registro y escribe headers directo sobre `res`, que
//      persisten sin importar qué middleware posterior termine la
//      respuesta. Por eso acá alcanza con registrar CORS ANTES que el rate
//      limiter (orden de registro normal) para lograr el mismo resultado:
//      los headers CORS quedan puestos en `res` antes de que el limitador
//      decida cortar con 429/413.
//
//   2. NOMBRES DE CAMPO EN JSON. Los módulos internos (models.mjs,
//      labeling/rules.mjs) usan camelCase, por convención JS. La API
//      Python (Pydantic, sin alias_generator) serializa en snake_case, y
//      el explorador (toolkit-api/index.html) ya consume ese contrato. Acá
//      se convierte a snake_case en el borde HTTP (toSnakeCase), nunca
//      dentro de los módulos internos — así internamente todo sigue en
//      camelCase idiomático JS y el contrato de red queda idéntico al
//      original.

import express from "express";
import { RULEBASES } from "./reasoning/rulesets/index.mjs";
import { prove } from "./reasoning/engine.mjs";
import { Party, FactAction, FactEntry, FactBase } from "./reasoning/models.mjs";
import { proposeFromText } from "./labeling/rules.mjs";
import {
  initData,
  getCorpusEntries,
  requireKnownCorpus,
  loadArticles,
  getArticleByUid,
  corpusSummary,
  NotFoundError,
  ARTICLE_TEXT_PREVIEW_CHARS,
} from "./data.mjs";
import { createRateLimiter } from "./ratelimit.mjs";

// ---------------------------------------------------------------------------
// Utilidades de borde HTTP
// ---------------------------------------------------------------------------

// camelCase -> snake_case, recursivo, para objetos/arrays planos. Ningún
// campo del proyecto usa acrónimos ni dígitos pegados a letras que
// rompan esta conversión (verificado a mano contra src/models.py y
// src/labeling/schemas.py al portar — ver comentario de cabecera).
function toSnakeCase(value) {
  if (Array.isArray(value)) return value.map(toSnakeCase);
  if (value !== null && typeof value === "object") {
    const out = {};
    for (const [key, val] of Object.entries(value)) {
      const snake = key.replace(/([A-Z])/g, "_$1").toLowerCase();
      out[snake] = toSnakeCase(val);
    }
    return out;
  }
  return value;
}

class HttpError extends Error {
  constructor(status, detail) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

function sendDetail(res, status, detail) {
  res.status(status).json({ detail });
}

// Réplica mínima, a mano, de la parte de la validación automática de
// FastAPI/Pydantic que de verdad importa acá: tipo correcto, longitud
// mínima/máxima, pertenencia a un enum cerrado. No es un clon completo
// de Pydantic (no hace falta: los únicos consumidores son el explorador
// del propio proyecto y estos tests), pero cada regla de acá tiene un
// espejo exacto en un `Field(...)` o tipo `Literal[...]` de src/api.py.
function reqString(body, field, { minLength = 0, maxLength = Infinity, required = true } = {}) {
  const value = body?.[field];
  if (value === undefined || value === null) {
    if (required) throw new HttpError(422, `'${field}' es obligatorio.`);
    return undefined;
  }
  if (typeof value !== "string") throw new HttpError(422, `'${field}' debe ser un string.`);
  if (value.length < minLength) throw new HttpError(422, `'${field}' debe tener al menos ${minLength} caracteres.`);
  if (value.length > maxLength) throw new HttpError(422, `'${field}' debe tener a lo sumo ${maxLength} caracteres.`);
  return value;
}

function reqEnum(body, field, allowedSet, { required = true, fallback = undefined } = {}) {
  const value = body?.[field];
  if (value === undefined || value === null) {
    if (required) throw new HttpError(422, `'${field}' es obligatorio.`);
    return fallback;
  }
  if (!allowedSet.has(value)) {
    throw new HttpError(422, `'${field}' inválido: '${value}'. Valores permitidos: ${[...allowedSet].sort().join(", ")}.`);
  }
  return value;
}

// Envuelve un handler async para que cualquier rechazo caiga en el
// middleware de errores de Express en vez de colgar la request.
function asyncRoute(handler) {
  return (req, res, next) => {
    Promise.resolve(handler(req, res, next)).catch(next);
  };
}

// ---------------------------------------------------------------------------
// CORS — mismo default y misma variable de entorno que src/api.py.
// ---------------------------------------------------------------------------

const DEFAULT_ORIGINS = [
  "https://datalexlab.com",
  "https://www.datalexlab.com",
  "https://juandf89.github.io",
  "http://localhost:5500", "http://127.0.0.1:5500",
  "http://localhost:8080", "http://127.0.0.1:8080",
];

function resolveAllowedOrigins() {
  const raw = (process.env.LATIO_ALLOWED_ORIGINS ?? "").trim();
  if (!raw) return DEFAULT_ORIGINS;
  return raw.split(",").map((o) => o.trim()).filter(Boolean);
}

function buildCorsMiddleware(allowedOrigins) {
  const allowSet = new Set(allowedOrigins);
  return function corsMiddleware(req, res, next) {
    const origin = req.headers.origin;
    if (origin && allowSet.has(origin)) {
      res.set("Access-Control-Allow-Origin", origin);
      res.set("Access-Control-Allow-Credentials", "true");
      res.set("Vary", "Origin");
    }
    if (req.method === "OPTIONS") {
      res.set("Access-Control-Allow-Methods", "*");
      res.set(
        "Access-Control-Allow-Headers",
        req.headers["access-control-request-headers"] || "*"
      );
      res.status(204).end();
      return;
    }
    next();
  };
}

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

export async function createApp() {
  await initData();

  const app = express();
  app.disable("x-powered-by");

  // 1) CORS primero (ver nota de cabecera: así sus headers quedan puestos
  //    en `res` incluso si el rate limiter corta con 429/413 más abajo).
  app.use(buildCorsMiddleware(resolveAllowedOrigins()));

  // 2) Rate limiter — antes de express.json() para que el 413 por
  //    Content-Length se decida sin gastar el costo de parsear el body.
  app.use(createRateLimiter());

  // 3) Parseo de body. limit generoso pero acotado; el tope real de
  //    negocio ya lo aplicó el rate limiter arriba (LATIO_MAX_BODY_BYTES).
  app.use(express.json({ limit: "2mb" }));

  // -------------------------------------------------------------------
  // raíz / salud
  // -------------------------------------------------------------------
  app.get("/", (req, res) => {
    res.json({
      lab: "DataLex Lab",
      website: "https://www.datalexlab.com",
      project: "LATIO API",
      version: "1.0.0",
      docs: "/docs",
    });
  });

  // Exento de rate limit (ver ratelimit.mjs: EXEMPT_PATHS) — sin
  // dependencias externas que chequear (sin base de datos), solo confirma
  // que el proceso responde.
  app.get("/health", (req, res) => {
    res.json({ status: "ok" });
  });

  // -------------------------------------------------------------------
  // /v1/reasoning
  // -------------------------------------------------------------------

  const MAX_FACTS_PER_REQUEST = 2000;

  app.get("/v1/reasoning/rulebases", (req, res) => {
    const out = Object.entries(RULEBASES).map(([id, rulebase]) => ({
      id,
      description: rulebase.description ?? "",
    }));
    res.json(out);
  });

  app.post("/v1/reasoning/prove", (req, res) => {
    const body = req.body ?? {};

    const rulebaseId = reqString(body, "rulebase_id", { minLength: 1, maxLength: 200 });
    const goal = reqString(body, "goal", { minLength: 1, maxLength: 200 });
    const party = reqEnum(body, "party", new Set(Object.values(Party)));

    const rawFacts = body.facts;
    if (!Array.isArray(rawFacts)) throw new HttpError(422, "'facts' debe ser una lista.");
    if (rawFacts.length > MAX_FACTS_PER_REQUEST) {
      throw new HttpError(422, `'facts' admite a lo sumo ${MAX_FACTS_PER_REQUEST} entradas.`);
    }
    const facts = rawFacts.map((f) => {
      const action = reqEnum(f ?? {}, "action", new Set(Object.values(FactAction)));
      const fact = reqString(f ?? {}, "fact", { minLength: 1, maxLength: 4000 });
      const partyField = reqEnum(f ?? {}, "party", new Set(Object.values(Party)), {
        required: false,
        fallback: null,
      });
      return new FactEntry({ action, fact, party: partyField ?? null });
    });

    const rulebase = RULEBASES[rulebaseId];
    if (!rulebase) {
      throw new HttpError(404, `rulebase_id '${rulebaseId}' no encontrado`);
    }

    const factbase = new FactBase({ entries: facts });
    const result = prove(goal, party, rulebase, factbase);
    res.json(toSnakeCase(result));
  });

  // -------------------------------------------------------------------
  // /v1/corpora — navegación de los 8 corpus reales.
  // -------------------------------------------------------------------

  app.get("/v1/corpora", asyncRoute(async (req, res) => {
    const entries = getCorpusEntries();
    const out = [];
    for (const [corpusId, entry] of entries) {
      out.push(await corpusSummary(corpusId, entry));
    }
    res.json(out);
  }));

  app.get("/v1/corpora/:corpusId", asyncRoute(async (req, res) => {
    const entry = requireKnownCorpus(req.params.corpusId);
    const summary = await corpusSummary(req.params.corpusId, entry);
    res.json({ ...summary, gates: entry.gates ?? {} });
  }));

  app.get("/v1/corpora/:corpusId/articles", asyncRoute(async (req, res) => {
    const corpusId = req.params.corpusId;
    const limitRaw = req.query.limit !== undefined ? Number(req.query.limit) : 50;
    const offsetRaw = req.query.offset !== undefined ? Number(req.query.offset) : 0;
    if (!Number.isInteger(limitRaw) || limitRaw < 1 || limitRaw > 200) {
      throw new HttpError(422, "'limit' debe ser un entero entre 1 y 200.");
    }
    if (!Number.isInteger(offsetRaw) || offsetRaw < 0) {
      throw new HttpError(422, "'offset' debe ser un entero >= 0.");
    }

    const articles = await loadArticles(corpusId);
    const total = articles.length;
    const page = articles.slice(offsetRaw, offsetRaw + limitRaw);

    const out = page.map((a) => {
      const text = a.text_raw || "";
      const truncated = text.length > ARTICLE_TEXT_PREVIEW_CHARS;
      return {
        uid: a.uid,
        number: a.number ?? null,
        suffix: a.suffix ?? null,
        path: a.path ?? [],
        text_raw: text.slice(0, ARTICLE_TEXT_PREVIEW_CHARS),
        truncated,
      };
    });

    res.json({ corpus_id: corpusId, total, limit: limitRaw, offset: offsetRaw, articles: out });
  }));

  app.get("/v1/corpora/:corpusId/articles/:uid", asyncRoute(async (req, res) => {
    const { corpusId, uid } = req.params;
    await loadArticles(corpusId);
    const article = getArticleByUid(corpusId, uid);
    if (!article) {
      throw new HttpError(404, `uid '${uid}' no encontrado en corpus '${corpusId}'.`);
    }
    res.json({
      uid: article.uid,
      number: article.number ?? null,
      suffix: article.suffix ?? null,
      path: article.path ?? [],
      text_raw: article.text_raw ?? "",
      editorial_notes: article.editorial_notes ?? [],
      qa_flags: article.qa_flags ?? [],
      position_index: article.position_index ?? null,
    });
  }));

  // -------------------------------------------------------------------
  // /v1/statements/propose
  // -------------------------------------------------------------------

  app.post("/v1/statements/propose", (req, res) => {
    const body = req.body ?? {};
    const textSpan = reqString(body, "text_span", { minLength: 1, maxLength: 4000 });
    const proposal = proposeFromText(textSpan);
    res.json(toSnakeCase(proposal));
  });

  // -------------------------------------------------------------------
  // 404 para rutas no reconocidas + manejador de errores.
  // -------------------------------------------------------------------

  app.use((req, res) => {
    sendDetail(res, 404, "Not Found");
  });

  // eslint-disable-next-line no-unused-vars
  app.use((err, req, res, next) => {
    if (err instanceof HttpError) {
      sendDetail(res, err.status, err.detail);
      return;
    }
    if (err instanceof NotFoundError) {
      sendDetail(res, 404, err.message);
      return;
    }
    if (err.name === "CorruptDataError") {
      sendDetail(res, 500, err.message);
      return;
    }
    // express.json() reporta JSON malformado como SyntaxError con
    // err.status === 400 — lo tratamos como 422 (cuerpo de request
    // inválido), coherente con el resto de los errores de forma acá.
    if (err.type === "entity.parse.failed" || err instanceof SyntaxError) {
      sendDetail(res, 422, "Cuerpo de la petición no es JSON válido.");
      return;
    }
    // No exponer detalles internos no anticipados — mismo criterio que un
    // 500 genérico de FastAPI para excepciones no manejadas.
    // eslint-disable-next-line no-console
    console.error("[latio] error no manejado:", err);
    sendDetail(res, 500, "Error interno.");
  });

  return app;
}

// ---------------------------------------------------------------------------
// Arranque del proceso. Hostinger conecta el Node.js Web App vía socket
// Unix (process.env.LSNODE_SOCKET, módulo lsnode de LiteSpeed — ver
// ratelimit.mjs y server/app.mjs del proyecto hermano datalex-lab, mismo
// patrón exacto en producción). En desarrollo local, PORT (o 3000 por
// defecto) sobre TCP normal.
// ---------------------------------------------------------------------------

// IMPORTANTE: el arranque NO puede ir detrás de un guard tipo
// `import.meta.url === file://${process.argv[1]}` (el equivalente ESM de
// `require.main === module`). El módulo lsnode de LiteSpeed carga este archivo
// sin ejecutarlo como entry point, así que ese guard evalúa a falso, listen()
// nunca se llama y Hostinger responde 503 con el error de runtime
// "App did not call listen() within 3 seconds". Verificado en producción el
// 2026-09-15. El proyecto hermano (datalex-lab/server/app.mjs) llama a listen()
// de forma incondicional por esta misma razón.
//
// La única condición admisible es excluir el runner de tests: node --test
// define NODE_TEST_CONTEXT en el proceso hijo, y los tests levantan su propio
// servidor efímero con app.listen(0). Esa variable no existe en producción.
if (!process.env.NODE_TEST_CONTEXT) {
  const app = await createApp();
  const listenTarget = process.env.LSNODE_SOCKET || process.env.PORT || 3000;
  app.listen(listenTarget, () => {
    // eslint-disable-next-line no-console
    console.log(`[latio] escuchando en ${listenTarget}`);
  });
}
