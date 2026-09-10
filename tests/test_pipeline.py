"""Tests de src/pipeline.py: segmentación (monotonicidad, INTERPOLATION_JUMP),
remisiones (numéricas, anafóricas, reflexivas) y gates(). Incluye además un
smoke test end-to-end contra el corpus TEST-FIXTURE (data/raw/ +
config/corpus_registry.yaml) para confirmar que el CLI corre sin romperse.
"""

from __future__ import annotations

import pytest

from src.pipeline import (
    INTERPOLATION_JUMP,
    Article,
    Corpus,
    extract,
    gates,
    load_registry,
    referrals,
    segment,
)


def _cfg(expected: int = 2, official: bool = True) -> dict:
    return {
        "jurisdiction": "XX",
        "code_id": "TEST",
        "year_tag": "2026",
        "parsing": {
            "article_pattern": r"^Art[íi]culo\s+(?P<num>\d+)\.?\s*",
            "levels": [{"type": "titulo", "pattern": r"^T[ÍI]TULO\s+(?P<ord>[IVXLCDM]+)\b"}],
        },
        "expected_article_count": expected,
        "source": {"official": official},
    }


def _gate(gate_results: list[dict], name: str) -> dict:
    for g in gate_results:
        if g["gate"] == name:
            return g
    raise AssertionError(f"gate {name!r} no encontrado en {[g['gate'] for g in gate_results]}")


# ---------------------------------------------------------------------------
# segment(): monotonicidad e INTERPOLATION_JUMP
# ---------------------------------------------------------------------------

def test_interpolation_jump_threshold_is_50():
    assert INTERPOLATION_JUMP == 50


def test_small_backward_jump_is_merged_into_current_article():
    lines = [
        "Artículo 1. Texto uno.",
        "Artículo 2. Texto dos.",
        "Artículo 10. Texto diez.",
        "Artículo 5. Texto cinco reformado.",  # backward, diff=5 <= 50
    ]
    c = Corpus("X", _cfg(expected=3), lines)
    articles, stats = segment(c)

    assert stats["rejected_non_monotonic"] == 1
    assert [a.number for a in articles] == [1, 2, 10]
    # la línea "backward" se funde en el cuerpo del artículo abierto (10), no
    # crea un artículo nuevo ni se descarta.
    assert "reformado" in articles[-1].text_raw


def test_backward_jump_beyond_interpolation_jump_drops_the_line():
    lines = [
        "Artículo 1. Texto uno.",
        "Artículo 60. Texto sesenta.",
        "Artículo 3. Texto tres perdido.",   # backward, diff=57 > 50 -> superseded
        "Artículo 61. Texto sesenta y uno.",  # no backward (61 >= 60) -> cierra superseded
    ]
    c = Corpus("X", _cfg(expected=3), lines)
    articles, stats = segment(c)

    assert stats["rejected_non_monotonic"] == 1
    assert [a.number for a in articles] == [1, 60, 61]
    assert all("perdido" not in a.text_raw for a in articles)


def test_monotonic_sequence_has_no_rejections():
    lines = ["Artículo 1. Uno.", "Artículo 2. Dos.", "Artículo 3. Tres."]
    c = Corpus("X", _cfg(expected=3), lines)
    articles, stats = segment(c)

    assert stats["rejected_non_monotonic"] == 0
    assert [a.number for a in articles] == [1, 2, 3]


# ---------------------------------------------------------------------------
# referrals(): numérica, anafórica y reflexiva
# ---------------------------------------------------------------------------

def _articles_for_referrals() -> list[Article]:
    return [
        Article(uid="A-1", number=1, suffix=None, path=[], position_index=0,
                text_raw="Texto base."),
        Article(uid="A-2", number=2, suffix=None, path=[], position_index=1,
                text_raw="Referencia al artículo 1 y al artículo anterior."),
        Article(uid="A-3", number=3, suffix=None, path=[], position_index=2,
                text_raw="Ver el artículo siguiente y el artículo 99."),
    ]


