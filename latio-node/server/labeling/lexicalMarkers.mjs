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
// remisión — heurística conservadora: solo se marca "remision" cuando el
// patrón aparece cerca del inicio del artículo Y el texto es corto.
// ---------------------------------------------------------------------------
export const REMISION_LEAD_RE =
  /^\s*(lo\s+dispuesto\s+en|r[ií]ge(?:n)?|aplícase|se\s+aplicar[áa]n?|rigen?\s+las\s+disposiciones\s+de)\b.{0,80}?\bart(?:[íi]culo)?s?\.?\s*\d+/i;
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
// ---------------------------------------------------------------------------
export const DEONTIC_PROHIBICION_RE =
  /\bproh[íi]bese\b|\bse\s+proh[íi]be\b|\bno\s+podr[áa](n)?\b|\bno\s+se\s+permit|\bes\s+nul[ao]\b|\bqueda(n)?\s+proh[íi]bid[ao]s?\b|\bno\s+se\s+admit/i;
export const DEONTIC_OBLIGACION_RE =
  /\bdeber[áa](n)?\b|\bestá(n)?\s+obligad[ao]s?\s+a\b|\btiene(n)?\s+el\s+deber\b|\bes\s+obligatori[ao]\b|\bestá(n)?\s+en\s+la\s+obligaci[óo]n\b/i;
export const DEONTIC_PERMISO_RE =
  /\bpodr[áa](n)?\b|\bestá(n)?\s+facultad[ao]s?\s+(?:a|para)\b|\btiene(n)?\s+derecho\s+a\b|\blibremente\b/i;

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
export const ENUMERATION_CLOSED_RE = /\b[uú]nicamente\b|\btaxativamente\b|\bsolo\s+en\s+los\s+siguientes\s+casos\b/i;
export const ENUMERATION_OPEN_RE = /\btales\s+como\b|\bentre\s+otros\b|\bpor\s+ejemplo\b/i;
