"""test_labeling_rules.py — src/labeling/rules.py y POST /v1/statements/propose.

Motor de reglas léxicas deterministas, sin LLM ni red. Cada caso verifica
tanto lo que las reglas SÍ determinan (con el marcador léxico que lo
justifica) como lo que deliberadamente dejan como no_determinado, para que
esa honestidad no se rompa silenciosamente en un futuro refactor.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api import app
from src.labeling.rules import propose_from_text

client = TestClient(app)


def test_detecta_antecedent_operator_siempre_que():
    p = propose_from_text("Siempre que el comprador pague el precio, el vendedor entrega la cosa.")
    assert p.antecedent_operator == "siempre_que"
    assert "antecedent_operator" in p.determined_fields


def test_ausencia_de_operador_es_ninguno_explicito_no_undetermined():
    p = propose_from_text("El comprador debe pagar el precio en el plazo estipulado.")
    assert p.antecedent_operator == "ninguno_explicito"
    assert "antecedent_operator" in p.determined_fields


def test_detecta_excepcion_interna_sin_referencia_a_otro_articulo():
    p = propose_from_text(
        "El deudor debe restituir la cosa, salvo que haya perecido por caso fortuito."
    )
    assert p.exception_present is True
    assert p.exception_marker == "salvo que"
    assert p.exception_scope == "interna"


def test_detecta_excepcion_por_remision_con_referencia_numerica():
    p = propose_from_text(
        "El plazo corre desde la notificación, salvo lo dispuesto en el artículo 45."
    )
    assert p.exception_present is True
    assert p.exception_scope == "por_remision"


def test_sin_marcador_de_excepcion_exception_present_false():
    p = propose_from_text("El comprador debe pagar el precio en el plazo estipulado.")
    assert p.exception_present is False
    assert p.exception_marker is None
    assert p.exception_scope is None


def test_presuncion_de_derecho_detecta_irrebuttable():
    p = propose_from_text("Se presume de derecho que el menor de diez años es incapaz.")
    assert p.statement_type == "presuncion"
    assert p.presumption_rebuttable is False
    assert p.structure == "supuesto_consecuencia"  # único candidato sin excepción


def test_presuncion_legal_detecta_rebuttable():
    p = propose_from_text("Se presume la buena fe del poseedor.")
    assert p.statement_type == "presuncion"
    assert p.presumption_rebuttable is True


def test_remision_corta_al_inicio_es_detectada():
    p = propose_from_text("Lo dispuesto en el artículo 120 se aplica a este contrato.")
    assert p.statement_type == "remision"
    assert p.structure == "remision_pura"


def test_texto_largo_sin_marcadores_deja_statement_type_no_determinado():
    p = propose_from_text(
        "El comprador debe pagar el precio en el plazo y lugar estipulados en el contrato, "
        "salvo pacto expreso en contrario de las partes celebrantes del negocio jurídico."
    )
    assert p.statement_type is None
    assert "statement_type" in p.undetermined_fields
    assert "structure" in p.undetermined_fields  # depende de statement_type


def test_deontic_addressee_generality_siempre_no_determinados_en_paso_1():
    p = propose_from_text("Se presume de derecho que el menor de diez años es incapaz.")
    assert set(["deontic_modality", "addressee", "generality"]) <= set(p.undetermined_fields)


def test_endpoint_propose_devuelve_shape_esperado():
    res = client.post(
        "/v1/statements/propose",
        json={"text_span": "Se presume de derecho que el menor de diez años es incapaz."},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["statement_type"] == "presuncion"
    assert body["presumption_rebuttable"] is False
    assert body["annotated_by"] == "heuristica_local"


def test_propuesta_de_reglas_pasa_validacion_real_end_to_end():
    """El flujo completo: proponer -> completar los campos que las reglas
    dejaron sin determinar -> validar contra el esquema real."""
    proposal = client.post(
        "/v1/statements/propose",
        json={"text_span": "Se presume de derecho que el menor de diez años es incapaz."},
    ).json()

    payload = {
        "text_span": "Se presume de derecho que el menor de diez años es incapaz.",
        "statement_type": proposal["statement_type"],
        "structure": proposal["structure"],
        "antecedent_operator": proposal["antecedent_operator"],
        "exception_present": proposal["exception_present"],
        "presumption_rebuttable": proposal["presumption_rebuttable"],
        # completados a mano, fuera del alcance de las reglas (Paso 1):
        "deontic_modality": "ninguno",
        "addressee": "juez",
        "generality_n_conditions": 1,
        "generality_has_enumeration": False,
    }
    res = client.post("/v1/statements/validate", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["valid"] is True
    assert body["normalized"]["annotated_by"] == "heuristica_local"
    assert body["normalized"]["derogability"] == "inderogable"
