"""rules.py — motor de reglas deterministas para la determinación deóntica
(Von Wright) y la posición hohfeldiana por defecto.

Distingue dos niveles de confianza, documentados en `notes` cuando aplica:

  * marcador léxico de baja ambigüedad medido o evidenciado dentro del
    propio proyecto — antecedent_operator, exception,
    presuncion/remision/definicion, deóntica de Von Wright.
  * sin marcador textual, pero con un valor modal razonable y documentado
    en `notes` — p. ej. addressee="partes" para una regla con deóntica
    explícita (la mayoría del derecho privado se dirige a las partes salvo
    marca en contrario), o el correlato hohfeldiano por defecto de la
    deóntica detectada (ver `_derive_hohfeld_from_deontic`: es una
    simplificación declarada, NO un análisis bilateral completo de
    Hohfeld, que exigiría identificar a la contraparte concreta).

Cuando no hay evidencia suficiente, el campo queda en None (o su valor
"ninguno"/"ninguno_explicito"), nunca adivinado. No usa red, no usa LLM, no
tiene costo.
"""

from __future__ import annotations

import re
import unicodedata

from src.labeling import lexical_markers as lex
from src.labeling.schemas import LabelProposal, ProlegPreview, ProlegRunResult
from src.models import COMPATIBILITY
from src.reasoning.engine import prove
from src.reasoning.models import FactAction, FactBase, FactEntry, Party, Rule, RuleBase, ExceptionLink


# Artefacto de la extracción del Código Civil brasileño (152 artículos): la
# letra inicial de un párrafo quedó tachada y separada del resto de la
# palabra — "~~N~~ ão pode", "~~S~~ alvo quando". Sin volver a unirla, el
# motor no ve la negación ni la excepción, y "Não pode o devedor…" se leía
# como un permiso. Solo se une cuando lo que sigue es una letra, es decir,
# cuando es claramente la misma palabra.
_LETRA_INICIAL_TACHADA = re.compile(r"~~([^\W\d_])~~\s+(?=[^\W\d_])")


def _detect_antecedent_operator(text: str) -> str:
    for label, pattern in lex.ANTECEDENT_PATTERNS:
        if pattern.search(text):
            return label
    return "ninguno_explicito"


def _detect_exception(text: str) -> tuple[bool, str | None, str | None]:
    for marker_label, pattern in lex.EXCEPTION_PATTERNS:
        match = pattern.search(text)
        if match:
            tail = text[match.start() : match.start() + 300]
            scope = "por_remision" if lex.ARTICLE_REFERENCE_RE.search(tail) else "interna"
            return True, marker_label, scope
    return False, None, None


def _detect_presumption(text: str) -> tuple[bool, bool | None]:
    if lex.PRESUMPTION_DE_DERECHO_RE.search(text):
        return True, False
    if lex.PRESUMPTION_LEGAL_RE.search(text):
        return True, True
    return False, None


def _detect_remision(text: str) -> bool:
    n_words = len(text.split())
    return n_words <= lex.REMISION_MAX_WORDS and bool(lex.REMISION_LEAD_RE.search(text))


def _detect_definicion(text: str) -> bool:
    return bool(lex.DEFINICION_LEAD_RE.search(text))


def _detect_deontic_modality(text: str) -> str | None:
    """Von Wright: obligación / prohibición / permiso. Orden importa —
    prohibición antes que permiso ("no podrá" no debe matchear "podrá")."""
    if lex.DEONTIC_PROHIBICION_RE.search(text):
        return "prohibicion"
    if lex.DEONTIC_OBLIGACION_RE.search(text):
        return "obligacion"
    if lex.DEONTIC_PERMISO_RE.search(text):
        return "permiso"
    return None


