// labeling/lexicalMarkers.mjs — port de src/labeling/lexical_markers.py.
//
// CÓMO ESTÁ HECHO EL PUERTO (leer antes de tocar un patrón)
// ----------------------------------------------------------
// Los patrones están escritos con EL MISMO TEXTO que en Python, y la función
// `py()` los traduce a una expresión regular de JavaScript con la misma
// semántica. No se traducen a mano, porque así se rompió la paridad una vez:
//
//   `\b` y `\w` de JavaScript son ASCII. Para JS, "á", "ã", "ç" no son letras,
//   así que `/podr[áa]\b/` nunca matcheaba "podrá" y el motor en producción
//   dejaba ~2.000 artículos sin modalidad deóntica que Python sí clasificaba.
//
// `py()` reemplaza `\b` y `\w` por equivalentes Unicode (`\p{L}`, `\p{N}`), y
// todas las expresiones usan el flag "u". Al agregar o cambiar un patrón:
// copiá el texto exacto del archivo Python y pasalo por `py()`. La paridad se
// verifica sobre los 22.110 artículos reales y en cross_validate.mjs.
//
// La única diferencia deliberada de estructura es la guarda de negación
// (_NEG): Python necesita un lookbehind de ancho fijo por combinación, y JS
// admite uno solo de ancho variable, que es equivalente.

const PAL = "\\p{L}\\p{N}_";
const LIMITE = `(?:(?<=[${PAL}])(?![${PAL}])|(?<![${PAL}])(?=[${PAL}]))`;

/** Traduce un patrón con sintaxis de `re` de Python a uno de JS con `\w` y `\b` Unicode. */
function py(src) {
  src = src.replaceAll("[^\\W\\d_]", "\\p{L}");
  let out = "";
  let enClase = false;
  for (let i = 0; i < src.length; i++) {
    const c = src[i];
    if (c === "\\") {
      const n = src[i + 1];
      i++;
      if (n === "b" && !enClase) out += LIMITE;
      else if (n === "w") out += enClase ? PAL : `[${PAL}]`;
      else if (n === "W" && !enClase) out += `[^${PAL}]`;
      else out += "\\" + n;
      continue;
    }
    if (c === "[" && !enClase) enClase = true;
    else if (c === "]" && enClase) enClase = false;
    out += c;
  }
  return out;
}

const re = (src, flags = "") => new RegExp(py(src), "iu" + flags);

// ---------------------------------------------------------------------------
// antecedent_operator — orden de chequeo del más específico al más genérico.
// El "se" condicional del portugués no se agrega: coincide con el "se"
// reflexivo con que arrancan miles de artículos en castellano.
// ---------------------------------------------------------------------------
export const ANTECEDENT_PATTERNS = [
  ["siempre_que", re(String.raw`\bsiempre\s+que\b|\bsempre\s+que\b`)],
  ["en_caso_de", re(String.raw`\ben\s+caso\s+de(\s+que)?\b|\b(?:no|em)\s+caso\s+de\b`)],
  ["cuando", re(String.raw`\bcuando\b|\bquando\b`)],
  ["si", re(String.raw`(?:^|[.,]\s*)si\s+(?!bien\b)`)],
];

// ---------------------------------------------------------------------------
// exception — marcadores de excepción, con el texto exacto que se reporta
// como exception.marker. Los del portugués son los equivalentes directos de
// los del castellano.
// ---------------------------------------------------------------------------
export const EXCEPTION_PATTERNS = [
  ["salvo que", re(String.raw`\bsalvo\s+que\b`)],
  ["salvo lo dispuesto en", re(String.raw`\bsalvo\s+lo\s+dispuesto\s+en\b`)],
  ["a menos que", re(String.raw`\ba\s+menos\s+que\b`)],
  ["excepto cuando", re(String.raw`\bexcepto\s+cuando\b`)],
  ["sin perjuicio de", re(String.raw`\bsin\s+perjuicio\s+de\b`)],
  ["con excepción de", re(String.raw`\bcon\s+excepci[óo]n\s+de\b`)],
  ["no obstante lo anterior", re(String.raw`\bno\s+obstante\s+lo\s+anterior\b`)],
  // portugués
  ["salvo se", re(String.raw`\bsalvo\s+se\b`)],
  ["salvo quando", re(String.raw`\bsalvo\s+quando\b`)],
  ["salvo o disposto", re(String.raw`\bsalvo\s+o\s+disposto\b`)],
  ["a não ser que", re(String.raw`\ba\s+n[ãa]o\s+ser\s+que\b`)],
  ["exceto se", re(String.raw`\bexceto\s+(?:se|quando)\b`)],
  ["ressalvado", re(String.raw`\bressalvad[oa]s?\b`)],
  ["sem prejuízo de", re(String.raw`\bsem\s+preju[íi]zo\s+d[eoa]s?\b`)],
  ["com exceção de", re(String.raw`\b(?:com|à)\s+exce[çc][ãa]o\s+d[eoa]s?\b`)],
];

