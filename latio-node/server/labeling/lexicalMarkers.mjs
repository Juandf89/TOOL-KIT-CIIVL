// labeling/lexicalMarkers.mjs — port de src/labeling/lexical_markers.py.
//
// OJO al re-verificar este archivo: la sintaxis de regex de JS y Python es
// casi idéntica para estos patrones (clases de caracteres, \b, alternancia,
// grupos), con dos diferencias reales que sí importan acá:
//   1. Python re.IGNORECASE + re.MULTILINE se escriben como flags "im" en JS.
//   2. Los caracteres acentuados (á, é, í, ó, ú, ñ) están escritos literales
//      en ambos — JS los soporta igual sin flag "u" adicional para esto.
// Cada patrón se comparó carácter por carácter contra el original Python al
// portarlo (no reescrito de memoria) — ver cross_validate.mjs, que corre
// decenas de textos de prueba por ambos motores y compara el resultado.

// ---------------------------------------------------------------------------
// antecedent_operator — orden de chequeo del más específico al más genérico.
// ---------------------------------------------------------------------------
export const ANTECEDENT_PATTERNS = [
  ["siempre_que", /\bsiempre\s+que\b/i],
  ["en_caso_de", /\ben\s+caso\s+de(\s+que)?\b/i],
  ["cuando", /\bcuando\b/i],
  // "si" condicional: al inicio de cláusula (arranque de texto, tras punto o
  // coma) y no seguido de "bien" (concesivo, no condicional).
  ["si", /(?:^|[.,]\s*)si\s+(?!bien\b)/i],
];

// ---------------------------------------------------------------------------
// exception — marcadores de excepción, con el texto exacto que se reporta
// como exception.marker.
// ---------------------------------------------------------------------------
export const EXCEPTION_PATTERNS = [
  ["salvo que", /\bsalvo\s+que\b/i],
  ["salvo lo dispuesto en", /\bsalvo\s+lo\s+dispuesto\s+en\b/i],
  ["a menos que", /\ba\s+menos\s+que\b/i],
  ["excepto cuando", /\bexcepto\s+cuando\b/i],
  ["sin perjuicio de", /\bsin\s+perjuicio\s+de\b/i],
  ["con excepción de", /\bcon\s+excepci[óo]n\s+de\b/i],
  ["no obstante lo anterior", /\bno\s+obstante\s+lo\s+anterior\b/i],
];

// Referencia a otro artículo dentro de la cláusula de excepción ->
// scope="por_remision"; si no aparece, se asume "interna".
export const ARTICLE_REFERENCE_RE = /\bart(?:[íi]culo)?s?\.?\s*\d+/i;

// ---------------------------------------------------------------------------
// presunción — "se presume de derecho" marca la presunción de derecho
// (irrebuttable); "se presume" a secas, la legal (rebuttable). Orden
// importa: chequear "de derecho" primero.
// ---------------------------------------------------------------------------
export const PRESUMPTION_DE_DERECHO_RE = /\bse\s+presum(?:e|en)\s+de\s+derecho\b/i;
export const PRESUMPTION_LEGAL_RE = /\bse\s+presum(?:e|en)\b/i;

// ---------------------------------------------------------------------------
// LÍMITE DE PALABRA CON ACENTOS — la diferencia que rompía la paridad con
// Python.
//
// `\b` de JavaScript es ASCII: para él "á" NO es carácter de palabra. Así,
// `/podr[áa]\b/` NUNCA matchea "podrá" (después de la "á" no ve un límite),
// mientras que en Python sí, porque ahí `\w` es Unicode. El mismo patrón,
// carácter por carácter, daba resultados DISTINTOS en cada motor: el Node en
// producción dejaba ~2.000 artículos con "podrá"/"deberá" en singular
// clasificados como "sin modalidad deóntica" que Python sí clasificaba.
//
// `FIN` y `INI` reemplazan a `\b` en todo patrón cuyo borde pueda caer sobre
// una vocal acentuada o la ñ. No uses `\b` ahí.
// ---------------------------------------------------------------------------
const LETRA = 'A-Za-zÁÉÍÓÚÜÑáéíóúüñ';
const FIN = `(?![${LETRA}])`;
const INI = `(?<![${LETRA}])`;

// ---------------------------------------------------------------------------
// remisión — heurística conservadora: solo se marca "remision" cuando el
// patrón aparece cerca del inicio del artículo Y el texto es corto.
// ---------------------------------------------------------------------------
export const REMISION_LEAD_RE = new RegExp(
  '^\\s*(lo\\s+dispuesto\\s+en|r[ií]ge(?:n)?|aplícase|se\\s+aplicar[áa]n?|rigen?\\s+las\\s+disposiciones\\s+de)' + FIN +
  '.{0,80}?\\bart(?:[íi]culo)?s?\\.?\\s*\\d+',
  'i',
);
export const REMISION_MAX_WORDS = 40;

