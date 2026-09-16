"""test_labeling_rules.py — src/labeling/rules.py y POST /v1/statements/propose.

Motor de reglas léxicas deterministas, sin LLM ni red, para la
determinación deóntica (Von Wright) y la posición hohfeldiana por defecto.
Cada caso verifica tanto lo que las reglas SÍ determinan (con el marcador
léxico que lo justifica) como lo que deliberadamente dejan sin determinar
(None/"ninguno"), para que esa honestidad no se rompa silenciosamente en un
futuro refactor.
"""

from __future__ import annotations

import unicodedata

from fastapi.testclient import TestClient

from src.api import app
from src.labeling.rules import propose_from_text

client = TestClient(app)


def test_detecta_antecedent_operator_siempre_que():
    p = propose_from_text("Siempre que el comprador pague el precio, el vendedor entrega la cosa.")
    assert p.antecedent_operator == "siempre_que"


def test_ausencia_de_operador_es_ninguno_explicito():
    p = propose_from_text("El comprador debe pagar el precio en el plazo estipulado.")
    assert p.antecedent_operator == "ninguno_explicito"


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
    # El texto no debe traer NINGÚN marcador deóntico: ni futuro ("deberá")
    # ni presente ("debe"). Antes decía "el comprador debe pagar el precio",
    # que solo pasaba por el hueco de que el presente de indicativo no se
    # detectaba; al cerrarlo, ese texto sí tiene obligación y el caso dejaba
    # de probar lo que dice su nombre.
    p = propose_from_text(
        "El precio se entrega en el plazo y lugar estipulados en el contrato, "
        "salvo pacto expreso en contrario de las partes celebrantes del negocio jurídico."
    )
    assert p.statement_type is None
    assert p.structure is None  # depende de statement_type


def test_sin_marcador_deontico_deontic_y_addressee_quedan_no_determinados():
    """Un texto sin obligación/prohibición/permiso explícitos (p. ej. una
    presunción) no tiene de dónde derivar Von Wright ni un addressee por
    defecto."""
    p = propose_from_text("Se presume de derecho que el menor de diez años es incapaz.")
    assert p.deontic_modality == "ninguno"
    assert p.addressee is None


def test_detecta_obligacion_von_wright_y_deriva_deber_hohfeld():
    p = propose_from_text("El comprador deberá pagar el precio en el plazo estipulado.")
    assert p.deontic_modality == "obligacion"
    assert p.hohfeldian_position == "deber"  # correlato por defecto, no análisis bilateral


def test_detecta_prohibicion_von_wright_y_deriva_deber_hohfeld():
    p = propose_from_text("Se prohíbe la venta de bienes de dominio público.")
    assert p.deontic_modality == "prohibicion"
    assert p.hohfeldian_position == "deber"


def test_detecta_presente_de_indicativo_no_solo_futuro():
    """Los códigos no redactan solo en futuro. El de Vélez (1869) y buena
    parte del peruano y el brasileño usan presente de indicativo, y tratarlo
    como "sin modalidad" dejaba miles de artículos sin su deóntica real."""
    assert propose_from_text(
        "El legado en dinero debe ser pagado en esta especie."
    ).deontic_modality == "obligacion"
    assert propose_from_text(
        "El locatario puede subarrendar en todo o en parte la cosa arrendada."
    ).deontic_modality == "permiso"
    assert propose_from_text(
        "El plazo del arrendamiento no puede exceder de diez años."
    ).deontic_modality == "prohibicion"


def test_la_negacion_no_se_lee_como_la_modalidad_afirmativa():
    """El error más caro de un detector léxico es invertir el signo: leer
    "no está obligado a" como una obligación. Preferimos "ninguno" antes que
    una modalidad invertida — afirmar que la ausencia de deber es un
    privilegio hohfeldiano exigiría identificar la contraparte, que es
    justamente lo que este motor no hace (docs/limitaciones_conocidas.md §2)."""
    p = propose_from_text(
        "El apoderado no está obligado a rendir cuentas de los frutos percibidos."
    )
    assert p.deontic_modality == "ninguno"

    p = propose_from_text(
        "El usufructuario no tiene derecho a pedir cosa alguna por las mejoras."
    )
    assert p.deontic_modality == "ninguno"


def test_cuantificador_negativo_es_prohibicion_aunque_el_verbo_sea_afirmativo():
    """"Nadie puede construir…" prohíbe, aunque "puede" esté en afirmativo:
    la negación la aporta el cuantificador, no el verbo."""
    assert propose_from_text(
        "Nadie puede construir cerca de una pared ajena hornos ni chimeneas."
    ).deontic_modality == "prohibicion"
    assert propose_from_text(
        "Ninguno de los comuneros podrá inquietar a los otros en sus porciones."
    ).deontic_modality == "prohibicion"


def test_puede_ser_descriptivo_no_es_permiso():
    """"La aceptación puede ser expresa o tácita" describe las modalidades
    posibles de un acto; no le concede un permiso a nadie."""
    p = propose_from_text("La aceptación puede ser expresa o tácita.")
    assert p.deontic_modality == "ninguno"


