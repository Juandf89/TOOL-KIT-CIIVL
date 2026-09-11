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

# Nota: detección de enumeraciones (has_enumeration/enumeration_closed) se
# deja para un paso posterior — el propio proyecto no midió evidencia de
# qué tan confiable es un regex de listas para eso, y forzar un valor sin
# esa evidencia repetiría el mismo error que motivó esta reescritura.
