import json
import os
from pathlib import Path

import yaml
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ValidationError
from typing import List, Literal, Optional, Dict, Any

from src.reasoning.models import Party, FactEntry, FactBase, ProofResult
from src.reasoning.engine import prove
from src.reasoning.rulesets import RULEBASES
from src.models import (
    AntecedentOperator,
    Addressee,
    DeonticModality,
    ExceptionInfo,
    GeneralityProxies,
    NormativeStatement,
    StatementType,
    Structure,
)
from src.labeling.rules import propose_from_text
from src.labeling.schemas import LabelProposal

app = FastAPI(title='DataLex Lab · LATIO API', version='1.0.0', docs_url='/docs')

# Orígenes permitidos. `allow_origins=['*']` junto con `allow_credentials=True`
# es una combinación inválida/insegura según la especificación CORS (ver A-2,
# reports/debate_revision_2026-09-10.md).
#
# Configurable vía la variable de entorno LATIO_ALLOWED_ORIGINS (lista
# separada por comas) para no hardcodear el dominio de producción en el
# código — ver DEPLOYMENT.md. Si no está seteada, usa un default seguro para
# desarrollo local: el dominio conocido del proyecto (datalexlab.com) más los
# puertos usados para servir toolkit-api/index.html localmente (sección
# "Motor de Razonamiento (real)" de la consola — `python -m http.server 5500`
# o el puerto que uses, agregalo acá si no es 5500/8080).
_DEFAULT_ORIGINS = [
    'https://datalexlab.com',
    'http://localhost:5500', 'http://127.0.0.1:5500',
    'http://localhost:8080', 'http://127.0.0.1:8080',
]
_env_origins = os.environ.get('LATIO_ALLOWED_ORIGINS', '').strip()
ALLOWED_ORIGINS = [o.strip() for o in _env_origins.split(',') if o.strip()] if _env_origins else _DEFAULT_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

@app.get('/')
def root():
    return {'lab': 'DataLex Lab', 'website': 'https://www.datalexlab.com', 'project': 'LATIO API', 'version': '1.0.0', 'docs': '/docs'}


@app.get('/health')
def health():
    """Health check para orquestadores de despliegue (Docker, balanceadores,
    plataformas PaaS) — no valida dependencias externas porque no hay
    ninguna (sin base de datos, sin servicios externos); solo confirma que
    el proceso responde."""
    return {'status': 'ok'}


# --------------------------------------------------------------------------
# /v1/reasoning — motor de razonamiento jurídico derrotable (PROLEG)
# --------------------------------------------------------------------------

class RulebaseInfo(BaseModel):
    id: str
    description: str


class ProveRequest(BaseModel):
    rulebase_id: str
    goal: str
    party: Party
    facts: List[FactEntry]


@app.get('/v1/reasoning/rulebases', response_model=List[RulebaseInfo])
def list_rulebases():
    return [
        RulebaseInfo(id=rulebase_id, description=getattr(rulebase, 'description', ''))
        for rulebase_id, rulebase in RULEBASES.items()
    ]


@app.post('/v1/reasoning/prove', response_model=ProofResult)
def reasoning_prove(req: ProveRequest):
    rulebase = RULEBASES.get(req.rulebase_id)
    if rulebase is None:
        raise HTTPException(status_code=404, detail=f"rulebase_id '{req.rulebase_id}' no encontrado")

    factbase = FactBase(entries=req.facts)
    return prove(req.goal, req.party, rulebase, factbase)


# --------------------------------------------------------------------------
# /v1/corpora — navegación de los 8 corpus legales reales ya extraídos por
# src/pipeline.py (data/processed/<corpus_id>_articles.json +
# reports/manifest.json). Contenido genuino, no mockeado: a diferencia de
# los endpoints /v1/statements/* y /v1/behavior/* del explorador
# (toolkit-api/index.html, banner "Modo demostración"), estos endpoints
# leen directamente los artefactos reales del pipeline.
# --------------------------------------------------------------------------

_ROOT = Path(__file__).resolve().parent.parent
_DATA_PROCESSED = _ROOT / "data" / "processed"
_REPORTS_DIR = _ROOT / "reports"
_CONFIG_DIR = _ROOT / "config"


