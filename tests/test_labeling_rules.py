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


def test_sin_marcador_deontico_deontic_y_addressee_quedan_no_determinados():
    """Un texto sin obligación/prohibición/permiso explícitos (p. ej. una
    presunción) no tiene de dónde derivar Von Wright ni un addressee por
    defecto — generality siempre queda fuera del alcance de este motor."""
    p = propose_from_text("Se presume de derecho que el menor de diez años es incapaz.")
    assert set(["deontic_modality", "addressee", "generality"]) <= set(p.undetermined_fields)


def test_detecta_obligacion_von_wright_y_deriva_deber_hohfeld():
    p = propose_from_text("El comprador deberá pagar el precio en el plazo estipulado.")
    assert p.deontic_modality == "obligacion"
    assert p.hohfeldian_position == "deber"
    assert "deontic_modality" in p.determined_fields
    assert "hohfeldian_position" in p.default_fields  # correlato por defecto, no análisis bilateral


def test_detecta_prohibicion_von_wright_y_deriva_deber_hohfeld():
    p = propose_from_text("Se prohíbe la venta de bienes de dominio público.")
    assert p.deontic_modality == "prohibicion"
    assert p.hohfeldian_position == "deber"


def test_detecta_permiso_von_wright_y_deriva_potestad_hohfeld():
    p = propose_from_text(
        "La mujer casada de cualquier edad podrá dedicarse libremente al ejercicio de un empleo."
    )
    assert p.deontic_modality == "permiso"
    assert p.hohfeldian_position == "potestad"


def test_deontica_explicita_sin_otro_marcador_deriva_statement_type_regla_por_defecto():
    p = propose_from_text("Toda persona deberá evitar causar un daño no justificado a otro.")
    assert p.statement_type == "regla"
    assert "statement_type" in p.default_fields  # default modal, no marcador de regla en sí
    assert p.structure == "supuesto_consecuencia"
    assert "structure" in p.default_fields


def test_addressee_juez_detectado_por_marcador():
    p = propose_from_text("El juez podrá reducir la pena cuando concurran atenuantes.")
    assert p.addressee == "juez"
    assert "addressee" in p.determined_fields


def test_addressee_default_partes_cuando_hay_deontica_sin_marcador_explicito():
    p = propose_from_text("El comprador deberá pagar el precio en el plazo estipulado.")
    assert p.addressee == "partes"
    assert "addressee" in p.default_fields


def test_definicion_detectada_por_formula_se_entiende_por():
    p = propose_from_text(
        "Se entiende por contrato de compraventa aquel por el cual una parte se obliga a "
        "transferir la propiedad de una cosa."
    )
    assert p.statement_type == "definicion"
    assert p.structure == "definicion_pura"
    assert p.deontic_modality == "ninguno"
    assert "deontic_modality" not in p.determined_fields
    assert "deontic_modality" not in p.default_fields


def test_proleg_preview_ausente_sin_excepcion():
    p = propose_from_text("El comprador deberá pagar el precio en el plazo estipulado.")
    assert p.proleg_preview is None


def test_proleg_preview_presente_y_demuestra_derrotabilidad_real():
    """Con excepción detectada, el motor PROLEG real corre dos veces sobre
    una regla genérica con esa misma forma: prueba sin la excepción, y se
    derrota cuando la excepción se prueba — el mecanismo real de
    src/reasoning/engine.py, no un mock."""
    p = propose_from_text(
        "El deudor debe restituir la cosa, salvo que haya perecido por caso fortuito."
    )
    assert p.proleg_preview is not None
    assert p.proleg_preview.without_exception.proved is True
    assert p.proleg_preview.with_exception.proved is False


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


def test_hohfeldian_position_propuesto_fluye_real_hasta_validate():
    """hohfeldian_position ya no está hardcodeado a 'ninguno' en el backend
    — lo que el motor de reglas deriva (o lo que un humano complete) se
    respeta de verdad en /v1/statements/validate."""
    text = "El comprador deberá pagar el precio en el plazo estipulado."
    proposal = client.post("/v1/statements/propose", json={"text_span": text}).json()
    assert proposal["hohfeldian_position"] == "deber"

    payload = {
        "text_span": text,
        "statement_type": proposal["statement_type"],
        "structure": proposal["structure"],
        "deontic_modality": proposal["deontic_modality"],
        "hohfeldian_position": proposal["hohfeldian_position"],
        "addressee": proposal["addressee"],
        "antecedent_operator": proposal["antecedent_operator"],
        "exception_present": proposal["exception_present"],
        "generality_n_conditions": 1,
        "generality_has_enumeration": False,
    }
    res = client.post("/v1/statements/validate", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["valid"] is True
    assert body["normalized"]["hohfeldian_position"] == "deber"