// Referencia a otro artículo dentro de la cláusula de excepción ->
// scope="por_remision"; si no aparece, se asume "interna".
export const ARTICLE_REFERENCE_RE = re(String.raw`\bart(?:[íi]culo|igo)?s?\.?\s*\d+`);

// ---------------------------------------------------------------------------
// presunción — "de derecho" (irrebuttable) se chequea antes que la legal.
// ---------------------------------------------------------------------------
// Además de la fórmula de Bello, las redacciones con que los otros códigos
// declaran una presunción absoluta (ver lexical_markers.py).
export const PRESUMPTION_DE_DERECHO_RE = re(
  String.raw`\bse\s+presum(?:e|en)\s+de\s+derecho\b` +
  String.raw`|\b(?:sin\s+(?:admitir(?:se)?|que\s+se\s+admita)|no\s+(?:se\s+)?admit(?:e|en|ir[áa]|ir[áa]n))` +
  String.raw`\s+(?:la\s+)?prueba\s+en\s+contrario\b` +
  String.raw`|\b[ij]uris\s+et\s+de\s+[ij]ure\b|\bpresunci[óo]n\s+absoluta\b` +
  String.raw`|\b(?:sem\s+admitir|n[ãa]o\s+(?:se\s+)?admit(?:e|em|ir[áa]))\s+prova\s+em\s+contr[áa]rio\b` +
  String.raw`|\bpresun[çc][ãa]o\s+absoluta\b`,
);
export const PRESUMPTION_LEGAL_RE = re(
  String.raw`\bse\s+presum(?:e|en)\b|\bpresume(?:m)?-se\b|\bpresumir-se-(?:[áa]|[ãa]o)\b`,
);

// ---------------------------------------------------------------------------
// remisión — solo cerca del inicio del artículo y si el texto es corto.
// ---------------------------------------------------------------------------
export const REMISION_LEAD_RE = re(
  String.raw`^\s*(lo\s+dispuesto\s+en|r[ií]ge(?:n)?|aplícase|se\s+aplicar[áa]n?|` +
  String.raw`rigen?\s+las\s+disposiciones\s+de|` +
  String.raw`o\s+disposto\s+n[oa]s?|aplica(?:m)?-se|aplicar-se-(?:[áa]|[ãa]o)|` +
  String.raw`observar-se-(?:[áa]|[ãa]o)|rege(?:m)?-se)\b.{0,80}?\bart(?:[íi]culo|igo)?s?\.?\s*\d+`,
);
export const REMISION_MAX_WORDS = 40;

// ---------------------------------------------------------------------------
// definición — fórmulas estándar de baja ambigüedad.
// ---------------------------------------------------------------------------
export const DEFINICION_LEAD_RE = re(
  String.raw`\bse\s+entiende(?:n)?\s+por\b|\bdenomín[ae]se\b|\bdefin[ei]ción\s+de\b` +
  String.raw`|\bpara\s+(?:efectos|los\s+efectos)\s+de\s+(?:este|esta)\b.{0,40}\bse\s+entender` +
  String.raw`|\bes\s+aquel(?:la)?\s+(?:persona|acto|contrato|cosa)?\s*que\b` +
  String.raw`|\bentende(?:m)?-se\s+por\b|\bdenomina(?:m)?-se\b`,
);

// ---------------------------------------------------------------------------
// deóntica (Von Wright). Ver lexical_markers.py para el porqué de cada regla:
// presente y futuro de indicativo en los dos idiomas, perífrasis, negación con
// pronombre intermedio, cuantificadores negativos y "no deber + infinitivo".
// ---------------------------------------------------------------------------
const _NEGADORES = ["no", "ni", "n[ãa]o", "nem"];
const _CLITICOS = [
  "se", "le", "les", "lo", "la", "los", "las", "me", "te", "nos", "os",
  "lhe", "lhes", "o", "a", "as", "vos",
];
const _CUANTIFICADORES_NEGATIVOS = ["nadie", "ninguno", "ninguna", "ningu[ée]m", "nenhum", "nenhuma"];