def _derive_hohfeld_from_deontic(deontic_modality: str | None, addressee: str | None) -> str:
    """Correlato hohfeldiano por defecto de la modalidad deóntica detectada.

    Simplificación declarada: Hohfeld exige identificar a la CONTRAPARTE
    concreta (quien tiene el deber correlativo del derecho, o quien está
    sujeto al ejercicio de la potestad) — algo que un texto
    normativo aislado no siempre da. Esta derivación asigna la posición del
    DESTINATARIO del mandato (no de su contraparte), que es lo único que el
    propio enunciado permite fijar sin inventar quién más interviene:
    obligación/prohibición -> deber (el destinatario debe/no debe actuar).

    "permiso" se bifurca porque colapsa dos casillas hohfeldianas DISTINTAS
    (no una simplificación de una sola): una LIBERTAD/PRIVILEGIO (facultad
    de actuar sin alterar la posición jurídica de nadie más — "podrá
    dedicarse libremente a un empleo") no es lo mismo que una POTESTAD
    (capacidad de alterar unilateralmente relaciones jurídicas ajenas — "el
    juez podrá reducir la pena"). Se usa el destinatario ya detectado para
    distinguirlas: permiso dirigido a juez/funcionario -> potestad (altera
    la posición de otro); permiso dirigido a partes/tercero/sin marcador ->
    privilegio (libertad civil ordinaria, el caso mayoritario).
    Ver docs/limitaciones_conocidas.md §2 para el límite de fondo (falta de
    correlatividad bilateral, un problema distinto y adicional a este)."""
    if deontic_modality in ("obligacion", "prohibicion"):
        return "deber"
    if deontic_modality == "permiso":
        if addressee in ("juez", "funcionario_o_notario"):
            return "potestad"
        return "privilegio"
    return "ninguno"


def _detect_addressee(text: str) -> str | None:
    if lex.ADDRESSEE_JUEZ_RE.search(text):
        return "juez"
    if lex.ADDRESSEE_FUNCIONARIO_RE.search(text):
        return "funcionario_o_notario"
    if lex.ADDRESSEE_TERCERO_RE.search(text):
        return "tercero"
    return None


def _detect_enumeration(text: str) -> tuple[bool, bool | None]:
    if not lex.ENUMERATION_ITEM_RE.search(text):
        return False, None
    if lex.ENUMERATION_CLOSED_RE.search(text):
        return True, True
    if lex.ENUMERATION_OPEN_RE.search(text):
        return True, False
    return True, None  # hay lista, pero abierta/cerrada queda sin determinar


def _derive_structure(
    statement_type: str | None, exception_present: bool, has_enumeration: bool
) -> str | None:
    """Usa COMPATIBILITY para derivar structure solo cuando queda un único
    candidato posible — nunca elige entre varios igual de válidos."""
    if statement_type is None:
        return None
    candidates = COMPATIBILITY.get(statement_type, set())
    if not candidates:
        return None
    if exception_present:
        if "supuesto_consecuencia_con_excepcion" in candidates:
            return "supuesto_consecuencia_con_excepcion"
        return None
    remaining = candidates - {"supuesto_consecuencia_con_excepcion"}
    if not has_enumeration:
        remaining = remaining - {"enumeracion_taxativa", "enumeracion_enunciativa"}
    if len(remaining) == 1:
        return next(iter(remaining))
    return None