def test_numeric_referral_resolves_to_target():
    edges, stats = referrals(_articles_for_referrals(), "XX", "TEST", "2026")
    numeric = [e for e in edges if e["resolution"] == "numeric"]
    resolved_numeric = [e for e in numeric if e["target"] is not None]
    assert any(e["source"] == "A-2" and e["target"] == "A-1" for e in resolved_numeric)


def test_anaphoric_referral_resolves_previous_and_next():
    edges, stats = referrals(_articles_for_referrals(), "XX", "TEST", "2026")
    # stats["edges_anaphoric"] cuenta todo match de ANA_REF, resuelva o no.
    assert stats["edges_anaphoric"] == 2
    # "artículo anterior" en A-2 -> A-1 (resuelto -> resolution="anaphoric")
    assert any(e["source"] == "A-2" and e["target"] == "A-1" and e["resolution"] == "anaphoric"
               for e in edges)
    # "artículo siguiente" en A-3 -> no existe A-4 -> sin resolver. El
    # pipeline etiqueta esto resolution="unresolved" (no "anaphoric"): el
    # campo resolution solo distingue anaphoric/numeric cuando SÍ resuelve.
    assert any(e["source"] == "A-3" and e["target"] is None and e["resolution"] == "unresolved"
               and "siguiente" in e["raw_reference"].lower() for e in edges)


def test_unresolved_numeric_referral_is_counted():
    edges, stats = referrals(_articles_for_referrals(), "XX", "TEST", "2026")
    assert any(e["source"] == "A-3" and e["resolution"] == "unresolved" and
               e["raw_reference"].endswith("99") for e in edges)
    assert stats["edges_unresolved"] == 2  # artículo 99 (numeric) + artículo siguiente (anaphoric)
    assert stats["resolution_rate"] == pytest.approx(0.5)


def test_reflexive_referral_is_detected():
    self_referencing = [
        Article(uid="A-1", number=1, suffix=None, path=[], position_index=0,
                text_raw="Ver el artículo 1 mismo."),
    ]
    edges, stats = referrals(self_referencing, "XX", "TEST", "2026")
    assert stats["reflexive"] == 1
    assert edges[0]["source"] == edges[0]["target"] == "A-1"


# ---------------------------------------------------------------------------
# gates()
# ---------------------------------------------------------------------------

def _seg_stats(empty_body: int = 0) -> dict:
    return {"empty_body": empty_body}


def _ref_stats(resolution_rate, reflexive: int = 0, edges_unresolved: int = 0) -> dict:
    return {"resolution_rate": resolution_rate, "reflexive": reflexive,
            "edges_unresolved": edges_unresolved}


def test_gates_completitud_pass_when_all_expected_numbers_present():
    articles = [Article(uid=f"A-{n}", number=n, suffix=None, path=[], position_index=n - 1,
                         text_raw="x") for n in (1, 2, 3)]
    c = Corpus("X", _cfg(expected=3), lines=[])
    result = gates(c, articles, _seg_stats(), _ref_stats(1.0))
    assert _gate(result, "completitud")["status"] == "PASS"


def test_gates_completitud_fail_when_numbers_missing():
    articles = [Article(uid="A-1", number=1, suffix=None, path=[], position_index=0, text_raw="x")]
    c = Corpus("X", _cfg(expected=3), lines=[])
    result = gates(c, articles, _seg_stats(), _ref_stats(1.0))
    g = _gate(result, "completitud")
    assert g["status"] == "FAIL"
    assert "2" in g["detail"] or "3" in g["detail"]


def test_gates_unicidad_fail_on_duplicate_uid():
    articles = [
        Article(uid="A-1", number=1, suffix=None, path=[], position_index=0, text_raw="x"),
        Article(uid="A-1", number=2, suffix=None, path=[], position_index=1, text_raw="y"),
    ]
    c = Corpus("X", _cfg(expected=2), lines=[])
    result = gates(c, articles, _seg_stats(), _ref_stats(1.0))
    assert _gate(result, "unicidad")["status"] == "FAIL"