// Equivalente a los lookbehind de ancho fijo de Python: ni una negación (con o
// sin pronombre en el medio) ni un cuantificador negativo antes del marcador.
const _NEG =
  String.raw`(?<!\b(?:${_NEGADORES.join("|")})\s(?:(?:${_CLITICOS.join("|")})\s)?)` +
  String.raw`(?<!\b(?:${_CUANTIFICADORES_NEGATIVOS.join("|")})\s)`;

const _NEGADO = String.raw`\b(?:no|ni|n[ãa]o|nem)\s+(?:(?:` + _CLITICOS.join("|") + String.raw`)\s+)?`;

const _afirmativo = (patron) => `(?=${patron})${_NEG}${patron}`;

const _PODER =
  String.raw`(?:puede|pueden|podr[áa]|podr[áa]n` +
  String.raw`|pode|podem|poder[áa]|poder[ãa]o|poder-se-(?:[áa]|[ãa]o))`;
const _DEBER =
  String.raw`(?:debe|deben|deber[áa]|deber[áa]n` +
  String.raw`|deve|devem|dever[áa]|dever[ãa]o|dever-se-(?:[áa]|[ãa]o))`;
const _ESTAR = String.raw`(?:est[áa]|est[áa]n|estar[áa]|estar[áa]n|est[ãa]o|estar[ãa]o)`;
const _SER = String.raw`(?:es|son|ser[áa]|ser[áa]n|é|s[ãa]o|ser[ãa]o)`;
const _QUEDAR = String.raw`(?:queda|quedan|quedar[áa]|quedar[áa]n|fica|ficam|ficar[áa]|ficar[ãa]o)`;
const _TENER = String.raw`(?:tiene|tienen|tendr[áa]|tendr[áa]n|tem|t[êe]m|ter[áa]|ter[ãa]o)`;
const _INFINITIVO =
  String.raw`\s+\w+(?:ar|er|ir|ír)(?:se|lo|la|los|las|le|les|-se|-lo|-la|-los|-las|-lhe|-lhes)?\b`;

export const DEONTIC_PROHIBICION_RE = re(
  String.raw`\bproh[íi]bese\b|\bse\s+proh[íi]be\b|\bproíbe-se\b|\bveda-se\b` +
  "|" + _NEGADO + String.raw`\b` + _PODER + String.raw`(?![\w-])` +
  "|" + _NEGADO + String.raw`\b` + _DEBER +
    String.raw`(?![\w-])(?!\s+responder\b)(?!\s+\S+\s+necesariamente\b)` + _INFINITIVO +
  String.raw`|\bno\s+se\s+permit|\bn[ãa]o\s+se\s+admite\b` +
  String.raw`|\b(?:no|n[ãa]o)\s+` + _SER + String.raw`\s+(?:l[íi]cit|permitid|facultad)[oa]s?\b` +
  // "es nulo/nula" NO está acá a propósito: la nulidad es una consecuencia
  // sobre el ACTO, no un operador deóntico sobre la CONDUCTA de alguien.
  String.raw`|\b` + _QUEDAR + String.raw`\s+proh[íi]bid[ao]s?\b|\bno\s+se\s+admit` +
  String.raw`|\b(?:` + _SER + "|" + _QUEDAR + String.raw`)\s+(?:vedad|proibid|defes)[oa]s?\b` +
  String.raw`|\b(?:` + _CUANTIFICADORES_NEGATIVOS.join("|") + String.raw`)\b[\s\w,]{0,40}?\b` +
    _PODER + String.raw`(?![\w-])`,
);