def build_proleg_preview(
    exception_marker: str | None, exception_scope: str | None, statement_type: str | None = None
) -> ProlegPreview:
    """Instancia una RuleBase mínima y GENÉRICA a partir de la MISMA
    estructura ya detectada (regla + excepción) y corre el motor PROLEG
    real dos veces: una sin la excepción probada, otra con ella. No fabrica
    contenido semántico del artículo — los nombres de hecho
    ("antecedente_cumplido", "excepcion_probada") son genéricos a
    propósito, para no simular una prueba jurídica que el texto por sí solo
    no permite construir. Lo que demuestra es la MECÁNICA de
    derrotabilidad, con el motor real, no un mock.

    `statement_type` cambia el TEXTO de la nota, no el cálculo: en una
    presunción, la "excepción" que el motor modela es en realidad la
    prueba en contrario, que opera por desplazamiento de la CARGA
    PROBATORIA (quien quiere desvirtuar la presunción debe probarlo) — una
    figura procesal distinta de la excepción sustantiva ordinaria de una
    regla (un hecho impeditivo que, probado, derrota la consecuencia). El
    motor PROLEG usa el mismo mecanismo de regla+excepción para ambas
    porque estructuralmente se comportan igual (algo se prueba salvo que
    se pruebe lo contrario), pero la nota debe decir cuál de las dos
    figuras jurídicas está mostrando, para no presentarlas como si fueran
    la misma cosa."""
    rulebase = RuleBase(
        id="preview_derrotabilidad",
        description=(
            f"Estructura genérica derivada del artículo: regla con excepción "
            f'("{exception_marker}", scope={exception_scope}).'
        ),
        rules=[
            Rule(
                head="consecuencia_aplica",
                body=["antecedente_cumplido"],
                source_note="Regla base detectada por reglas léxicas (no contenido inventado).",
            )
        ],
        exceptions=[ExceptionLink(rule_head="consecuencia_aplica", exception_head="excepcion_probada")],
    )

    base_facts = FactBase(
        entries=[
            FactEntry(action=FactAction.ALLEGE, fact="antecedente_cumplido", party=Party.PLAINTIFF),
            FactEntry(action=FactAction.PROVIDE_EVIDENCE, fact="antecedente_cumplido", party=Party.PLAINTIFF),
            FactEntry(action=FactAction.PLAUSIBLE, fact="antecedente_cumplido", party=None),
        ]
    )

    without_exception = prove("consecuencia_aplica", Party.PLAINTIFF, rulebase, base_facts)

    with_exception_facts = FactBase(
        entries=list(base_facts.entries)
        + [FactEntry(action=FactAction.PLAUSIBLE, fact="excepcion_probada", party=None)]
    )
    with_exception = prove("consecuencia_aplica", Party.PLAINTIFF, rulebase, with_exception_facts)

    if statement_type == "presuncion":
        note = (
            "Vista previa estructural: usa el motor de razonamiento real "
            "sobre una regla genérica con la misma forma detectada en el "
            "artículo. En una presunción, esto modela la PRUEBA EN "
            "CONTRARIO (desplazamiento de la carga de la prueba hacia "
            "quien quiere desvirtuarla), no la derrota de una regla "
            "sustantiva — son figuras procesales distintas aunque el "
            "motor las calcule con el mismo mecanismo. No es un análisis "
            "semántico del contenido específico del artículo."
        )
    else:
        note = (
            "Vista previa estructural: usa el motor de razonamiento real "
            "sobre una regla genérica con la misma forma detectada en el "
            "artículo (regla + excepción sustantiva). No es un análisis "
            "semántico del contenido específico del artículo — muestra "
            "que la excepción detectada, si se prueba, efectivamente "
            "derrota la regla bajo el motor determinista."
        )

    return ProlegPreview(
        rulebase_id=rulebase.id,
        without_exception=ProlegRunResult(
            proved=without_exception.proved,
            trace_length=len(without_exception.trace),
        ),
        with_exception=ProlegRunResult(
            proved=with_exception.proved,
            trace_length=len(with_exception.trace),
        ),
        note=note,
    )


