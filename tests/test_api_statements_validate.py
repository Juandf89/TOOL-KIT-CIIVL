"""test_api_statements_validate.py — POST /v1/statements/validate.

Este endpoint es el punto único de verdad para saber si un etiquetado N3
propuesto —por reglas deterministas locales (src/labeling/rules.py, ver
POST /v1/statements/propose) o por un humano— es jurídicamente válido según
el esquema real (src/models.py). No reimplementa esas reglas: construye un
NormativeStatement real y deja que Pydantic decida.

Los casos de esta suite corresponden a los verificados a mano contra la API
real durante el desarrollo: regla simple válida, structure-con-excepción
sin exception.present=True (debe rechazar), y presunción de derecho /
irrebuttable (deriva derogability=inderogable automáticamente).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from src.api import app

client = TestClient(app)


def test_valid_simple_rule_is_accepted():
    payload = {
        "text_span": "El comprador debe pagar el precio en el plazo estipulado.",
        "statement_type": "regla",
        "structure": "supuesto_consecuencia",
        "deontic_modality": "obligacion",
        "addressee": "partes",
        "antecedent_operator": "ninguno_explicito",
        "exception_present": False,
        "generality_n_conditions": 1,
        "generality_has_enumeration": False,
    }
    res = client.post("/v1/statements/validate", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["valid"] is True
    assert body["error"] is None
    assert body["normalized"]["statement_type"] == "regla"
    assert body["normalized"]["hohfeldian_position"] == "ninguno"  # nunca se pide como input
    assert body["normalized"]["derogability"] == "indeterminada"  # default seguro, no inferido
    assert body["normalized"]["annotated_by"] == "heuristica_local"  # default del endpoint
    assert body["normalized"]["verified"] is False
    assert body["computed"]["generality_level"] in ("casuistica", "intermedia", "clausula_general")


def test_structure_con_excepcion_sin_exception_present_es_rechazado():
    """Reproduce el mismo caso verificado a mano: el esquema real rechaza
    la combinación ilegal con el mensaje exacto del validator de
    NormativeStatement, no un error genérico."""
    payload = {
        "text_span": "Texto de prueba.",
        "statement_type": "regla",
        "structure": "supuesto_consecuencia_con_excepcion",
        "deontic_modality": "obligacion",
        "addressee": "partes",
        "antecedent_operator": "si",
        "exception_present": False,
        "generality_n_conditions": 1,
        "generality_has_enumeration": False,
    }
    res = client.post("/v1/statements/validate", json=payload)
    assert res.status_code == 200  # el rechazo es un resultado válido del endpoint, no un error HTTP
    body = res.json()
    assert body["valid"] is False
    assert body["normalized"] is None
    assert "exception.present=True" in body["error"]


def test_presuncion_de_derecho_deriva_derogability_inderogable():
    payload = {
        "text_span": "Se presume de derecho que el menor de diez años es incapaz.",
        "statement_type": "presuncion",
        "structure": "supuesto_consecuencia",
        "deontic_modality": "ninguno",
        "addressee": "juez",
        "antecedent_operator": "ninguno_explicito",
        "exception_present": False,
        "generality_n_conditions": 1,
        "generality_has_enumeration": False,
        "presumption_rebuttable": False,
    }
    res = client.post("/v1/statements/validate", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["valid"] is True
    assert body["normalized"]["derogability"] == "inderogable"
    assert body["normalized"]["presumption"] == {
        "rebuttable": False,
        "burden_shifts_to": "ninguno",
        "marker": None,
    }


def test_presuncion_rebuttable_por_defecto_si_no_se_especifica():
    payload = {
        "text_span": "Se presume la buena fe.",
        "statement_type": "presuncion",
        "structure": "supuesto_consecuencia",
        "deontic_modality": "ninguno",
        "addressee": "partes",
        "antecedent_operator": "ninguno_explicito",
        "exception_present": False,
        "generality_n_conditions": 1,
        "generality_has_enumeration": False,
    }
    res = client.post("/v1/statements/validate", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["valid"] is True
    assert body["normalized"]["presumption"]["rebuttable"] is True
    assert body["normalized"]["derogability"] == "indeterminada"


def test_exception_scope_invalido_es_rechazado_por_el_esquema_real():
    """El prompt del cliente restringe scope a interna|por_remision
    ('implicita' existe en el Literal real de ExceptionScope pero se
    excluye a propósito del prompt por ser juicio sistémico, no textual —
    ver revisión de ontología). El endpoint igual no confía ciegamente en
    lo que mande el cliente: cualquier valor fuera del Literal real de
    ExceptionInfo.scope se rechaza."""
    payload = {
        "text_span": "Texto con excepción.",
        "statement_type": "regla",
        "structure": "supuesto_consecuencia_con_excepcion",
        "deontic_modality": "obligacion",
        "addressee": "partes",
        "antecedent_operator": "si",
        "exception_present": True,
        "exception_marker": "salvo que",
        "exception_scope": "un_valor_que_no_existe_en_el_esquema",
        "generality_n_conditions": 1,
        "generality_has_enumeration": False,
    }
    res = client.post("/v1/statements/validate", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["valid"] is False