export const DEONTIC_OBLIGACION_RE = re(
  [
    _afirmativo(String.raw`\b` + _DEBER + String.raw`(?![\w-])`),
    _afirmativo(String.raw`\b(?:deve|devem)-se\b`),
    _afirmativo(String.raw`\b(?:` + _ESTAR + "|" + _SER + "|" + _QUEDAR + String.raw`)\s+(?:obligad|obrigad)[ao]s?\s+a\b`),
    _afirmativo(String.raw`\b` + _TENER + String.raw`\s+el\s+deber\b`),
    _afirmativo(String.raw`\b` + _TENER + String.raw`\s+o\s+dever\s+de\b`),
    _afirmativo(String.raw`\b` + _SER + String.raw`\s+(?:obligatori|obrigat[óo]ri)[ao]s?\b`),
    _afirmativo(String.raw`\b` + _ESTAR + String.raw`\s+en\s+la\s+obligaci[óo]n\b`),
  ].join("|"),
  // "incumbe" queda afuera a propósito: aparece igual en los dos idiomas y casi
  // siempre expresa una CARGA, que no es un deber.
);

export const DEONTIC_PERMISO_RE = re(
  [
    // "puede ser" / "pode ser" describen una modalidad del objeto.
    _afirmativo(String.raw`\b(?:puede|pueden|pode|podem)(?![\w-])(?!\s+ser\b)`),
    _afirmativo(String.raw`\b(?:podr[áa]|podr[áa]n|poder[áa]|poder[ãa]o|poder-se-(?:[áa]|[ãa]o))(?![\w-])`),
    _afirmativo(String.raw`\b(?:pode|podem)-se\b`),
    _afirmativo(String.raw`\b` + _ESTAR + String.raw`\s+facultad[ao]s?\s+(?:a|para)\b`),
    _afirmativo(String.raw`\b(?:` + _SER + "|" + _QUEDAR + String.raw`)\s+(?:l[íi]cit|facultad|permitid)[oa]s?\b`),
    _afirmativo(String.raw`\b` + _TENER + String.raw`\s+a\s+faculdade\s+de\b`),
  ].join("|"),
  // Salieron "tiene(n) derecho a" (es Hohfeld, no Von Wright — ver
  // DERECHO_SUBJETIVO_RE) y "libremente" (describía la capacidad o el modo de
  // obrar de las partes, no un permiso concedido por el artículo).
);

// ---------------------------------------------------------------------------
// derecho subjetivo (Hohfeld) — NO es deóntica de Von Wright. Su correlativo
// es un deber en la otra parte: no es un privilegio ni un permiso.
// ---------------------------------------------------------------------------
export const DERECHO_SUBJETIVO_RE = re(
  _afirmativo(String.raw`\b` + _TENER + String.raw`\s+derecho\s+(?:a|al)\b`) +
  "|" + _afirmativo(String.raw`\b` + _TENER + String.raw`\s+direito\s+(?:a|à|ao|aos|às|as)(?!\w)`),
);

// ---------------------------------------------------------------------------
// addressee — a quién se dirige el mandato. "o tribunal" queda afuera: coincide
// con "el juez o tribunal" en castellano.
// ---------------------------------------------------------------------------
export const ADDRESSEE_JUEZ_RE = re(
  String.raw`\bel\s+juez\b|\bel\s+tribunal\b|\bla\s+autoridad\s+judicial\b` +
  String.raw`|\bo\s+juiz\b|\ba\s+autoridade\s+judici[áa]ria\b`,
);
export const ADDRESSEE_FUNCIONARIO_RE = re(
  String.raw`\bel\s+notario\b|\bel\s+registrador\b|\bel\s+funcionario\b|\bel\s+oficial\s+del\s+registro\b` +
  String.raw`|\bo\s+tabeli[ãa]o\b|\bo\s+oficial\s+d[oe]\s+registro\b|\bo\s+notário\b`,
);
export const ADDRESSEE_TERCERO_RE = re(
  String.raw`\bun\s+tercero\b|\bterceros\b|\bla\s+contraparte\b|\bum\s+terceiro\b|\bterceiros\b`,
);

// ---------------------------------------------------------------------------
// enumeración
// ---------------------------------------------------------------------------
export const ENUMERATION_ITEM_RE = re(String.raw`(?:^|\n)\s*(?:[a-z]\)|\d+[\.\)]|-\s)`, "m");
export const ENUMERATION_CLOSED_RE = re(
  String.raw`\b[uú]nicamente\b|\btaxativamente\b|\bsolo\s+en\s+los\s+siguientes\s+casos\b` +
  String.raw`|\bsomente\b|\bapenas\s+nos\s+seguintes\s+casos\b`,
);
export const ENUMERATION_OPEN_RE = re(
  String.raw`\btales\s+como\b|\bentre\s+otros\b|\bpor\s+ejemplo\b|\btais\s+como\b|\bentre\s+outros\b`,
);
