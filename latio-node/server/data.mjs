// data.mjs — carga de manifest.json / corpus_registry.json / artículos por
// corpus. Port de la sección "/v1/corpora" de src/api.py.
//
// Diferencia deliberada con el original Python: config/corpus_registry.yaml
// se convirtió UNA VEZ a config/corpus_registry.json (ver
// scripts/convertir_corpus_registry.md si se necesita repetirlo) para no
// agregar una dependencia de parseo YAML a producción — en shared hosting,
// cada dependencia npm extra es un punto más de falla en el install. El
// contenido es idéntico, solo el formato de archivo cambia.

import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");
const DATA_PROCESSED = path.join(ROOT, "data", "processed");
const REPORTS_DIR = path.join(ROOT, "reports");
const CONFIG_DIR = path.join(ROOT, "config");

export const ARTICLE_TEXT_PREVIEW_CHARS = 300;

let manifestPromise = null;
let corpusRegistryPromise = null;
let corpusEntries = null; // Map<corpus_id, manifest entry>

async function loadManifest() {
  if (!manifestPromise) {
    manifestPromise = readFile(path.join(REPORTS_DIR, "manifest.json"), "utf-8").then(JSON.parse);
  }
  return manifestPromise;
}

async function loadCorpusRegistry() {
  if (!corpusRegistryPromise) {
    corpusRegistryPromise = readFile(path.join(CONFIG_DIR, "corpus_registry.json"), "utf-8").then(JSON.parse);
  }
  return corpusRegistryPromise;
}

// Leídos una sola vez al arrancar el proceso — igual criterio que el
// original Python: metadata pequeña y estable, releerla por request sería
// I/O innecesario en un endpoint que se puede llamar seguido.
export async function initData() {
  const [manifest] = await Promise.all([loadManifest(), loadCorpusRegistry()]);
  corpusEntries = new Map((manifest.corpora ?? []).map((entry) => [entry.corpus_id, entry]));
  return { manifest, corpusEntries };
}

export function getCorpusEntries() {
  if (corpusEntries === null) {
    throw new Error("data.mjs: initData() no se llamó antes de usar getCorpusEntries().");
  }
  return corpusEntries;
}

// Los artículos completos (miles por corpus, hasta ~4.4MB por archivo) se
// cargan perezosamente la primera vez que se piden y quedan cacheados en
// memoria para el resto de la vida del proceso — mismo criterio que
// _ARTICLES_CACHE en el Python original.
const articlesCache = new Map(); // corpus_id -> array de artículos
const articlesByUidCache = new Map(); // corpus_id -> Map(uid -> artículo)

export class NotFoundError extends Error {
  constructor(message) {
    super(message);
    this.name = "NotFoundError";
  }
}

export function requireKnownCorpus(corpusId) {
  const entries = getCorpusEntries();
  const entry = entries.get(corpusId);
  if (!entry) {
    throw new NotFoundError(
      `corpus_id '${corpusId}' no encontrado. Corpus disponibles: ` +
      JSON.stringify([...entries.keys()].sort())
    );
  }
  return entry;
}

export async function loadArticles(corpusId) {
  requireKnownCorpus(corpusId);
  if (articlesCache.has(corpusId)) return articlesCache.get(corpusId);

  const filePath = path.join(DATA_PROCESSED, `${corpusId}_articles.json`);
  let raw;
  try {
    raw = await readFile(filePath, "utf-8");
  } catch (err) {
    if (err.code === "ENOENT") {
      throw new NotFoundError(
        `No se encontró el archivo de artículos de '${corpusId}' (${path.basename(filePath)}).`
      );
    }
    throw err;
  }

  let articles;
  try {
    articles = JSON.parse(raw);
  } catch (err) {
    const httpError = new Error(
      `El archivo de artículos de '${corpusId}' está corrupto o mal formado: ${err.message}`
    );
    httpError.name = "CorruptDataError";
    throw httpError;
  }

  articlesCache.set(corpusId, articles);
  articlesByUidCache.set(corpusId, new Map(articles.map((a) => [a.uid, a])));
  return articles;
}

export function getArticleByUid(corpusId, uid) {
  return articlesByUidCache.get(corpusId)?.get(uid) ?? null;
}

export async function corpusSummary(corpusId, entry) {
  const registry = await loadCorpusRegistry();
  const reg = registry[corpusId] ?? {};
  return {
    corpus_id: corpusId,
    display_name: reg.display_name ?? corpusId,
    jurisdiction: reg.jurisdiction ?? "?",
    articles_parsed: entry.articles_parsed,
    expected_article_count: entry.expected_article_count,
    recall: entry.recall,
  };
}
