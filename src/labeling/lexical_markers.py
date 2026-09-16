"""lexical_markers.py — patrones léxicos deterministas para el etiquetado N3.

Cada patrón está anclado en evidencia ya medida dentro del propio proyecto
(ver changelog de src/models.py: censo de presunción B1, familias de
derogabilidad) o en marcadores gramaticales de baja ambigüedad (operadores
condicionales, excepciones). Donde no hay evidencia de que un patrón
discrimine bien (ej. distinguir "regla" de "principio" sin marcador léxico),
deliberadamente NO se intenta adivinar — ver rules.py, que deja esos campos
como no_determinado en vez de forzar un valor.

IDIOMAS: siete de los ocho códigos están en castellano y uno (BR-CC) en
portugués. Los patrones cubren los dos idiomas en las mismas expresiones
regulares, sin detectar el idioma del texto. Eso solo es seguro para formas
que no existen en el otro idioma, y se midió forma por forma sobre los
22.110 artículos antes de incorporarla. Las que chocan quedaron afuera a
propósito, cada una con su motivo en el lugar donde correspondería:
"incumbe" (castellano y portugués, y además es una carga, no un deber),
"desde que" (temporal en castellano, condicional en portugués), "o
tribunal" (coincide con "juez o tribunal"), "exclusivamente" (en los dos) y
el "se" condicional del portugués (coincide con el "se" reflexivo con que
arrancan miles de artículos en castellano).

MODOS VERBALES: se reconocen los modos en que el código dispone — el
indicativo, presente y futuro, en singular y plural, con sus formas
perifrásticas ("está/estará obligado a", "é/será obrigado a") y, en
portugués, con el pronombre pegado al verbo ("pode-se", "poder-se-á"). El
subjuntivo y el condicional ("pueda", "deba", "possa", "puder", "poderia")
quedan afuera a propósito: en los códigos aparecen dentro del supuesto de
hecho ("si el deudor no pudiere pagar", "o legado de coisa que deva
encontrar-se…"), no en la consecuencia que la norma dispone.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# antecedent_operator — orden de chequeo del más específico al más genérico.
# ---------------------------------------------------------------------------

ANTECEDENT_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("siempre_que", re.compile(r"\bsiempre\s+que\b|\bsempre\s+que\b", re.IGNORECASE)),
    ("en_caso_de", re.compile(r"\ben\s+caso\s+de(\s+que)?\b|\b(?:no|em)\s+caso\s+de\b", re.IGNORECASE)),
    ("cuando", re.compile(r"\bcuando\b|\bquando\b", re.IGNORECASE)),
    # "si" condicional: al inicio de cláusula (arranque de texto, tras punto
    # o coma) y no seguido de "bien" (concesivo, no condicional). El "se"
    # condicional del portugués no se agrega: ver el docstring del módulo.
    ("si", re.compile(r"(?:^|[.,]\s*)si\s+(?!bien\b)", re.IGNORECASE)),
]

# ---------------------------------------------------------------------------
# exception — marcadores de excepción, con el texto exacto que se reporta
# como exception.marker. Los del portugués son los equivalentes directos de
# los del castellano, no fórmulas nuevas.
# ---------------------------------------------------------------------------

EXCEPTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("salvo que", re.compile(r"\bsalvo\s+que\b", re.IGNORECASE)),
    ("salvo lo dispuesto en", re.compile(r"\bsalvo\s+lo\s+dispuesto\s+en\b", re.IGNORECASE)),
    ("a menos que", re.compile(r"\ba\s+menos\s+que\b", re.IGNORECASE)),
    ("excepto cuando", re.compile(r"\bexcepto\s+cuando\b", re.IGNORECASE)),
    ("sin perjuicio de", re.compile(r"\bsin\s+perjuicio\s+de\b", re.IGNORECASE)),
    ("con excepción de", re.compile(r"\bcon\s+excepci[óo]n\s+de\b", re.IGNORECASE)),
    ("no obstante lo anterior", re.compile(r"\bno\s+obstante\s+lo\s+anterior\b", re.IGNORECASE)),
    # portugués
    ("salvo se", re.compile(r"\bsalvo\s+se\b", re.IGNORECASE)),
    ("salvo quando", re.compile(r"\bsalvo\s+quando\b", re.IGNORECASE)),
    ("salvo o disposto", re.compile(r"\bsalvo\s+o\s+disposto\b", re.IGNORECASE)),
    ("a não ser que", re.compile(r"\ba\s+n[ãa]o\s+ser\s+que\b", re.IGNORECASE)),
    ("exceto se", re.compile(r"\bexceto\s+(?:se|quando)\b", re.IGNORECASE)),
    ("ressalvado", re.compile(r"\bressalvad[oa]s?\b", re.IGNORECASE)),
    ("sem prejuízo de", re.compile(r"\bsem\s+preju[íi]zo\s+d[eoa]s?\b", re.IGNORECASE)),
    ("com exceção de", re.compile(r"\b(?:com|à)\s+exce[çc][ãa]o\s+d[eoa]s?\b", re.IGNORECASE)),
]

# Referencia a otro artículo dentro de la cláusula de excepción -> scope
# "por_remision"; si no aparece, se asume "interna" (la excepción está
# contenida en el propio artículo). "artigo" es la forma portuguesa.
ARTICLE_REFERENCE_RE = re.compile(
    r"\bart(?:[íi]culo|igo)?s?\.?\s*\d+", re.IGNORECASE
)

# ---------------------------------------------------------------------------
# presunción — B1 del changelog de models.py: "se presume de derecho" marca
# la presunción de derecho (irrebuttable); "se presume" a secas, la legal
# (rebuttable). Orden importa: chequear "de derecho" primero.
# ---------------------------------------------------------------------------

PRESUMPTION_DE_DERECHO_RE = re.compile(
    r"\bse\s+presum(?:e|en)\s+de\s+derecho\b", re.IGNORECASE
)
# "se presume" es igual en los dos idiomas; el portugués agrega la forma con
# el pronombre pegado ("presume-se") y la del futuro ("presumir-se-á"). El
# Código Civil brasileño no usa una fórmula equivalente a "de derecho": sus
# presunciones son relativas salvo que la ley diga lo contrario.
PRESUMPTION_LEGAL_RE = re.compile(
    r"\bse\s+presum(?:e|en)\b|\bpresume(?:m)?-se\b|\bpresumir-se-(?:[áa]|[ãa]o)\b", re.IGNORECASE
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
    r"rigen?\s+las\s+disposiciones\s+de|"
    # portugués: "aplica-se o disposto no art.", "aplicar-se-á", "rege-se"
    r"o\s+disposto\s+n[oa]s?|aplica(?:m)?-se|aplicar-se-(?:[áa]|[ãa]o)|"
    r"observar-se-(?:[áa]|[ãa]o)|rege(?:m)?-se)\b.{0,80}?\bart(?:[íi]culo|igo)?s?\.?\s*\d+",
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
    r"|\bes\s+aquel(?:la)?\s+(?:persona|acto|contrato|cosa)?\s*que\b"
    # portugués. "considera-se" queda afuera a propósito: en el Código Civil
    # brasileño introduce tanto definiciones ("considera-se domicílio…") como
    # ficciones y reglas ("considera-se celebrado o contrato no lugar…").
    r"|\bentende(?:m)?-se\s+por\b|\bdenomina(?:m)?-se\b",
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

# --- Negación --------------------------------------------------------------
#
# Un marcador afirmativo NO cuenta si lo precede una negación ("no", "ni",
# "não", "nem"), con o sin un pronombre átono en el medio. Sin contemplar el
# pronombre, "no SE puede renunciar" y "não SE pode aceitar" se leían como
# PERMISO: 97 artículos en castellano tenían el signo invertido por eso, y
# otros 33 con "no se debe" figuraban como obligación.
#
# Tampoco cuenta si lo precede un cuantificador negativo ("nadie está
# obligado a vender" niega la obligación, no la afirma).
#
# `re` exige ancho fijo en cada lookbehind, así que se genera uno por
# combinación en lugar de uno solo con alternativas de largo distinto.

_NEGADORES = ("no", "ni", r"n[ãa]o", "nem")
_CLITICOS = (
    "se", "le", "les", "lo", "la", "los", "las", "me", "te", "nos", "os",
    "lhe", "lhes", "o", "a", "as", "vos",
)
_CUANTIFICADORES_NEGATIVOS = ("nadie", "ninguno", "ninguna", r"ningu[ée]m", "nenhum", "nenhuma")

_NEG = "".join(
    [rf"(?<!\b{n}\s)" for n in _NEGADORES]
    + [rf"(?<!\b{n}\s{c}\s)" for n in _NEGADORES for c in _CLITICOS]
    + [rf"(?<!\b{q}\s)" for q in _CUANTIFICADORES_NEGATIVOS]
)

# Forma negada explícita: "no puede", "no se podrá", "não lhe pode", "nem pode".
_NEGADO = r"\b(?:no|ni|n[ãa]o|nem)\s+(?:(?:" + "|".join(_CLITICOS) + r")\s+)?"


def _afirmativo(patron: str) -> str:
    """Marcador afirmativo con la guarda de negación. El lookahead va
    primero para que los lookbehind solo se evalúen donde el marcador
    realmente empieza, y no en cada posición del texto."""
    return rf"(?={patron}){_NEG}{patron}"


# --- Verbos modales, en todas sus formas indicativas ----------------------

# poder: presente y futuro, singular y plural; en portugués también con el
# pronombre pegado ("pode-se") o intercalado en el futuro ("poder-se-á").
_PODER = (
    r"(?:puede|pueden|podr[áa]|podr[áa]n"
    r"|pode|podem|poder[áa]|poder[ãa]o|poder-se-(?:[áa]|[ãa]o))"
)
# deber: ídem.
_DEBER = (
    r"(?:debe|deben|deber[áa]|deber[áa]n"
    r"|deve|devem|dever[áa]|dever[ãa]o|dever-se-(?:[áa]|[ãa]o))"
)

# Verbos de las perífrasis ("está obligado", "é obrigado", "fica obrigado"):
# presente y futuro, singular y plural.
_ESTAR = r"(?:est[áa]|est[áa]n|estar[áa]|estar[áa]n|est[ãa]o|estar[ãa]o)"
_SER = r"(?:es|son|ser[áa]|ser[áa]n|é|s[ãa]o|ser[ãa]o)"
_QUEDAR = r"(?:queda|quedan|quedar[áa]|quedar[áa]n|fica|ficam|ficar[áa]|ficar[ãa]o)"
_TENER = r"(?:tiene|tienen|tendr[áa]|tendr[áa]n|tem|t[êe]m|ter[áa]|ter[ãa]o)"

# Un infinitivo a continuación (con o sin pronombre pegado): "exceder",
# "efectuarse", "ausentar-se".
_INFINITIVO = r"\s+\w+(?:ar|er|ir|ír)(?:se|lo|la|los|las|le|les|-se|-lo|-la|-los|-las|-lhe|-lhes)?\b"

DEONTIC_PROHIBICION_RE = re.compile(
    r"\bproh[íi]bese\b|\bse\s+proh[íi]be\b|\bproíbe-se\b|\bveda-se\b"
    + r"|" + _NEGADO + r"\b" + _PODER + r"(?![\w-])"
    # "no deber" + INFINITIVO es un deber de no hacer: "no deben exceder la
    # normal tolerancia", "no debe efectuarse la restitución". Sin infinitivo
    # significa otra cosa — "no se deben intereses", "no debe colación" dicen
    # que nada se adeuda — y por eso no está acá: la guarda de negación de la
    # obligación lo deja en "ninguno".
    #
    # Revisados los 66 casos de los 8 códigos, 56 son prohibiciones. De los
    # otros se excluyen los dos patrones que niegan una obligación en lugar de
    # imponer una abstención: "no debe RESPONDER" (ausencia de
    # responsabilidad) y "no deberán resolverse NECESARIAMENTE". Quedan mal
    # leídos unos seis ("no deben contribuir en nada", "no deben ser
    # colacionadas"), que no tienen una marca léxica que los distinga.
    + r"|" + _NEGADO + r"\b" + _DEBER + r"(?![\w-])(?!\s+responder\b)(?!\s+\S+\s+necesariamente\b)" + _INFINITIVO
    + r"|\bno\s+se\s+permit|\bn[ãa]o\s+se\s+admite\b"
    # "no es lícito", "no será permitido", "não é facultado": negar la
    # permisión es prohibir.
    + r"|\b(?:no|n[ãa]o)\s+" + _SER + r"\s+(?:l[íi]cit|permitid|facultad)[oa]s?\b"
    # "es nulo/nula" NO está acá a propósito: la nulidad es una consecuencia
    # jurídica sobre el ACTO (su invalidez), no un operador deóntico sobre la
    # CONDUCTA de alguien. "Es nula la donación que comprenda la totalidad de
    # los bienes" no le prohíbe nada a nadie: dice qué pasa si se hace.
    # Tratarla como prohibición mezclaba dos planos distintos.
    + r"|\b" + _QUEDAR + r"\s+proh[íi]bid[ao]s?\b|\bno\s+se\s+admit"
    # portugués: "é vedado", "é proibido", "é defeso" (fórmula clásica del
    # Código Civil brasileño: "é defeso ao juiz…").
    + r"|\b(?:" + _SER + r"|" + _QUEDAR + r")\s+(?:vedad|proibid|defes)[oa]s?\b"
    # "Nadie puede construir…", "ninguno de los comuneros podrá inquietar…",
    # "ninguém pode…": el cuantificador negativo prohíbe aunque el verbo esté
    # en afirmativo. La ventana se limita a palabras y comas para no cruzar a
    # otra oración.
    + r"|\b(?:" + "|".join(_CUANTIFICADORES_NEGATIVOS) + r")\b[\s\w,]{0,40}?\b" + _PODER + r"(?![\w-])",
    re.IGNORECASE,
)
DEONTIC_OBLIGACION_RE = re.compile(
    _afirmativo(r"\b" + _DEBER + r"(?![\w-])")
    + r"|" + _afirmativo(r"\b(?:deve|devem)-se\b")
    + r"|" + _afirmativo(r"\b(?:" + _ESTAR + r"|" + _SER + r"|" + _QUEDAR + r")\s+(?:obligad|obrigad)[ao]s?\s+a\b")
    + r"|" + _afirmativo(r"\b" + _TENER + r"\s+el\s+deber\b")
    + r"|" + _afirmativo(r"\b" + _TENER + r"\s+o\s+dever\s+de\b")
    + r"|" + _afirmativo(r"\b" + _SER + r"\s+(?:obligatori|obrigat[óo]ri)[ao]s?\b")
    + r"|" + _afirmativo(r"\b" + _ESTAR + r"\s+en\s+la\s+obligaci[óo]n\b"),
    # "incumbe" queda afuera a propósito: aparece igual en los dos idiomas y
    # casi siempre expresa una CARGA ("incumbe al actor probar"), que no es un
    # deber — no tiene un derecho correlativo en nadie.
    re.IGNORECASE,
)
DEONTIC_PERMISO_RE = re.compile(
    # "puede ser / pueden ser" y "pode ser / podem ser" describen una
    # modalidad del objeto ("la aceptación puede ser expresa o tácita"), no
    # un permiso dirigido a alguien: se excluyen para no inflar el permiso
    # con enunciados descriptivos.
    _afirmativo(r"\b(?:puede|pueden|pode|podem)(?![\w-])(?!\s+ser\b)")
    + r"|" + _afirmativo(r"\b(?:podr[áa]|podr[áa]n|poder[áa]|poder[ãa]o|poder-se-(?:[áa]|[ãa]o))(?![\w-])")
    + r"|" + _afirmativo(r"\b(?:pode|podem)-se\b")
    + r"|" + _afirmativo(r"\b" + _ESTAR + r"\s+facultad[ao]s?\s+(?:a|para)\b")
    # portugués: "é lícito", "é facultado", "é permitido", "tem a faculdade de".
    + r"|" + _afirmativo(r"\b(?:" + _SER + r"|" + _QUEDAR + r")\s+(?:l[íi]cit|facultad|permitid)[oa]s?\b")
    + r"|" + _afirmativo(r"\b" + _TENER + r"\s+a\s+faculdade\s+de\b"),
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
    # "tiene derecho a / al", "tendrá derecho a", "tem direito a / à / ao",
    # "terão direito a": presente y futuro, singular y plural.
    _afirmativo(r"\b" + _TENER + r"\s+derecho\s+(?:a|al)\b")
    + r"|" + _afirmativo(r"\b" + _TENER + r"\s+direito\s+(?:a|à|ao|aos|às|as)(?!\w)"),
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# addressee — a quién se dirige el mandato. "partes" es el default modal
# del derecho privado (no un marcador léxico), por eso vive en rules.py como
# default explícito, no acá.
# ---------------------------------------------------------------------------

# Portugués: "o juiz" y "a autoridade judiciária". "o tribunal" queda afuera
# a propósito: coincide con "el juez o tribunal" en castellano.
ADDRESSEE_JUEZ_RE = re.compile(
    r"\bel\s+juez\b|\bel\s+tribunal\b|\bla\s+autoridad\s+judicial\b"
    r"|\bo\s+juiz\b|\ba\s+autoridade\s+judici[áa]ria\b",
    re.IGNORECASE,
)
# Portugués: "o tabelião", "o oficial do/de registro", "o notário" (con tilde:
# sin ella es la palabra castellana, ya cubierta por "el notario").
ADDRESSEE_FUNCIONARIO_RE = re.compile(
    r"\bel\s+notario\b|\bel\s+registrador\b|\bel\s+funcionario\b|\bel\s+oficial\s+del\s+registro\b"
    r"|\bo\s+tabeli[ãa]o\b|\bo\s+oficial\s+d[oe]\s+registro\b|\bo\s+notário\b",
    re.IGNORECASE,
)
ADDRESSEE_TERCERO_RE = re.compile(
    r"\bun\s+tercero\b|\bterceros\b|\bla\s+contraparte\b|\bum\s+terceiro\b|\bterceiros\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# enumeración — usado solo para resolver structure de "definicion" cuando
# hay lista explícita (a diferencia del intento anterior, acá no se decide
# nada por sí solo: enumeration_closed se deja sin determinar salvo marcador
# explícito, ver rules.py).
# ---------------------------------------------------------------------------

ENUMERATION_ITEM_RE = re.compile(r"(?:^|\n)\s*(?:[a-z]\)|\d+[\.\)]|-\s)", re.IGNORECASE | re.MULTILINE)
ENUMERATION_CLOSED_RE = re.compile(
    r"\b[uú]nicamente\b|\btaxativamente\b|\bsolo\s+en\s+los\s+siguientes\s+casos\b"
    r"|\bsomente\b|\bapenas\s+nos\s+seguintes\s+casos\b",
    re.IGNORECASE,
)
ENUMERATION_OPEN_RE = re.compile(
    r"\btales\s+como\b|\bentre\s+otros\b|\bpor\s+ejemplo\b|\btais\s+como\b|\bentre\s+outros\b",
    re.IGNORECASE,
)
