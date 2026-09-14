// tests/api.test.mjs — smoke test HTTP de todas las rutas, incluidos los
// contratos de error (404/422/413/429) y CORS. Espejo liviano de
// tests/test_api_corpora.py y tests/test_api_statements_validate.py del
// repo Python — no reimplementa cada caso de esos archivos (ver
// cross_validate.mjs para la comparación exhaustiva contra el oráculo).

import test from "node:test";
import assert from "node:assert/strict";
import { createApp } from "../server/app.mjs";

process.env.LATIO_RATE_LIMIT_ENABLED = "0"; // se prueba el rate limiter aparte, con su propia instancia

let base;
let server;

test.before(async () => {
  const app = await createApp();
  server = app.listen(0);
  const port = server.address().port;
  base = `http://127.0.0.1:${port}`;
});

test.after(async () => {
  await new Promise((resolve) => server.close(resolve));
});

test("GET / responde metadata del proyecto", async () => {
  const res = await fetch(`${base}/`);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.project, "LATIO API");
});

test("GET /health responde ok", async () => {
  const res = await fetch(`${base}/health`);
  assert.equal(res.status, 200);
  assert.deepEqual(await res.json(), { status: "ok" });
});

test("GET /v1/reasoning/rulebases lista los 2 rulebases", async () => {
  const res = await fetch(`${base}/v1/reasoning/rulebases`);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.length, 2);
  assert.ok(body.every((r) => typeof r.id === "string" && typeof r.description === "string"));
});

test("POST /v1/reasoning/prove con rulebase_id inexistente -> 404", async () => {
  const res = await fetch(`${base}/v1/reasoning/prove`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rulebase_id: "no-existe", goal: "x", party: "plaintiff", facts: [] }),
  });
  assert.equal(res.status, 404);
});

test("POST /v1/reasoning/prove sin goal -> 422", async () => {
  const res = await fetch(`${base}/v1/reasoning/prove`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rulebase_id: "jp-civil-612-sublease-demo", party: "plaintiff", facts: [] }),
  });
  assert.equal(res.status, 422);
});

test("POST /v1/reasoning/prove con facts por encima del tope -> 422", async () => {
  const facts = Array.from({ length: 2001 }, () => ({ action: "admission", fact: "x", party: "plaintiff" }));
  const res = await fetch(`${base}/v1/reasoning/prove`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rulebase_id: "jp-civil-612-sublease-demo", goal: "x", party: "plaintiff", facts }),
  });
  assert.equal(res.status, 422);
});

test("GET /v1/corpora lista los 8 corpus del manifest", async () => {
  const res = await fetch(`${base}/v1/corpora`);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.length, 8);
});

test("GET /v1/corpora/:id inexistente -> 404 con lista de disponibles", async () => {
  const res = await fetch(`${base}/v1/corpora/ZZ-NOPE`);
  assert.equal(res.status, 404);
  const body = await res.json();
  assert.match(body.detail, /Corpus disponibles/);
});

test("GET /v1/corpora/CO-CC/articles pagina correctamente", async () => {
  const res = await fetch(`${base}/v1/corpora/CO-CC/articles?limit=5&offset=0`);
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.articles.length, 5);
  assert.equal(body.limit, 5);
  assert.ok(body.total > 5);
  assert.ok(body.articles.every((a) => a.text_raw.length <= 300));
});

test("GET /v1/corpora/CO-CC/articles?limit=0 -> 422 (fuera de rango)", async () => {
  const res = await fetch(`${base}/v1/corpora/CO-CC/articles?limit=0`);
  assert.equal(res.status, 422);
});

test("GET /v1/corpora/CO-CC/articles/:uid inexistente -> 404", async () => {
  const res = await fetch(`${base}/v1/corpora/CO-CC/articles/uid-que-no-existe`);
  assert.equal(res.status, 404);
});

