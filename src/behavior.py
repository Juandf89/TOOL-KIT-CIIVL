"""
behavior.py — Cómo se comporta la lógica del civil law dentro de cada código.
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    # Permite `python src/behavior.py`, `python -m src.behavior` y el import
    # normal de pytest (`from src.behavior import ...`) sin duplicar lógica
    # de import condicional en cada función.
    sys.path.insert(0, str(ROOT))

from src.models import (  # noqa: E402 — requiere el sys.path.insert de arriba
    Architecture,
    ArticleRecord,
    ExceptionInfo,
    GeneralityProxies,
    Institution,
    NormativeStatement,
    PathNode,
    PresumptionInfo,
    TimeLimit,
    Validity,
)

PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"
BEHAVIOR_VERSION = "behavior_v0.1"

CORPORA = ["CL-CC", "CO-CC", "AR-CC", "AR-CCYC", "BR-CC", "MX-CCF", "MX-CDMX", "PE-CC"]
NAMES = {"CL-CC": "Chile", "CO-CC": "Colombia", "AR-CC": "Argentina · Vélez",
         "AR-CCYC": "Argentina · CCyC", "BR-CC": "Brasil", "MX-CCF": "México federal",
         "MX-CDMX": "México capital", "PE-CC": "Perú"}

# ---------------------------------------------------------------------------
# Adaptador ArticleRecord (esquema real, src/models.py) -> dict plano
# ---------------------------------------------------------------------------
# profile_of()/FEATURES más abajo son PREVIOS a models.py n3_v1.1 y usan
# claves inventadas (P6_deontic, is_definitional, ...) que no existen en el
# modelo Pydantic real (ver C-5 en reports/debate_revision_2026-09-10.md).
# En vez de reescribir profile_of()/FEATURES (funcionan bien sobre su propio
# vocabulario), este adaptador traduce un ArticleRecord real al mismo dict
# plano que ya consumen, de modo que ambos queden sincronizados sin duplicar
# el vocabulario en dos lugares.

def article_to_profile(article: ArticleRecord) -> dict:
    """Traduce un ArticleRecord/NormativeStatement real (src/models.py) al
    dict plano que consumen profile_of() y FEATURES.

    Mapeo (N3 real -> clave plana histórica):
      is_definition            -> is_definitional
      {s.deontic_modality}     -> P6_deontic       (lista, excluye 'ninguno')
      {s.addressee}            -> P5_addressee     (lista)
      has_exception             -> P3_exception
      generality.indeterminate_concepts (aplanado) -> P2_indeterminate
      has_time_limit            -> has_time_limit
      statement_type=='presuncion' en algún enunciado -> is_presumption
      {s.antecedent_operator}  -> antecedent       (lista, excluye 'ninguno_explicito')
    """
    statements = article.n3_statements
    deontic = sorted({s.deontic_modality for s in statements if s.deontic_modality != "ninguno"})
    addressees = sorted({s.addressee for s in statements})
    indeterminate = [c for s in statements for c in s.generality.indeterminate_concepts]
    antecedents = [s.antecedent_operator for s in statements if s.antecedent_operator != "ninguno_explicito"]

    return {
        "is_definitional": article.is_definition,
        "P6_deontic": deontic,
        "P5_addressee": addressees,
        "P3_exception": article.has_exception,
        "P2_indeterminate": indeterminate,
        "has_time_limit": article.has_time_limit,
        "is_presumption": any(s.statement_type == "presuncion" for s in statements),
        "antecedent": antecedents,
    }

def profile_of(p: dict) -> tuple:
    return (
        "DEF" if p.get("is_definitional") else "",
        "OBL" if "obligacion" in p.get("P6_deontic", []) else
        ("PRO" if "prohibicion" in p.get("P6_deontic", []) else
         ("PER" if "permiso" in p.get("P6_deontic", []) else "")),
        "JUE" if "juez" in p.get("P5_addressee", []) else "",
        "EXC" if p.get("P3_exception") else "",
        "IND" if p.get("P2_indeterminate") else "",
        "PLZ" if p.get("has_time_limit") else "",
        "PRE" if p.get("is_presumption") else "",
    )

FEATURES = {
    "definitorio":     lambda p: p.get("is_definitional", False),
    "obligación":      lambda p: "obligacion" in p.get("P6_deontic", []),
    "permiso":         lambda p: "permiso" in p.get("P6_deontic", []),
    "prohibición":     lambda p: "prohibicion" in p.get("P6_deontic", []),
    "juez":            lambda p: "juez" in p.get("P5_addressee", []),
    "notario":         lambda p: "funcionario_o_notario" in p.get("P5_addressee", []),
    "partes":          lambda p: "partes" in p.get("P5_addressee", []),
    "excepción":       lambda p: bool(p.get("P3_exception")),
    "indeterminado":   lambda p: bool(p.get("P2_indeterminate")),
    "plazo":           lambda p: p.get("has_time_limit", False),
    "presunción":      lambda p: p.get("is_presumption", False),
    "antecedente":     lambda p: bool(p.get("antecedent")),
}

# ---------------------------------------------------------------------------
# CLI — corre lectura + profile_of() de punta a punta
# ---------------------------------------------------------------------------
# El pipeline (src/pipeline.py) hoy solo produce N0/N1/N4; N2/N3/N5
# (institución, enunciados anotados, vigencia) dependen de anotación
# humana/LLM externa que no existe todavía en data/processed/ (ver C-3 en
# reports/debate_revision_2026-09-10.md). Por eso este CLI corre sobre un
# fixture de ArticleRecord embebido, sintético y claramente marcado como tal,
# en vez de simular datos de anotación real. Reemplazar `_fixture_articles()`
# por una carga real desde data/processed/*.json en cuanto exista un lote de
# artículos anotados con el esquema n3_v1.1.

def _fixture_articles() -> list[ArticleRecord]:
    """Dos ArticleRecord sintéticos (FIXTURE DE PRUEBA, no corpus real) que
    cubren distintas ramas del adaptador: definición con concepto
    indeterminado, y obligación con excepción + plazo + presunción simple.
    Ver tests/test_behavior.py para las mismas instancias usadas como test."""
    article_a = ArticleRecord(
        uid="XX-TEST-2026-ART-1",
        jurisdiction="XX",
        code_id="TEST",
        manifest_id="fixture-behavior-v1",
        source_version_date=date(2026, 1, 1),
        source_url="N/A - fixture sintético",
        source_retrieved_at=date(2026, 1, 1),
        source_hash="sha256:" + "0" * 64,
        n1_architecture=Architecture(
            path=[PathNode(level_type="titulo", ordinal="I", label="TÍTULO I", depth=0)],
            position_index=0,
        ),
        n2_institution=Institution(primary="personas", verified=True),
        n3_statements=[
            NormativeStatement(
                statement_id=0,
                span_type="articulo_completo",
                statement_type="definicion",
                structure="definicion_pura",
                deontic_modality="ninguno",
                hohfeldian_position="ninguno",
                derogability="indeterminada",
                addressee="partes",
                antecedent_operator="ninguno_explicito",
                generality=GeneralityProxies(
                    n_conditions=0, has_enumeration=False,
                    indeterminate_concepts=["buena fe"],
                ),
                verified=True,
            ),
        ],
        n5_validity=Validity(status="vigente"),
        text_raw="Toda persona debe actuar de buena fe.",
        text_normalized="toda persona debe actuar de buena fe.",
    )

    article_b = ArticleRecord(
        uid="XX-TEST-2026-ART-2",
        jurisdiction="XX",
        code_id="TEST",
        manifest_id="fixture-behavior-v1",
        source_version_date=date(2026, 1, 1),
        source_url="N/A - fixture sintético",
        source_retrieved_at=date(2026, 1, 1),
        source_hash="sha256:" + "1" * 64,
        n1_architecture=Architecture(
            path=[PathNode(level_type="titulo", ordinal="II", label="TÍTULO II", depth=0)],
            position_index=1,
        ),
        n2_institution=Institution(primary="obligaciones", verified=True),
        n3_statements=[
            NormativeStatement(
                statement_id=0,
                span_type="articulo_completo",
                statement_type="presuncion",
                structure="supuesto_consecuencia_con_excepcion",
                deontic_modality="obligacion",
                hohfeldian_position="deber",
                derogability="derogable_por_pacto",
                addressee="juez",
                antecedent_operator="si",
                exception=ExceptionInfo(present=True, marker="salvo", scope="interna"),
                presumption=PresumptionInfo(rebuttable=True, burden_shifts_to="partes"),
                time_limit=TimeLimit(has=True, values=[(30, "dias")], nature="plazo_de_ejercicio"),
                generality=GeneralityProxies(n_conditions=1, has_enumeration=False),
                verified=True,
            ),
        ],
        n5_validity=Validity(status="vigente"),
        text_raw="El deudor debe pagar dentro de 30 días, salvo pacto en contrario. Se presume la mora.",
        text_normalized="el deudor debe pagar dentro de 30 dias, salvo pacto en contrario. se presume la mora.",
    )
    return [article_a, article_b]

def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass

    articles = _fixture_articles()
    profiles = {a.uid: article_to_profile(a) for a in articles}
    report = {
        "behavior_version": BEHAVIOR_VERSION,
        "note": (
            "TODO: reemplazar _fixture_articles() por carga real de "
            "data/processed/*.json en cuanto exista un lote de ArticleRecord "
            "anotados (N2/N3/N5); hoy corre sobre un fixture sintético "
            "embebido en behavior.py, no sobre datos jurídicos reales."
        ),
        "profiles": {
            uid: {
                "flat_profile": p,
                "profile_tuple": list(profile_of(p)),
                "features": {name: fn(p) for name, fn in FEATURES.items()},
            }
            for uid, p in profiles.items()
        },
    }

    REPORTS.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS / "behavior_fixture_report.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
