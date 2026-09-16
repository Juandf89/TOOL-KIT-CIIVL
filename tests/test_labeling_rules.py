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


def test_tiene_derecho_a_es_derecho_subjetivo_no_privilegio():
    """"Tiene derecho a" no manda una conducta: afirma una posición jurídica
    cuyo CORRELATIVO es un deber en la otra parte. Eso es un derecho
    subjetivo, no un privilegio (cuyo correlativo es un no-derecho) ni un
    permiso de Von Wright — leerlo como permiso era el mismo error categorial
    que ya se corrigió una vez con permiso/potestad."""
    p = propose_from_text(
        "El arrendatario tiene derecho a la terminación del arrendamiento."
    )
    assert p.hohfeldian_position == "derecho_subjetivo"
    assert p.deontic_modality == "ninguno"


def test_no_tiene_derecho_a_no_afirma_derecho_subjetivo():
    p = propose_from_text(
        "El usufructuario no tiene derecho a pedir cosa alguna por las mejoras."
    )
    assert p.hohfeldian_position != "derecho_subjetivo"


def test_libremente_solo_no_es_permiso():
    """"Siendo capaces de disponer libremente de lo suyo" describe la
    capacidad de las partes, no un permiso que el artículo conceda. Cuando sí
    hay permiso, el "podrá"/"puede" de la misma oración ya lo detecta."""
    p = propose_from_text(
        "Las partes interesadas, siendo capaces de disponer libremente de lo suyo, "
        "consienten en darla por nula."
    )
    assert p.deontic_modality == "ninguno"


def test_nulidad_no_es_prohibicion():
    """La nulidad es una consecuencia sobre el ACTO (su invalidez), no un
    operador deóntico sobre la CONDUCTA de alguien: "es nula la donación
    que…" no le prohíbe nada a nadie, dice qué pasa si se hace."""
    p = propose_from_text(
        "Es nula la donación que comprenda la totalidad de los bienes del donante."
    )
    assert p.deontic_modality == "ninguno"


def test_puede_ser_descriptivo_no_es_permiso():
    """"La aceptación puede ser expresa o tácita" describe las modalidades
    posibles de un acto; no le concede un permiso a nadie."""
    p = propose_from_text("La aceptación puede ser expresa o tácita.")
    assert p.deontic_modality == "ninguno"


# ---------------------------------------------------------------------------
# Negación con pronombre intermedio, formas perifrásticas y "no deber + inf."
# ---------------------------------------------------------------------------

def test_negacion_con_pronombre_intermedio_es_prohibicion():
    """"No SE puede empeñar una cosa" prohíbe. Sin contemplar el pronombre
    entre la negación y el verbo, se leía como permiso."""
    for texto in (
        "No se puede empeñar una cosa, sino por persona que tenga facultad de enajenarla.",
        "Si fueren varios los propietarios, no se podrán imponer servidumbres.",
        "El direito de preferência não se pode ceder nem passa aos herdeiros.",
    ):
        assert propose_from_text(texto).deontic_modality == "prohibicion", texto


def test_ni_puede_es_prohibicion():
    p = propose_from_text("El derecho de recibir alimentos no es renunciable, ni puede ser objeto de transacción.")
    assert p.deontic_modality == "prohibicion"


def test_no_deber_con_infinitivo_es_prohibicion():
    """"no deber" + infinitivo es un deber de no hacer."""
    for texto in (
        "Las molestias por actividades en inmuebles vecinos no deben exceder la normal tolerancia.",
        "No debe efectuarse la restitución al depositante del bien.",
        "Não devem casar os ascendentes com os descendentes.",
    ):
        assert propose_from_text(texto).deontic_modality == "prohibicion", texto


def test_no_deber_sin_infinitivo_dice_que_no_se_adeuda():
    """"No se deben intereses de los intereses" no prohíbe nada: dice que
    nada se adeuda. No es obligación ni prohibición."""
    p = propose_from_text("No se deben intereses de los intereses.")
    assert p.deontic_modality == "ninguno"


def test_no_deber_responder_no_es_prohibicion():
    p = propose_from_text("El dueño no debe responder por el hecho del tercero.")
    assert p.deontic_modality != "prohibicion"


def test_cuantificador_negativo_niega_la_obligacion():
    p = propose_from_text("Nadie está obligado a vender, excepto que se encuentre sometido a una necesidad jurídica.")
    assert p.deontic_modality != "obligacion"