def _load_manifest() -> dict:
    manifest_path = _REPORTS_DIR / "manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _load_corpus_registry() -> dict:
    registry_path = _CONFIG_DIR / "corpus_registry.yaml"
    with open(registry_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# Leídos una sola vez al arrancar el proceso (no en cada request) — el
# manifiesto y el registro de corpus son metadata pequeña y estable durante
# la vida del proceso; re-leerlos por request sería I/O de disco
# innecesario en un endpoint de listado que se puede llamar seguido.
_MANIFEST = _load_manifest()
_CORPUS_REGISTRY = _load_corpus_registry()
_CORPUS_ENTRIES: Dict[str, dict] = {
    entry["corpus_id"]: entry for entry in _MANIFEST.get("corpora", [])
}

# Los artículos completos (miles por corpus, hasta ~4.4MB por archivo) se
# cargan de forma perezosa la primera vez que se piden y quedan cacheados en
# memoria para el resto de la vida del proceso — ver consigna: "cachear en
# memoria al arrancar el proceso está bien" / "no cargues el archivo
# completo en cada request si podés evitarlo razonablemente". Cargar los 8
# de una al levantar el proceso alargaría el arranque para el caso común de
# solo consultar /v1/corpora o un único corpus; con caché perezosa el costo
# de lectura se paga una sola vez, en el primer acceso a cada corpus.
_ARTICLES_CACHE: Dict[str, List[dict]] = {}
_ARTICLES_BY_UID_CACHE: Dict[str, Dict[str, dict]] = {}

ARTICLE_TEXT_PREVIEW_CHARS = 300


class CorpusSummary(BaseModel):
    corpus_id: str
    display_name: str
    jurisdiction: str
    articles_parsed: int
    expected_article_count: int
    recall: float


class CorpusGates(BaseModel):
    completitud: str
    unicidad: str
    consistencia_N4: str
    integridad_grafo: str
    cuerpo_no_vacio: str
    trazabilidad: str


class CorpusDetail(CorpusSummary):
    gates: CorpusGates


class ArticlePathLevel(BaseModel):
    level_type: Optional[str] = None
    rank: Optional[int] = None
    ordinal: Optional[str] = None
    ordinal_int: Optional[int] = None
    label: Optional[str] = None
    depth: Optional[int] = None


class ArticleSummary(BaseModel):
    uid: str
    number: Optional[int] = None
    suffix: Optional[str] = None
    path: List[ArticlePathLevel] = Field(default_factory=list)
    text_raw: str
    truncated: bool


class ArticleListResponse(BaseModel):
    corpus_id: str
    total: int
    limit: int
    offset: int
    articles: List[ArticleSummary]


class ArticleFull(BaseModel):
    uid: str
    number: Optional[int] = None
    suffix: Optional[str] = None
    path: List[ArticlePathLevel] = Field(default_factory=list)
    text_raw: str
    editorial_notes: List[str] = Field(default_factory=list)
    qa_flags: List[str] = Field(default_factory=list)
    position_index: Optional[int] = None


def _require_known_corpus(corpus_id: str) -> dict:
    """Devuelve la fila de reports/manifest.json para corpus_id, o levanta un
    404 explícito con la lista de corpus disponibles — nunca deja que un
    KeyError crudo llegue al cliente."""
    entry = _CORPUS_ENTRIES.get(corpus_id)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"corpus_id '{corpus_id}' no encontrado. "
                f"Corpus disponibles: {sorted(_CORPUS_ENTRIES)}"
            ),
        )
    return entry


def _corpus_summary(corpus_id: str, entry: dict) -> CorpusSummary:
    reg = _CORPUS_REGISTRY.get(corpus_id) or {}
    return CorpusSummary(
        corpus_id=corpus_id,
        display_name=reg.get("display_name", corpus_id),
        jurisdiction=reg.get("jurisdiction", "?"),
        articles_parsed=entry["articles_parsed"],
        expected_article_count=entry["expected_article_count"],
        recall=entry["recall"],
    )