def propose_from_text(text: str) -> LabelProposal:
    # NFC: sin esto, el mismo texto en dos formas Unicode canónicamente
    # equivalentes (p. ej. copiado desde macOS o extraído de OCR, que suelen
    # producir NFD) puede no matchear los patrones léxicos (que usan tildes
    # precompuestas) y dar un resultado distinto para el mismo enunciado —
    # rompería la promesa de determinismo de este motor. El pipeline de
    # ingesta (src/pipeline.py) ya normaliza a NFC los 8 corpus reales; esto
    # cubre el otro punto de entrada: texto pegado directo por un usuario.
    text = unicodedata.normalize("NFC", text).strip()
    text = _LETRA_INICIAL_TACHADA.sub(r"\1", text)

    notes: list[str] = []

    antecedent_operator = _detect_antecedent_operator(text)

    exception_present, exception_marker, exception_scope = _detect_exception(text)

    deontic_modality = _detect_deontic_modality(text)
    deontic_determined = deontic_modality is not None
    if not deontic_determined:
        deontic_modality = "ninguno"
        notes.append(
            "Deóntica (Von Wright): sin marcador léxico de obligación/"
            "prohibición/permiso — se deja 'ninguno' por defecto (correcto "
            "para definiciones/remisiones, pero revisar si es una regla "
            "con deóntica implícita en presente indicativo, ej. 'el "
            "comprador paga el precio' sin 'deberá')."
        )

    # addressee se detecta ACÁ (antes de derivar Hohfeld) porque
    # _derive_hohfeld_from_deontic necesita saber si el "permiso" se
    # dirige a un juez/funcionario (potestad) o a partes/tercero
    # (privilegio) — ver docstring de esa función.
    addressee = _detect_addressee(text)
    if addressee is None and deontic_modality != "ninguno":
        addressee = "partes"
        notes.append(
            "Destinatario: sin marcador de juez/funcionario/tercero — se "
            "asume 'partes' por defecto (mayoría del derecho privado); "
            "revisar si el artículo se dirige a otro destinatario."
        )

    # "tiene derecho a" fija Hohfeld POR SÍ MISMO, sin pasar por Von Wright:
    # no manda una conducta, afirma una posición jurídica cuyo correlativo es
    # un deber en la otra parte. Se chequea antes que la derivación desde la
    # deóntica porque es evidencia más directa que un correlato por defecto.
    if lex.DERECHO_SUBJETIVO_RE.search(text):
        hohfeldian_position = "derecho_subjetivo"
        notes.append(
            "Posición (Hohfeld): el texto dice 'tiene derecho a', que afirma "
            "un derecho subjetivo — su correlativo es un deber en la otra "
            "parte, no la mera libertad de un privilegio. No se deriva de la "
            "deóntica; se lee directo del enunciado."
        )
    else:
        hohfeldian_position = _derive_hohfeld_from_deontic(
            deontic_modality if deontic_determined else None,
            addressee,
        )
        if deontic_determined:
            notes.append(
                "Posición (Hohfeld): correlato por defecto de la deóntica "
                "detectada (y, si es 'permiso', del destinatario) — no un "
                "análisis bilateral de Hohfeld (no identifica contraparte) — "
                "ver docs/limitaciones_conocidas.md §2."
            )

    statement_type: str | None = None
    presumption_rebuttable: bool | None = None

    is_presumption, rebuttable = _detect_presumption(text)
    if is_presumption:
        statement_type = "presuncion"
        presumption_rebuttable = rebuttable
    elif _detect_remision(text):
        statement_type = "remision"
    elif _detect_definicion(text):
        statement_type = "definicion"
    elif deontic_modality != "ninguno":
        # Hay marcador deóntico explícito y ningún otro marcador más
        # específico (presunción/remisión/definición): el default modal es
        # "regla" — es, literalmente, la definición de statement_type=regla
        # en este esquema (mandato con antecedente y consecuente).
        statement_type = "regla"
    else:
        notes.append(
            "Tipo de norma: no determinado. Sin marcador léxico de "
            "presunción/remisión/definición ni deóntica explícita. "
            "Distinguir principio/regla_interpretativa/norma_organica/"
            "ficcion sin marcador textual requiere criterio humano."
        )

    has_enumeration, enumeration_closed = _detect_enumeration(text)

    structure = _derive_structure(statement_type, exception_present, has_enumeration)
    if structure is None and statement_type is not None:
        notes.append(
            f"Estructura: no determinada. El tipo de norma detectado "
            f"('{statement_type}') admite más de una estructura "
            f"compatible sin más evidencia "
            f"({sorted(COMPATIBILITY.get(statement_type, set()))})."
        )

    proleg_preview = None
    if exception_present:
        proleg_preview = build_proleg_preview(exception_marker, exception_scope, statement_type)

    return LabelProposal(
        statement_type=statement_type,
        structure=structure,
        deontic_modality=deontic_modality,
        hohfeldian_position=hohfeldian_position,
        addressee=addressee,
        antecedent_operator=antecedent_operator,
        exception_present=exception_present,
        exception_marker=exception_marker,
        exception_scope=exception_scope,
        presumption_rebuttable=presumption_rebuttable,
        notes=notes,
        proleg_preview=proleg_preview,
    )
