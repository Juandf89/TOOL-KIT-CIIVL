"""lexical_markers.py — patrones léxicos deterministas para el etiquetado N3.

Cada patrón está anclado en evidencia ya medida dentro del propio proyecto
(ver changelog de src/models.py: censo de presunción B1, familias de
derogabilidad) o en marcadores gramaticales de baja ambigüedad (operadores
condicionales, excepciones). Donde no hay evidencia de que un patrón
discrimine bien (ej. distinguir "regla" de "principio" sin marcador léxico),
deliberadamente NO se intenta adivinar — ver rules.py, que deja esos campos
como no_determinado en vez de forzar un valor.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# antecedent_operator — orden de chequeo del más específico al más genérico.
# ---------------------------------------------------------------------------

ANTECEDENT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("siempre_que", re.compile(r"\bsiempre\s+que\b", re.IGNORECASE)),
    ("en_caso_de", re.compile(r"\ben\s+caso\s+de(\s+que)?\b", re.IGNORECASE)),
    ("cuando", re.compile(r"\bcuando\b", re.IGNORECASE)),
    # "si" condicional: al inicio de cláusula (arranque de texto, tras punto
    # o coma) y no seguido de "bien" (concesivo, no condicional).
    ("si", re.compile(r"(?:^|[.,]\s*)si\s+(?!bien\b)", re.IGNORECASE)),
]

# ---------------------------------------------------------------------------
# exception — marcadores de excepción, con el texto exacto que se reporta
# como exception.marker.
# ---------------------------------------------------------------------------

EXCEPTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("salvo que", re.compile(r"\bsalvo\s+que\b", re.IGNORECASE)),
    ("salvo lo dispuesto en", re.compile(r"\bsalvo\s+lo\s+dispuesto\s+en\b", re.IGNORECASE)),
    ("a menos que", re.compile(r"\ba\s+menos\s+que\b", re.IGNORECASE)),
    ("excepto cuando", re.compile(r"\bexcepto\s+cuando\b", re.IGNORECASE)),
    ("sin perjuicio de", re.compile(r"\bsin\s+perjuicio\s+de\b", re.IGNORECASE)),
    ("con excepción de", re.compile(r"\bcon\s+excepci[óo]n\s+de\b", re.IGNORECASE)),
    ("no obstante lo anterior", re.compile(r"\bno\s+obstante\s+lo\s+anterior\b", re.IGNORECASE)),
]

# Referencia a otro artículo dentro de la cláusula de excepción -> scope
# "por_remision"; si no aparece, se asume "interna" (la excepción está
# contenida en el propio artículo).
ARTICLE_REFERENCE_RE = re.compile(
    r"\bart(?:[íi]culo)?s?\.?\s*\d+", re.IGNORECASE
)

# ---------------------------------------------------------------------------
# presunción — B1 del changelog de models.py: "se presume de derecho" marca
# la presunción de derecho (irrebuttable); "se presume" a secas, la legal
# (rebuttable). Orden importa: chequear "de derecho" primero.
# ---------------------------------------------------------------------------

PRESUMPTION_DE_DERECHO_RE = re.compile(
    r"\bse\s+presum(?:e|en)\s+de\s+derecho\b", re.IGNORECASE
)
PRESUMPTION_LEGAL_RE = re.compile(
    r"\bse\s+presum(?:e|en)\b", re.IGNORECASE
)

# ---------------------------------------------------------------------------
# remisión — artículo cuyo contenido normativo es, en esencia, remitir a
# otro. Heurística conservadora: el propio proyecto mide (B2, models.py)
# que solo una minoría de remisiones llevan marcador funcional reconocible
# — así que acá solo se marca "remision" cuando el patrón aparece cerca del
# inicio del artículo Y el texto es corto (si fuera largo, lo más probable
# es que la remisión sea solo una parte del artículo, no su totalidad).
# ---------------------------------------------------------------------------

REMISION_LEAD_RE = re.compile(
    r"^\s*(lo\s+dispuesto\s+en|r[ií]ge(?:n)?|aplícase|se\s+aplicar[áa]n?|"
    r"rigen?\s+las\s+disposiciones\s+de)\b.{0,80}?\bart(?:[íi]culo)?s?\.?\s*\d+",
    re.IGNORECASE,
)
REMISION_MAX_WORDS = 40

# ---------------------------------------------------------------------------
# definición — "se entiende por X...", "denomínase...", "es aquel/aquella
# que..." son fórmulas de definición estándar en la redacción legal
# continental, de baja ambigüedad (a diferencia de distinguir "regla" de
# "principio", que sí se deja sin determinar).
# ---------------------------------------------------------------------------

DEFINICION_LEAD_RE = re.compile(
    r"\bse\s+entiende(?:n)?\s+por\b|\bdenomín[ae]se\b|\bdefin[ei]ción\s+de\b"
    r"|\bpara\s+(?:efectos|los\s+efectos)\s+de\s+(?:este|esta)\b.{0,40}\bse\s+entender"
    r"|\bes\s+aquel(?:la)?\s+(?:persona|acto|contrato|cosa)?\s*que\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# deóntica (Von Wright) — obligación / prohibición / permiso. Orden importa:
# la prohibición ("no podrá") es más específica que un permiso genérico
# ("podrá"), así que se chequea primero.
# ---------------------------------------------------------------------------

DEONTIC_PROHIBICION_RE = re.compile(
    r"\bproh[íi]bese\b|\bse\s+proh[íi]be\b|\bno\s+podr[áa](n)?\b|\bno\s+se\s+permit"
    r"|\bes\s+nul[ao]\b|\bqueda(n)?\s+proh[íi]bid[ao]s?\b|\bno\s+se\s+admit",
    re.IGNORECASE,
)
DEONTIC_OBLIGACION_RE = re.compile(
    r"\bdeber[áa](n)?\b|\bestá(n)?\s+obligad[ao]s?\s+a\b|\btiene(n)?\s+el\s+deber\b"
    r"|\bes\s+obligatori[ao]\b|\bestá(n)?\s+en\s+la\s+obligaci[óo]n\b",
    re.IGNORECASE,
)
DEONTIC_PERMISO_RE = re.compile(
    r"\bpodr[áa](n)?\b|\bestá(n)?\s+facultad[ao]s?\s+(?:a|para)\b"
    r"|\btiene(n)?\s+derecho\s+a\b|\blibremente\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# addressee — a quién se dirige el mandato. "partes" es el default modal
# del derecho privado (no un marcador léxico), por eso vive en rules.py como
# default explícito, no acá.
# ---------------------------------------------------------------------------

ADDRESSEE_JUEZ_RE = re.compile(r"\bel\s+juez\b|\bel\s+tribunal\b|\bla\s+autoridad\s+judicial\b", re.IGNORECASE)
ADDRESSEE_FUNCIONARIO_RE = re.compile(
    r"\bel\s+notario\b|\bel\s+registrador\b|\bel\s+funcionario\b|\bel\s+oficial\s+del\s+registro\b",
    re.IGNORECASE,
)
ADDRESSEE_TERCERO_RE = re.compile(r"\bun\s+tercero\b|\bterceros\b|\bla\s+contraparte\b", re.IGNORECASE)

# ---------------------------------------------------------------------------
# enumeración — usado solo para resolver structure de "definicion" cuando
# hay lista explícita (a diferencia del intento anterior, acá no se decide
# nada por sí solo: enumeration_closed se deja sin determinar salvo marcador
# explícito, ver rules.py).
# ---------------------------------------------------------------------------

ENUMERATION_ITEM_RE = re.compile(r"(?:^|\n)\s*(?:[a-z]\)|\d+[\.\)]|-\s)", re.IGNORECASE | re.MULTILINE)
ENUMERATION_CLOSED_RE = re.compile(
    r"\b[uú]nicamente\b|\btaxativamente\b|\bsolo\s+en\s+los\s+siguientes\s+casos\b", re.IGNORECASE
)
ENUMERATION_OPEN_RE = re.compile(
    r"\btales\s+como\b|\bentre\s+otros\b|\bpor\s+ejemplo\b", re.IGNORECASE
)