def _load_articles(corpus_id: str) -> List[dict]:
    """Carga (con caché en memoria tras el primer acceso) los artículos
    reales de data/processed/<corpus_id>_articles.json. Nunca deja escapar
    un FileNotFoundError/JSONDecodeError crudo como 500 sin contexto."""
    _require_known_corpus(corpus_id)

    if corpus_id in _ARTICLES_CACHE:
        return _ARTICLES_CACHE[corpus_id]

    path = _DATA_PROCESSED / f"{corpus_id}_articles.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            articles = json.load(f)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"No se encontró el archivo de artículos de '{corpus_id}' ({path.name}).",
        )
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"El archivo de artículos de '{corpus_id}' está corrupto o mal formado: {exc}",
        )

    _ARTICLES_CACHE[corpus_id] = articles
    _ARTICLES_BY_UID_CACHE[corpus_id] = {a["uid"]: a for a in articles}
    return articles


@app.get('/v1/corpora', response_model=List[CorpusSummary])
def list_corpora():
    """Lista los 8 corpus legales reales (LATAM) ya extraídos por el
    pipeline, con su metadata de reports/manifest.json y
    config/corpus_registry.yaml."""
    return [_corpus_summary(cid, entry) for cid, entry in _CORPUS_ENTRIES.items()]


@app.get('/v1/corpora/{corpus_id}', response_model=CorpusDetail)
def get_corpus(corpus_id: str):
    """Detalle de un corpus: metadata + las 6 compuertas de calidad
    (gates) de reports/manifest.json."""
    entry = _require_known_corpus(corpus_id)
    summary = _corpus_summary(corpus_id, entry)
    gates = entry.get("gates", {})
    return CorpusDetail(**summary.model_dump(), gates=CorpusGates(**gates))


@app.get('/v1/corpora/{corpus_id}/articles', response_model=ArticleListResponse)
def list_corpus_articles(
    corpus_id: str,
    limit: int = Query(50, ge=1, le=200, description="Tamaño de página (máx. 200)"),
    offset: int = Query(0, ge=0, description="Desplazamiento desde el primer artículo"),
):
    """Lista paginada de artículos reales de un corpus. `text_raw` se
    recorta a ARTICLE_TEXT_PREVIEW_CHARS caracteres (ver `truncated`); usar
    GET /v1/corpora/{corpus_id}/articles/{uid} para el texto completo."""
    articles = _load_articles(corpus_id)
    total = len(articles)
    page = articles[offset: offset + limit]

    out: List[ArticleSummary] = []
    for a in page:
        text = a.get("text_raw") or ""
        truncated = len(text) > ARTICLE_TEXT_PREVIEW_CHARS
        out.append(ArticleSummary(
            uid=a["uid"],
            number=a.get("number"),
            suffix=a.get("suffix"),
            path=[ArticlePathLevel(**lvl) for lvl in a.get("path") or []],
            text_raw=text[:ARTICLE_TEXT_PREVIEW_CHARS],
            truncated=truncated,
        ))

    return ArticleListResponse(corpus_id=corpus_id, total=total, limit=limit, offset=offset, articles=out)


@app.get('/v1/corpora/{corpus_id}/articles/{uid}', response_model=ArticleFull)
def get_corpus_article(corpus_id: str, uid: str):
    """Un artículo real completo (texto sin recortar) por su uid exacto."""
    _load_articles(corpus_id)
    article = _ARTICLES_BY_UID_CACHE.get(corpus_id, {}).get(uid)
    if article is None:
        raise HTTPException(
            status_code=404,
            detail=f"uid '{uid}' no encontrado en corpus '{corpus_id}'.",
        )
    return ArticleFull(**article)


# --------------------------------------------------------------------------
# /v1/statements/validate — valida un etiquetado propuesto (por reglas
# deterministas locales, ver src/labeling/, o por un humano) contra el
# esquema ontológico REAL del proyecto (NormativeStatement, src/models.py).
# Este endpoint es la parte verificable del flujo: quien propone el
# etiquetado nunca reimplementa las reglas de compatibilidad — las manda
# acá y Pydantic decide, con el motivo exacto si rechaza.
#
# Campos deliberadamente EXCLUIDOS del etiquetado propuesto:
# `hohfeldian_position` (Hohfeld exige el correlato, que ni una regla local
# ni un anotador humano sin contexto adicional tienen de forma confiable —
# ver docs/limitaciones_conocidas.md §2) y `generality_level`/`derogability`
# (son DERIVADOS por código real: `derive_generality()` y
# `DEROGABILITY_MARKER_RE` en src/models.py). Este endpoint aplica esos
# defaults/derivaciones reales en vez de pedirlos como input.
# --------------------------------------------------------------------------

