"""rules.py — motor de reglas deterministas para el etiquetado N3 (Paso 1).

Alcance deliberadamente acotado a los campos con evidencia de alta
confiabilidad léxica dentro del propio proyecto: antecedent_operator,
exception_present/marker/scope, statement_type=presuncion/remision, y la
derivación de structure cuando COMPATIBILITY (src/models.py) la deja sin
ambigüedad una vez conocidos statement_type y exception_present.

No usa red, no usa LLM, no tiene costo. Todo lo que no se determina acá se
reporta explícitamente en `undetermined_fields` — el llamador (UI o un
humano) lo completa antes de mandar el resultado a
POST /v1/statements/validate, que es quien de verdad decide si la
combinación final es jurídicamente válida.
"""

from __future__ import annotations

from src.labeling import lexical_markers as lex
from src.labeling.schemas import LabelProposal
from src.models import COMPATIBILITY


def _detect_antecedent_operator(text: str) -> str:
    for label, pattern in lex.ANTECEDENT_PATTERNS:
        if pattern.search(text):
            return label
    # Ausencia de marcador es en sí misma una respuesta determinada: el
    # esquema tiene un valor explícito para "sin operador explícito".
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
    """Devuelve (es_presuncion, rebuttable). rebuttable es None si
    es_presuncion es False (no aplica)."""
    if lex.PRESUMPTION_DE_DERECHO_RE.search(text):
        return True, False
    if lex.PRESUMPTION_LEGAL_RE.search(text):
        return True, True
    return False, None


def _detect_remision(text: str) -> bool:
    n_words = len(text.split())
    return n_words <= lex.REMISION_MAX_WORDS and bool(lex.REMISION_LEAD_RE.search(text))


def _derive_structure(statement_type: str | None, exception_present: bool) -> str | None:
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
        return None  # excepción detectada pero statement_type no la admite: ambiguo, no forzar
    remaining = candidates - {"supuesto_consecuencia_con_excepcion"}
    if len(remaining) == 1:
        return next(iter(remaining))
    return None


def propose_from_text(text: str) -> LabelProposal:
    text = text.strip()

    determined: list[str] = []
    undetermined: list[str] = []
    notes: list[str] = []

    antecedent_operator = _detect_antecedent_operator(text)
    determined.append("antecedent_operator")

    exception_present, exception_marker, exception_scope = _detect_exception(text)
    determined.append("exception_present")
    if exception_present:
        determined += ["exception_marker", "exception_scope"]

    statement_type: str | None = None
    presumption_rebuttable: str | None = None

    is_presumption, rebuttable = _detect_presumption(text)
    if is_presumption:
        statement_type = "presuncion"
        presumption_rebuttable = rebuttable
        determined += ["statement_type", "presumption_rebuttable"]
    elif _detect_remision(text):
        statement_type = "remision"
        determined.append("statement_type")
    else:
        undetermined.append("statement_type")
        notes.append(
            "statement_type no determinado por reglas léxicas: distinguir "
            "regla/principio/definicion/regla_interpretativa/norma_organica/"
            "ficcion sin marcador textual explícito requiere criterio humano "
            "(o, más adelante, un clasificador local entrenado — ver Paso 2)."
        )

    structure = _derive_structure(statement_type, exception_present)
    if structure is not None:
        determined.append("structure")
    else:
        undetermined.append("structure")
        if statement_type is not None:
            notes.append(
                f"structure no determinado: statement_type='{statement_type}' "
                f"admite más de una estructura compatible sin excepción "
                f"detectada ({sorted(COMPATIBILITY.get(statement_type, set()))})."
            )

    for field in ("deontic_modality", "addressee", "generality"):
        undetermined.append(field)
    notes.append(
        "deontic_modality, addressee y generality quedan fuera del alcance "
        "de este paso (sin evidencia léxica confiable medida en el proyecto "
        "para proponerlos automáticamente) — completalos manualmente antes "
        "de validar."
    )

    return LabelProposal(
        statement_type=statement_type,
        structure=structure,
        antecedent_operator=antecedent_operator,
        exception_present=exception_present,
        exception_marker=exception_marker,
        exception_scope=exception_scope,
        presumption_rebuttable=presumption_rebuttable,
        determined_fields=determined,
        undetermined_fields=undetermined,
        notes=notes,
    )
