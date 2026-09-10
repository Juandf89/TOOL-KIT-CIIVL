"""Tests de los validadores Pydantic de src/models.py.

Cubre, por cada model_validator: al menos un caso válido y uno inválido
(salvo que el propio validador solo tenga un lado que pueda fallar).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.models import (
    ArticleRecord,
    ExceptionInfo,
    GeneralityProxies,
    NormativeStatement,
    PathNode,
    PresumptionInfo,
    Referral,
    Referrals,
    TimeLimit,
)
from tests.factories import make_article, make_statement

# ---------------------------------------------------------------------------
# ExceptionInfo._coherence
# ---------------------------------------------------------------------------

def test_exception_info_present_without_scope_raises():
    with pytest.raises(ValidationError, match="exige scope"):
        ExceptionInfo(present=True, scope=None)

def test_exception_info_present_true_with_scope_is_valid():
    exc = ExceptionInfo(present=True, scope="interna", marker="salvo")
    assert exc.present is True

def test_exception_info_absent_with_marker_raises():
    with pytest.raises(ValidationError, match="no admite marker"):
        ExceptionInfo(present=False, marker="salvo")

def test_exception_info_absent_default_is_valid():
    exc = ExceptionInfo()
    assert exc.present is False and exc.scope is None

# ---------------------------------------------------------------------------
# PresumptionInfo._coherence (B-2 del debate de revisión)
# ---------------------------------------------------------------------------

def test_presumption_info_irrebuttable_with_burden_shift_raises():
    with pytest.raises(ValidationError, match="burden_shifts_to"):
        PresumptionInfo(rebuttable=False, burden_shifts_to="partes")

def test_presumption_info_irrebuttable_with_ninguno_is_valid():
    p = PresumptionInfo(rebuttable=False, burden_shifts_to="ninguno")
    assert p.rebuttable is False

def test_presumption_info_rebuttable_with_burden_shift_is_valid():
    p = PresumptionInfo(rebuttable=True, burden_shifts_to="partes")
    assert p.burden_shifts_to == "partes"

# ---------------------------------------------------------------------------
# TimeLimit._coherence
# ---------------------------------------------------------------------------

def test_time_limit_has_true_without_nature_raises():
    with pytest.raises(ValidationError, match="exige nature"):
        TimeLimit(has=True, values=[(30, "dias")], nature=None)

def test_time_limit_has_false_with_values_raises():
    with pytest.raises(ValidationError, match="no admite values"):
        TimeLimit(has=False, values=[(30, "dias")])

def test_time_limit_has_true_valid_computes_min_days():
    tl = TimeLimit(has=True, values=[(2, "meses"), (10, "dias")], nature="plazo_de_ejercicio")
    assert tl.min_days == 10  # min(2*30, 10*1)

def test_time_limit_default_is_valid_and_min_days_none():
    tl = TimeLimit()
    assert tl.min_days is None

# ---------------------------------------------------------------------------
# GeneralityProxies._enum_coherence
# ---------------------------------------------------------------------------

def test_generality_proxies_enum_closed_without_enumeration_raises():
    with pytest.raises(ValidationError, match="enumeration_closed debe ser None"):
        GeneralityProxies(n_conditions=1, has_enumeration=False, enumeration_closed=True)

def test_generality_proxies_enumeration_without_closed_flag_raises():
    with pytest.raises(ValidationError, match="exige enumeration_closed"):
        GeneralityProxies(n_conditions=1, has_enumeration=True, enumeration_closed=None)

def test_generality_proxies_valid_enumeration():
    g = GeneralityProxies(n_conditions=1, has_enumeration=True, enumeration_closed=True)
    assert g.derive_generality() == "casuistica"

def test_generality_proxies_clausula_general():
    g = GeneralityProxies(n_conditions=0, has_enumeration=False,
                           indeterminate_concepts=["buena fe"])
    assert g.derive_generality() == "clausula_general"

# ---------------------------------------------------------------------------
# NormativeStatement._rules
# ---------------------------------------------------------------------------

def test_statement_illegal_type_structure_combination_raises():
    with pytest.raises(ValidationError, match="combinación ilegal"):
        make_statement(statement_type="regla", structure="definicion_pura")

def test_statement_valid_type_structure_combination():
    stmt = make_statement(statement_type="regla", structure="supuesto_consecuencia")
    assert stmt.structure == "supuesto_consecuencia"

def test_statement_exception_structure_requires_exception_present():
    with pytest.raises(ValidationError, match="exige exception.present"):
        make_statement(structure="supuesto_consecuencia_con_excepcion",
                        exception=ExceptionInfo(present=False))

def test_statement_exception_structure_with_exception_present_is_valid():
    stmt = make_statement(
        structure="supuesto_consecuencia_con_excepcion",
        exception=ExceptionInfo(present=True, scope="interna", marker="salvo"),
    )
    assert stmt.exception.present is True

def test_statement_presuncion_without_presumption_block_raises():
    with pytest.raises(ValidationError, match="exige el bloque presumption"):
        make_statement(statement_type="presuncion",
                        structure="supuesto_consecuencia", presumption=None)

def test_statement_non_presuncion_with_presumption_block_raises():
    with pytest.raises(ValidationError, match="solo se admite en"):
        make_statement(statement_type="regla", structure="supuesto_consecuencia",
                        presumption=PresumptionInfo(rebuttable=True))

def test_statement_irrebuttable_presumption_requires_inderogable():
    with pytest.raises(ValidationError, match="derogability debe ser 'inderogable'"):
        make_statement(
            statement_type="presuncion",
            structure="supuesto_consecuencia",
            derogability="derogable_por_pacto",
            presumption=PresumptionInfo(rebuttable=False, burden_shifts_to="ninguno"),
        )

def test_statement_irrebuttable_presumption_with_inderogable_is_valid():
    stmt = make_statement(
        statement_type="presuncion",
        structure="supuesto_consecuencia",
        derogability="inderogable",
        presumption=PresumptionInfo(rebuttable=False, burden_shifts_to="ninguno"),
    )
    assert stmt.presumption.rebuttable is False

def test_statement_articulo_completo_with_span_index_raises():
    with pytest.raises(ValidationError, match="no admite span_index"):
        make_statement(span_type="articulo_completo", span_index=1)

def test_statement_non_articulo_completo_requires_span_index():
    with pytest.raises(ValidationError, match="exige span_index"):
        make_statement(span_type="inciso", span_index=None)

def test_statement_inciso_with_span_index_is_valid():
    stmt = make_statement(span_type="inciso", span_index=1)
    assert stmt.span_index == 1

# ---------------------------------------------------------------------------
# ArticleRecord — field_validator (hash / uid) y model_validator (_consistency)
# ---------------------------------------------------------------------------

def test_article_source_hash_bad_format_raises():
    with pytest.raises(ValidationError, match="source_hash"):
        make_article(source_hash="not-a-real-hash")

def test_article_uid_bad_format_raises():
    with pytest.raises(ValidationError, match="uid esperado"):
        make_article(uid="XX-TEST-2026-BAD-1")

def test_article_uid_valid_format_is_accepted():
    art = make_article(uid="XX-TEST-2026-ART-1")
    assert art.uid == "XX-TEST-2026-ART-1"

def test_article_duplicate_statement_id_raises():
    with pytest.raises(ValidationError, match="statement_id duplicado"):
        make_article(n3_statements=[
            make_statement(statement_id=0),
            make_statement(statement_id=0, span_type="inciso", span_index=1),
        ])

def test_article_single_statement_must_be_articulo_completo():
    with pytest.raises(ValidationError, match="debe usar span_type=articulo_completo"):
        make_article(n3_statements=[make_statement(span_type="inciso", span_index=1)])

def test_article_reflexive_referral_raises():
    with pytest.raises(ValidationError, match="remisión reflexiva"):
        make_article(
            uid="XX-TEST-2026-ART-7",
            n4_referrals=Referrals(outbound=[
                Referral(target_uid="XX-TEST-2026-ART-7", raw_reference="artículo 7",
                          resolution="numeric"),
            ]),
        )

def test_article_non_reflexive_referral_is_valid():
    art = make_article(
        uid="XX-TEST-2026-ART-7",
        n4_referrals=Referrals(outbound=[
            Referral(target_uid="XX-TEST-2026-ART-1", raw_reference="artículo 1",
                      resolution="numeric"),
        ]),
    )
    assert art.n4_referrals.n_resolved == 1

# ---------------------------------------------------------------------------
# StrictModel: validate_assignment=True + extra="forbid" (hardening)
# ---------------------------------------------------------------------------

def test_extra_field_is_forbidden():
    with pytest.raises(ValidationError, match="Extra inputs are not permitted|extra"):
        PathNode(level_type="titulo", depth=0, campo_inventado="x")

def test_validate_assignment_reruns_validator_on_mutation():
    exc = ExceptionInfo(present=True, scope="interna", marker="salvo")
    with pytest.raises(ValidationError):
        exc.scope = None  # present sigue True -> debe re-disparar _coherence

def test_validate_assignment_allows_coherent_mutation():
    tl = TimeLimit()
    tl.has = False  # sigue siendo coherente (has=False, sin values/nature)
    assert tl.has is False