def test_formas_perifrasticas_en_presente_y_futuro():
    """El principio es cubrir cada modo en que el código dispone, no solo
    "debe/deberá": "estará obligado", "es obligado", "queda obligado",
    "será obligatoria", "es lícito", "es permitido", "tendrá derecho a"."""
    casos = {
        "El gestor estará obligado a pagarla, aunque hubiese perdido.": "obligacion",
        "El vendedor será obligado a reembolsar al comprador.": "obligacion",
        "Los usuarios quedan obligados a todos los gastos de cultivo.": "obligacion",
        "La ley será obligatoria desde su publicación.": "obligacion",
        "Es lícito a cualquier persona apropiarse los enjambres.": "permiso",
        "Es permitido estipular interés por el mutuo.": "permiso",
        "No es lícito al propietario hacer cosa alguna que perjudique al usufructuario.": "prohibicion",
    }
    for texto, esperado in casos.items():
        assert propose_from_text(texto).deontic_modality == esperado, texto
    p = propose_from_text("Cada socio tendrá derecho a que la sociedad le reembolse las sumas.")
    assert p.hohfeldian_position == "derecho_subjetivo"
    p = propose_from_text("El fiduciario tiene derecho al reembolso de los gastos.")
    assert p.hohfeldian_position == "derecho_subjetivo"


# ---------------------------------------------------------------------------
# Portugués (Código Civil brasileño)
# ---------------------------------------------------------------------------

def test_portugues_modales_en_todas_sus_formas():
    casos = {
        "O herdeiro pode demandar o reconhecimento de seu direito sucessório.": "permiso",
        "Podem os nubentes requerer prazo razoável para fazer prova contrária.": "permiso",
        "Qualquer dos nubentes poderá acrescer ao seu o sobrenome do outro.": "permiso",
        "Pode-se exigir que cesse a ameaça a direito da personalidade.": "permiso",
        "Também se poderá deixar a fixação do preço à taxa de mercado.": "permiso",
        "É lícito às partes fixar o preço em função de índices.": "permiso",
        "O tabelião deve começar o auto de aprovação imediatamente.": "obligacion",
        "O instrumento do penhor deverá ser levado a registro.": "obligacion",
        "O mutuário é obrigado a restituir ao mutuante o que dele recebeu.": "obligacion",
        "Os contratantes são obrigados a guardar os princípios de probidade.": "obligacion",
        "O devedor não poderá alienar os animais empenhados.": "prohibicion",
        "A coisa consignada não pode ser objeto de penhora.": "prohibicion",
        "Não pode o credor exigir indenização suplementar.": "prohibicion",
        "É vedada contribuição que consista em prestação de serviços.": "prohibicion",
        "Não é lícito encostar à parede divisória chaminés.": "prohibicion",
        "Ninguém pode ser constrangido a submeter-se a tratamento médico.": "prohibicion",
    }
    for texto, esperado in casos.items():
        assert propose_from_text(texto).deontic_modality == esperado, texto


def test_portugues_negacion_no_se_lee_como_obligacion():
    p = propose_from_text("Desembarcadas as mercadorias, o transportador não é obrigado a dar aviso ao destinatário.")
    assert p.deontic_modality == "ninguno"


def test_portugues_pode_ser_descriptivo_no_es_permiso():
    p = propose_from_text("A dispensa da colação pode ser outorgada pelo doador em testamento.")
    assert p.deontic_modality == "ninguno"


def test_portugues_direito_subjetivo_en_presente_y_futuro():
    for texto in (
        "Cada um dos credores solidários tem direito a exigir do devedor o cumprimento.",
        "O possuidor de título ao portador tem direito à prestação nele indicada.",
        "Aquele que restituir a coisa achada terá direito a uma recompensa.",
    ):
        assert propose_from_text(texto).hohfeldian_position == "derecho_subjetivo", texto


def test_portugues_juez_con_permiso_es_potestad():
    p = propose_from_text("Para fiscalização dos atos do tutor, pode o juiz nomear um protutor.")
    assert p.addressee == "juez"
    assert p.hohfeldian_position == "potestad"


def test_portugues_excepcion_y_presuncion():
    p = propose_from_text("O devedor responde pelos prejuízos, salvo se provar caso fortuito.")
    assert p.exception_present is True
    assert p.exception_marker == "salvo se"
    assert p.proleg_preview is not None
    p = propose_from_text("Presumem-se verdadeiras as declarações constantes de documentos assinados.")
    assert p.statement_type == "presuncion"
    assert p.presumption_rebuttable is True


def test_portugues_letra_inicial_tachada_se_une_a_su_palabra():
    """Artefacto de la extracción del Código Civil brasileño: "~~N~~ ão
    pode" es "Não pode". Sin unirlo, la negación no se ve y se lee permiso."""
    p = propose_from_text("§ 1 o ~~N~~ ão pode o devedor obrigar o credor a receber parte.")
    assert p.deontic_modality == "prohibicion"
    p = propose_from_text("§ 1 o ~~S~~ alvo quando exigidos por lei outros requisitos, a escritura é válida.")
    assert p.exception_present is True


def test_portugues_no_contamina_el_castellano():
    """"juez o tribunal" no es el "o tribunal" portugués, y "desde que" en
    castellano es temporal, no condicional."""
    p = propose_from_text("El juez o tribunal resolverá lo que corresponda.")
    assert p.addressee == "juez"
    p = propose_from_text("Los frutos se deben desde que se interpuso la demanda.")
    assert p.antecedent_operator == "ninguno_explicito"


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