def test_gates_consistencia_n4_threshold_is_098():
    articles = [Article(uid="A-1", number=1, suffix=None, path=[], position_index=0, text_raw="x")]
    c = Corpus("X", _cfg(expected=1), lines=[])

    below = gates(c, articles, _seg_stats(), _ref_stats(0.97))
    at_threshold = gates(c, articles, _seg_stats(), _ref_stats(0.98))

    assert _gate(below, "consistencia_N4")["status"] == "FAIL"
    assert _gate(at_threshold, "consistencia_N4")["status"] == "PASS"


def test_gates_integridad_grafo_warns_on_reflexive_edges():
    articles = [Article(uid="A-1", number=1, suffix=None, path=[], position_index=0, text_raw="x")]
    c = Corpus("X", _cfg(expected=1), lines=[])
    result = gates(c, articles, _seg_stats(), _ref_stats(1.0, reflexive=1))
    assert _gate(result, "integridad_grafo")["status"] == "WARN"


def test_gates_cuerpo_no_vacio_warns_on_empty_bodies():
    articles = [Article(uid="A-1", number=1, suffix=None, path=[], position_index=0, text_raw="x")]
    c = Corpus("X", _cfg(expected=1), lines=[])
    result = gates(c, articles, _seg_stats(empty_body=1), _ref_stats(1.0))
    assert _gate(result, "cuerpo_no_vacio")["status"] == "WARN"


def test_gates_trazabilidad_fail_on_non_official_source():
    articles = [Article(uid="A-1", number=1, suffix=None, path=[], position_index=0, text_raw="x")]
    c = Corpus("X", _cfg(expected=1, official=False), lines=[])
    result = gates(c, articles, _seg_stats(), _ref_stats(1.0))
    assert _gate(result, "trazabilidad")["status"] == "FAIL"


def test_gates_trazabilidad_pass_on_official_source():
    articles = [Article(uid="A-1", number=1, suffix=None, path=[], position_index=0, text_raw="x")]
    c = Corpus("X", _cfg(expected=1, official=True), lines=[])
    result = gates(c, articles, _seg_stats(), _ref_stats(1.0))
    assert _gate(result, "trazabilidad")["status"] == "PASS"


# ---------------------------------------------------------------------------
# Smoke test end-to-end: extract -> segment -> referrals -> gates contra el
# corpus TEST-FIXTURE real (data/raw/fixture_test_corpus.md +
# config/corpus_registry.yaml). Confirma que el pipeline corre de punta a
# punta sin KeyError ni excepción (ver C-1 del debate de revisión).
# ---------------------------------------------------------------------------

def test_pipeline_end_to_end_on_test_fixture_corpus():
    registry = load_registry()
    assert "TEST-FIXTURE" in registry

    c = extract("TEST-FIXTURE", registry)
    articles, seg_stats = segment(c)
    edges, ref_stats = referrals(articles, c.cfg["jurisdiction"], c.cfg["code_id"], c.cfg["year_tag"])
    gate_results = gates(c, articles, seg_stats, ref_stats)

    assert len(articles) == 4
    assert seg_stats["articles_parsed"] == 4
    assert ref_stats["reflexive"] == 0

    # todas las compuertas deben correr sin excepción; solo trazabilidad
    # debe fallar porque la fuente TEST-FIXTURE está marcada official=false
    # a propósito (es un dataset sintético, no una fuente jurídica real).
    statuses = {g["gate"]: g["status"] for g in gate_results}
    assert statuses["trazabilidad"] == "FAIL"
    for name, status in statuses.items():
        if name != "trazabilidad":
            assert status == "PASS", f"{name} inesperadamente en {status}"