test("POST /v1/statements/validate: caso valido -> valid true con computed", async () => {
  const res = await fetch(`${base}/v1/statements/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text_span: "El comprador deberá pagar el precio dentro de los treinta días.",
      statement_type: "regla",
      structure: "supuesto_consecuencia",
      deontic_modality: "obligacion",
      addressee: "partes",
      antecedent_operator: "ninguno_explicito",
      generality_n_conditions: 1,
    }),
  });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.valid, true);
  assert.equal(body.computed.generality_level, "intermedia");
});

test("POST /v1/statements/validate: combinacion ilegal -> valid false con error, HTTP 200", async () => {
  const res = await fetch(`${base}/v1/statements/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text_span: "x",
      statement_type: "definicion",
      structure: "supuesto_consecuencia",
      deontic_modality: "ninguno",
      addressee: "partes",
      antecedent_operator: "ninguno_explicito",
      generality_n_conditions: 0,
    }),
  });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.valid, false);
  assert.match(body.error, /combinación ilegal/);
});

test("POST /v1/statements/validate: statement_type invalido -> 422 (forma de request)", async () => {
  const res = await fetch(`${base}/v1/statements/validate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      text_span: "x",
      statement_type: "no-es-un-tipo-valido",
      structure: "supuesto_consecuencia",
      deontic_modality: "ninguno",
      addressee: "partes",
      antecedent_operator: "ninguno_explicito",
      generality_n_conditions: 0,
    }),
  });
  assert.equal(res.status, 422);
});

test("POST /v1/statements/propose devuelve una propuesta parcial", async () => {
  const res = await fetch(`${base}/v1/statements/propose`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text_span: "Se presume la buena fe del poseedor." }),
  });
  assert.equal(res.status, 200);
  const body = await res.json();
  assert.equal(body.statement_type, "presuncion");
  assert.equal(body.presumption_rebuttable, true);
});

test("cuerpo JSON malformado -> 422", async () => {
  const res = await fetch(`${base}/v1/statements/propose`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: "{ esto no es json",
  });
  assert.equal(res.status, 422);
});

test("ruta desconocida -> 404", async () => {
  const res = await fetch(`${base}/no/existe`);
  assert.equal(res.status, 404);
});

test("CORS: origen permitido recibe Access-Control-Allow-Origin", async () => {
  const res = await fetch(`${base}/health`, { headers: { Origin: "https://datalexlab.com" } });
  assert.equal(res.headers.get("access-control-allow-origin"), "https://datalexlab.com");
  assert.equal(res.headers.get("access-control-allow-credentials"), "true");
});

test("CORS: origen no permitido no recibe el header", async () => {
  const res = await fetch(`${base}/health`, { headers: { Origin: "https://evil.example" } });
  assert.equal(res.headers.get("access-control-allow-origin"), null);
});

// ---------------------------------------------------------------------
// Rate limiter — instancia propia de la app con límites bajos, aislada
// del resto de los tests (que corren con LATIO_RATE_LIMIT_ENABLED=0).
// ---------------------------------------------------------------------

test("rate limiter: 413 por Content-Length, 429 tras exceder el limite, /health exento", async () => {
  process.env.LATIO_RATE_LIMIT_ENABLED = "1";
  process.env.LATIO_RATE_LIMIT_DEFAULT = "2";
  process.env.LATIO_RATE_LIMIT_WINDOW = "60";
  process.env.LATIO_MAX_BODY_BYTES = "50";
  try {
    const app = await createApp();
    const s = app.listen(0);
    const b = `http://127.0.0.1:${s.address().port}`;
    try {
      const big = await fetch(`${b}/v1/statements/propose`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text_span: "x".repeat(200) }),
      });
      assert.equal(big.status, 413);

      let sawLimited = false;
      for (let i = 0; i < 5; i++) {
        const r = await fetch(`${b}/v1/reasoning/rulebases`);
        if (r.status === 429) {
          sawLimited = true;
          assert.ok(r.headers.get("retry-after"));
          break;
        }
      }
      assert.ok(sawLimited, "se esperaba al menos un 429 tras exceder el límite");

      const health = await fetch(`${b}/health`);
      assert.equal(health.status, 200);

      const otherIp = await fetch(`${b}/v1/reasoning/rulebases`, {
        headers: { "X-Forwarded-For": "203.0.113.9" },
      });
      assert.equal(otherIp.status, 200);
    } finally {
      await new Promise((resolve) => s.close(resolve));
    }
  } finally {
    delete process.env.LATIO_RATE_LIMIT_DEFAULT;
    delete process.env.LATIO_RATE_LIMIT_WINDOW;
    delete process.env.LATIO_MAX_BODY_BYTES;
    process.env.LATIO_RATE_LIMIT_ENABLED = "0";
  }
});
