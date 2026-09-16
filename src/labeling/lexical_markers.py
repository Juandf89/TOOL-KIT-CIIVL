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
#
# Dos reglas de fondo, ambas aprendidas midiendo sobre los 22.110 artículos
# reales de los 8 códigos:
#
# 1. PRESENTE DE INDICATIVO. Los códigos no redactan solo en futuro
#    ("deberá", "podrá"). El de Vélez (1869) y buena parte del peruano y el
#    brasileño usan presente: "el locatario PUEDE subarrendar", "el legado en
#    dinero DEBE ser pagado". Ignorar el presente dejaba 5.756 artículos con
#    marcador deóntico real clasificados como "sin modalidad".
#
# 2. LA NEGACIÓN INVIERTE EL SIGNO, y es el error más caro posible acá:
#    "el apoderado NO ESTÁ OBLIGADO a rendir cuentas" no es una obligación,
#    es justo lo contrario. Por eso cada marcador afirmativo lleva la guarda
#    `_NEG`, y las formas negadas que SÍ son prohibición ("no puede", "no
#    podrá", "nadie puede") se listan explícitamente en la prohibición, que
#    se evalúa primero. Las negaciones que NO son prohibición sino ausencia
#    de deber ("no está obligado a", "no tiene derecho a") caen a "ninguno":
#    para afirmar que eso es un privilegio hohfeldiano hace falta identificar
#    la contraparte, que es justamente lo que este motor no hace (ver
#    docs/limitaciones_conocidas.md §2). Preferimos "sin determinar" antes
#    que una modalidad invertida.
# ---------------------------------------------------------------------------

# "no " inmediatamente antes del marcador. Ancho fijo, requisito de los
# lookbehind de `re`.
_NEG = r"(?<!\bno\s)"

DEONTIC_PROHIBICION_RE = re.compile(
    r"\bproh[íi]bese\b|\bse\s+proh[íi]be\b"
    r"|\bno\s+podr[áa](n)?\b"
    r"|\bno\s+puede(n)?\b"
    r"|\bno\s+se\s+permit"
    # "es nulo/nula" NO está acá a propósito: la nulidad es una consecuencia
    # jurídica sobre el ACTO (su invalidez), no un operador deóntico sobre la
    # CONDUCTA de alguien. "Es nula la donación que comprenda la totalidad de
    # los bienes" no le prohíbe nada a nadie: dice qué pasa si se hace.
    # Tratarla como prohibición mezclaba dos planos distintos.
    r"|\bqueda(n)?\s+proh[íi]bid[ao]s?\b|\bno\s+se\s+admit"
    # "Nadie puede construir…", "ninguno de los comuneros podrá inquietar…":
    # el cuantificador negativo prohíbe aunque el verbo esté en afirmativo.
    # La ventana se limita a palabras y comas para no cruzar a otra oración.
    r"|\b(nadie|ninguno|ninguna)\b[\s\w,]{0,40}?\b(puede|pueden|podr[áa]|podr[áa]n)\b",
    re.IGNORECASE,
)
DEONTIC_OBLIGACION_RE = re.compile(
    _NEG + r"\bdeber[áa](n)?\b"
    r"|" + _NEG + r"\bdebe(n)?\b"
    r"|" + _NEG + r"\bestá(n)?\s+obligad[ao]s?\s+a\b"
    r"|" + _NEG + r"\btiene(n)?\s+el\s+deber\b"
    r"|" + _NEG + r"\bes\s+obligatori[ao]\b"
    r"|" + _NEG + r"\bestá(n)?\s+en\s+la\s+obligaci[óo]n\b",
    re.IGNORECASE,
)
DEONTIC_PERMISO_RE = re.compile(
    _NEG + r"\bpodr[áa](n)?\b"
    # "puede ser / pueden ser" describe una modalidad del objeto ("la
    # aceptación puede ser expresa o tácita"), no un permiso dirigido a
    # alguien: se excluye para no inflar el permiso con enunciados
    # descriptivos.
    r"|" + _NEG + r"\bpuede(n)?\b(?!\s+ser\b)"
    r"|" + _NEG + r"\bestá(n)?\s+facultad[ao]s?\s+(?:a|para)\b",
    # Salieron de acá dos marcadores:
    #   * "tiene(n) derecho a" -> no es una modalidad de Von Wright sino una
    #     posición de Hohfeld; ver DERECHO_SUBJETIVO_RE abajo.
    #   * "libremente" -> describía la capacidad o el modo de obrar de las
    #     partes ("siendo capaces de disponer libremente de lo suyo"), no un
    #     permiso concedido por el artículo. Cuando sí hay permiso, el
    #     "podrá"/"puede" de la misma oración ya lo detecta.
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# derecho subjetivo (Hohfeld) — NO es deóntica de Von Wright.
#
# "El arrendatario tiene derecho a la terminación del arrendamiento" no manda
# una conducta: afirma una posición jurídica cuyo CORRELATIVO es un deber en
# la otra parte. Eso es un derecho subjetivo, no un privilegio (cuyo
# correlativo es un no-derecho) ni un permiso. Por eso fija la posición
# hohfeldiana directamente, sin pasar por la deóntica.
#
# La guarda de negación importa igual que en los marcadores deónticos: "el
# usufructuario NO tiene derecho a pedir cosa alguna" es justo lo contrario.
# ---------------------------------------------------------------------------
DERECHO_SUBJETIVO_RE = re.compile(
    _NEG + r"\btiene(n)?\s+derecho\s+a\b",
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