class StatementDraftRequest(BaseModel):
    text_span: str = Field(min_length=1)
    statement_type: StatementType
    structure: Structure
    deontic_modality: DeonticModality
    addressee: Addressee
    antecedent_operator: AntecedentOperator
    exception_present: bool = False
    exception_marker: Optional[str] = None
    exception_scope: Optional[str] = None  # restringido a interna|por_remision
    generality_n_conditions: int = Field(ge=0)
    generality_has_enumeration: bool = False
    generality_enumeration_closed: Optional[bool] = None
    generality_indeterminate_concepts: List[str] = Field(default_factory=list)
    # Solo relevante si statement_type == "presuncion" — marcador textual
    # explícito ("se presume de derecho" vs. "se presume"), no inferencia.
    presumption_rebuttable: Optional[bool] = None
    # Procedencia real del etiquetado propuesto — nunca se asume "llm" por
    # defecto (ver src/models.py: "heuristica_local" es src/labeling/rules.py).
    annotated_by: Literal["human", "llm", "llm+human", "heuristica_local"] = "heuristica_local"


class StatementValidationResult(BaseModel):
    valid: bool
    normalized: Optional[Dict[str, Any]] = None
    computed: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@app.post('/v1/statements/validate', response_model=StatementValidationResult)
def validate_statement(req: StatementDraftRequest):
    """Construye un NormativeStatement real a partir de un etiquetado
    propuesto y devuelve si el esquema ontológico lo acepta o lo rechaza —
    con el motivo exacto del rechazo si corresponde. No persiste nada."""
    presumption = None
    derogability = "indeterminada"
    if req.statement_type == "presuncion":
        rebuttable = req.presumption_rebuttable if req.presumption_rebuttable is not None else True
        presumption = {
            "rebuttable": rebuttable,
            "burden_shifts_to": "partes" if rebuttable else "ninguno",
        }
        if not rebuttable:
            derogability = "inderogable"

    try:
        stmt = NormativeStatement(
            statement_id=0,
            span_type="articulo_completo",
            text_span=req.text_span,
            statement_type=req.statement_type,
            structure=req.structure,
            deontic_modality=req.deontic_modality,
            hohfeldian_position="ninguno",
            derogability=derogability,
            addressee=req.addressee,
            antecedent_operator=req.antecedent_operator,
            exception=ExceptionInfo(
                present=req.exception_present,
                marker=req.exception_marker if req.exception_present else None,
                scope=req.exception_scope if req.exception_present else None,
            ),
            presumption=presumption,
            generality=GeneralityProxies(
                n_conditions=req.generality_n_conditions,
                has_enumeration=req.generality_has_enumeration,
                enumeration_closed=req.generality_enumeration_closed,
                indeterminate_concepts=req.generality_indeterminate_concepts,
            ),
            annotated_by=req.annotated_by,
            verified=False,
        )
    except ValidationError as exc:
        return StatementValidationResult(valid=False, error=str(exc))

    return StatementValidationResult(
        valid=True,
        normalized=stmt.model_dump(mode="json"),
        computed={
            "generality_level": stmt.generality_level,
            "derogability_marker_detected": stmt.derogability_marker_detected,
        },
    )


# --------------------------------------------------------------------------
# /v1/statements/propose — primer paso del etiquetado sin LLM ni costo
# externo (ver src/labeling/rules.py): a partir del texto de un artículo,
# propone los campos donde hay evidencia léxica confiable dentro del propio
# proyecto (antecedent_operator, exception, presuncion/remision, structure
# derivado de COMPATIBILITY). Los campos sin evidencia suficiente quedan
# explícitos en `undetermined_fields`, no se adivinan. El resultado de este
# endpoint es solo una propuesta parcial: se completa a mano y se confirma
# con /v1/statements/validate antes de darlo por válido.
# --------------------------------------------------------------------------

class ProposeLabelsRequest(BaseModel):
    text_span: str = Field(min_length=1, max_length=4000)


@app.post('/v1/statements/propose', response_model=LabelProposal)
def propose_statement_labels(req: ProposeLabelsRequest):
    return propose_from_text(req.text_span)
