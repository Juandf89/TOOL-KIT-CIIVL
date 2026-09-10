"""Tests del adaptador ArticleRecord -> dict plano en src/behavior.py
(article_to_profile) y de que profile_of()/FEATURES sigan funcionando
correctamente sobre la salida de ese adaptador (C-5 del debate de revisión:
behavior.py usaba claves inventadas que no existen en src/models.py)."""

from __future__ import annotations

from src.behavior import FEATURES, article_to_profile, profile_of
from src.models import ExceptionInfo, GeneralityProxies, PresumptionInfo, TimeLimit
from tests.factories import make_article, make_statement


def test_adapter_maps_definitional_article():
    stmt = make_statement(
        statement_type="definicion",
        structure="definicion_pura",
        deontic_modality="ninguno",
        addressee="partes",
        antecedent_operator="ninguno_explicito",
        generality=GeneralityProxies(n_conditions=0, has_enumeration=False,
                                      indeterminate_concepts=["buena fe"]),
    )
    article = make_article(n3_statements=[stmt])
    profile = article_to_profile(article)

    assert profile["is_definitional"] is True
    assert profile["P6_deontic"] == []
    assert profile["P5_addressee"] == ["partes"]
    assert profile["P3_exception"] is False
    assert profile["P2_indeterminate"] == ["buena fe"]
    assert profile["has_time_limit"] is False
    assert profile["is_presumption"] is False
    assert profile["antecedent"] == []


def test_adapter_maps_obligacion_con_excepcion_plazo_y_presuncion():
    stmt = make_statement(
        statement_type="presuncion",
        structure="supuesto_consecuencia_con_excepcion",
        deontic_modality="obligacion",
        addressee="juez",
        antecedent_operator="si",
        exception=ExceptionInfo(present=True, marker="salvo", scope="interna"),
        presumption=PresumptionInfo(rebuttable=True, burden_shifts_to="partes"),
        time_limit=TimeLimit(has=True, values=[(30, "dias")], nature="plazo_de_ejercicio"),
    )
    article = make_article(n3_statements=[stmt])
    profile = article_to_profile(article)

    assert profile["is_definitional"] is False
    assert profile["P6_deontic"] == ["obligacion"]
    assert profile["P5_addressee"] == ["juez"]
    assert profile["P3_exception"] is True
    assert profile["has_time_limit"] is True
    assert profile["is_presumption"] is True
    assert profile["antecedent"] == ["si"]


def test_adapter_excludes_ninguno_deontic_and_ninguno_explicito_antecedent():
    stmt = make_statement(deontic_modality="ninguno", antecedent_operator="ninguno_explicito")
    article = make_article(n3_statements=[stmt])
    profile = article_to_profile(article)

    assert profile["P6_deontic"] == []
    assert profile["antecedent"] == []


def test_profile_of_and_features_consume_adapter_output():
    stmt = make_statement(
        statement_type="presuncion",
        structure="supuesto_consecuencia_con_excepcion",
        deontic_modality="prohibicion",
        addressee="funcionario_o_notario",
        exception=ExceptionInfo(present=True, marker="salvo", scope="interna"),
        presumption=PresumptionInfo(rebuttable=True, burden_shifts_to="tercero"),
    )
    article = make_article(n3_statements=[stmt])
    profile = article_to_profile(article)

    tag = profile_of(profile)
    assert tag[1] == "PRO"   # prohibición
    assert tag[3] == "EXC"   # excepción
    assert tag[6] == "PRE"   # presunción

    assert FEATURES["prohibición"](profile) is True
    assert FEATURES["obligación"](profile) is False
    assert FEATURES["notario"](profile) is True
    assert FEATURES["excepción"](profile) is True
    assert FEATURES["presunción"](profile) is True