def test_detecta_permiso_dirigido_a_partes_deriva_privilegio_no_potestad():
    """"Permiso" a un particular es una LIBERTAD/PRIVILEGIO hohfeldiana (no
    altera la posición jurídica de nadie más), distinta de una POTESTAD
    (capacidad de alterar relaciones jurídicas ajenas) — confundirlas es un
    error categorial, no una simplificación válida. Ver
    _derive_hohfeld_from_deontic en src/labeling/rules.py."""
    p = propose_from_text(
        "La mujer casada de cualquier edad podrá dedicarse libremente al ejercicio de un empleo."
    )
    assert p.deontic_modality == "permiso"
    assert p.hohfeldian_position == "privilegio"


def test_detecta_permiso_dirigido_a_juez_deriva_potestad():
    """"Permiso" dirigido a un juez/funcionario SÍ es una potestad: implica
    la capacidad de alterar la posición jurídica de otra persona (aquí,
    reducir la pena de alguien más) por un acto de voluntad calificado."""
    p = propose_from_text("El juez podrá reducir la pena cuando concurran atenuantes.")
    assert p.deontic_modality == "permiso"
    assert p.addressee == "juez"
    assert p.hohfeldian_position == "potestad"


def test_deontica_explicita_sin_otro_marcador_deriva_statement_type_regla_por_defecto():
    p = propose_from_text("Toda persona deberá evitar causar un daño no justificado a otro.")
    assert p.statement_type == "regla"  # default modal, no marcador de regla en sí
    assert p.structure == "supuesto_consecuencia"


def test_addressee_juez_detectado_por_marcador():
    p = propose_from_text("El juez podrá reducir la pena cuando concurran atenuantes.")
    assert p.addressee == "juez"


def test_addressee_default_partes_cuando_hay_deontica_sin_marcador_explicito():
    p = propose_from_text("El comprador deberá pagar el precio en el plazo estipulado.")
    assert p.addressee == "partes"


def test_definicion_detectada_por_formula_se_entiende_por():
    p = propose_from_text(
        "Se entiende por contrato de compraventa aquel por el cual una parte se obliga a "
        "transferir la propiedad de una cosa."
    )
    assert p.statement_type == "definicion"
    assert p.structure == "definicion_pura"
    assert p.deontic_modality == "ninguno"


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


def test_hohfeldian_position_propuesto_es_el_correlato_por_defecto():
    """hohfeldian_position lo deriva el motor de reglas de verdad (no
    hardcodeado a 'ninguno') a partir de la deóntica detectada."""
    text = "El comprador deberá pagar el precio en el plazo estipulado."
    proposal = client.post("/v1/statements/propose", json={"text_span": text}).json()
    assert proposal["hohfeldian_position"] == "deber"


def test_nfc_y_nfd_dan_el_mismo_resultado():
    """Regresión: el mismo texto en dos formas Unicode canónicamente
    equivalentes (NFC vs. NFD — común en texto pegado desde macOS o
    extraído de OCR/PDF) debe dar el MISMO resultado. Antes de normalizar
    a NFC en propose_from_text(), NFD rompía los patrones léxicos con
    tildes precompuestas y producía un resultado distinto para el mismo
    enunciado — contradecía la promesa de determinismo del motor."""
    text_nfc = unicodedata.normalize(
        "NFC", "Se prohíbe la venta de bienes de dominio público."
    )
    text_nfd = unicodedata.normalize("NFD", text_nfc)
    assert text_nfc != text_nfd  # confirma que de verdad son representaciones distintas

    p_nfc = propose_from_text(text_nfc)
    p_nfd = propose_from_text(text_nfd)
    assert p_nfc.deontic_modality == p_nfd.deontic_modality == "prohibicion"
    assert p_nfc.hohfeldian_position == p_nfd.hohfeldian_position == "deber"
    assert p_nfc.notes == p_nfd.notes


def test_propose_rechaza_texto_vacio():
    res = client.post("/v1/statements/propose", json={"text_span": ""})
    assert res.status_code == 422


def test_propose_rechaza_texto_mayor_a_4000_caracteres():
    res = client.post("/v1/statements/propose", json={"text_span": "a" * 4001})
    assert res.status_code == 422


def test_proleg_preview_nota_distingue_presuncion_de_excepcion_sustantiva():
    """Una presunción y una regla con excepción sustantiva no son la misma
    figura jurídica (desplazamiento de carga probatoria vs. derrota de la
    regla) aunque el motor las calcule con el mismo mecanismo — la nota
    visible tiene que decir cuál de las dos está mostrando."""
    p_presuncion = propose_from_text(
        "Se presume de derecho que el menor de diez años es incapaz, "
        "salvo lo dispuesto en el artículo 45."
    )
    assert p_presuncion.statement_type == "presuncion"
    note_presuncion = p_presuncion.proleg_preview.note.lower()
    assert "prueba en contrario" in note_presuncion
    assert "carga de la prueba" in note_presuncion

    p_regla = propose_from_text(
        "El deudor deberá restituir la cosa, salvo que haya perecido por caso fortuito."
    )
    assert p_regla.statement_type == "regla"
    note_regla = p_regla.proleg_preview.note.lower()
    assert "prueba en contrario" not in note_regla
    assert "excepción sustantiva" in note_regla