// ---------------------------------------------------------------------------
// definición — fórmulas estándar de baja ambigüedad en redacción legal
// continental.
// ---------------------------------------------------------------------------
export const DEFINICION_LEAD_RE =
  /\bse\s+entiende(?:n)?\s+por\b|\bdenomín[ae]se\b|\bdefin[ei]ción\s+de\b|\bpara\s+(?:efectos|los\s+efectos)\s+de\s+(?:este|esta)\b.{0,40}\bse\s+entender|\bes\s+aquel(?:la)?\s+(?:persona|acto|contrato|cosa)?\s*que\b/i;

// ---------------------------------------------------------------------------
// deóntica (Von Wright) — obligación / prohibición / permiso. Orden importa:
// la prohibición ("no podrá") es más específica que un permiso genérico
// ("podrá"), así que se chequea primero.
//
// Port 1:1 de src/labeling/lexical_markers.py — ver ahí la explicación
// completa. En resumen, dos reglas medidas sobre los 22.110 artículos reales:
//
// 1. PRESENTE DE INDICATIVO: los códigos no redactan solo en futuro. El de
//    Vélez (1869) y buena parte del peruano y el brasileño usan "puede" y
//    "debe", no "podrá" y "deberá".
// 2. LA NEGACIÓN INVIERTE EL SIGNO: "no está obligado a" no es una
//    obligación. Cada marcador afirmativo lleva la guarda _NEG; las
//    negaciones que sí son prohibición ("no puede", "nadie puede") se listan
//    en la prohibición, que se evalúa primero; las que son mera ausencia de
//    deber ("no tiene derecho a") caen a "ninguno" a propósito.
// ---------------------------------------------------------------------------

// "no " inmediatamente antes del marcador.
const _NEG = '(?<!\\bno\\s)';

export const DEONTIC_PROHIBICION_RE = new RegExp(
  '\\bproh[íi]bese' + FIN + '|\\bse\\s+proh[íi]be' + FIN +
  '|\\bno\\s+podr[áa](n)?' + FIN +
  '|\\bno\\s+puede(n)?' + FIN +
  '|\\bno\\s+se\\s+permit' +
  '|\\bes\\s+nul[ao]' + FIN + '|\\bqueda(n)?\\s+proh[íi]bid[ao]s?' + FIN + '|\\bno\\s+se\\s+admit' +
  // "Nadie puede construir…", "ninguno de los comuneros podrá inquietar…".
  '|' + INI + '(nadie|ninguno|ninguna)' + FIN + '[\\s\\wáéíóúüñ,]{0,40}?' + INI + '(puede|pueden|podr[áa]|podr[áa]n)' + FIN,
  'i',
);
export const DEONTIC_OBLIGACION_RE = new RegExp(
  _NEG + '\\bdeber[áa](n)?' + FIN +
  '|' + _NEG + '\\bdebe(n)?' + FIN +
  '|' + _NEG + '\\bestá(n)?\\s+obligad[ao]s?\\s+a' + FIN +
  '|' + _NEG + '\\btiene(n)?\\s+el\\s+deber' + FIN +
  '|' + _NEG + '\\bes\\s+obligatori[ao]' + FIN +
  '|' + _NEG + '\\bestá(n)?\\s+en\\s+la\\s+obligaci[óo]n' + FIN,
  'i',
);
export const DEONTIC_PERMISO_RE = new RegExp(
  _NEG + '\\bpodr[áa](n)?' + FIN +
  // "puede ser" describe una modalidad del objeto, no un permiso.
  '|' + _NEG + '\\bpuede(n)?' + FIN + '(?!\\s+ser' + FIN + ')' +
  '|' + _NEG + '\\bestá(n)?\\s+facultad[ao]s?\\s+(?:a|para)' + FIN +
  '|' + _NEG + '\\btiene(n)?\\s+derecho\\s+a' + FIN +
  '|\\blibremente' + FIN,
  'i',
);

// ---------------------------------------------------------------------------
// addressee — a quién se dirige el mandato.
// ---------------------------------------------------------------------------
export const ADDRESSEE_JUEZ_RE = /\bel\s+juez\b|\bel\s+tribunal\b|\bla\s+autoridad\s+judicial\b/i;
export const ADDRESSEE_FUNCIONARIO_RE =
  /\bel\s+notario\b|\bel\s+registrador\b|\bel\s+funcionario\b|\bel\s+oficial\s+del\s+registro\b/i;
export const ADDRESSEE_TERCERO_RE = /\bun\s+tercero\b|\bterceros\b|\bla\s+contraparte\b/i;

// ---------------------------------------------------------------------------
// enumeración
// ---------------------------------------------------------------------------
export const ENUMERATION_ITEM_RE = /(?:^|\n)\s*(?:[a-z]\)|\d+[.)]|-\s)/im;
// `\b[uú]nicamente` tampoco sirve: ante "únicamente", el `\b` de JS no ve
// límite antes de la "ú". Mismo motivo que FIN, del otro lado de la palabra.
export const ENUMERATION_CLOSED_RE = new RegExp(
  INI + '[uú]nicamente' + FIN + '|\\btaxativamente\\b|\\bsolo\\s+en\\s+los\\s+siguientes\\s+casos\\b',
  'i',
);
export const ENUMERATION_OPEN_RE = /\btales\s+como\b|\bentre\s+otros\b|\bpor\s+ejemplo\b/i;
