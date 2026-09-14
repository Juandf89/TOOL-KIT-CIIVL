// models.mjs — port PARCIAL de src/models.py (Python).
//
// Solo se portan los símbolos que /v1/statements/validate y
// /v1/statements/propose usan de verdad — confirmado grepeando el import
// real de api.py (`from src.models import AntecedentOperator, Addressee,
// DeonticModality, ExceptionInfo, GeneralityProxies, HohfeldianPosition,
// NormativeStatement, StatementType, Structure`). ArticleRecord,
// Institution, Architecture, Referral, Referrals, Validity, PathNode y sus
// validadores (uid/source_hash format, remisión reflexiva, etc.) NO están
// alcanzados por ninguna ruta HTTP — pertenecen al pipeline de ingesta
// (src/pipeline.py), que no se expone por la API y por lo tanto no se porta
// acá. Si en el futuro se expone un endpoint de ingesta, portar el resto
// desde el Python original en ese momento, no antes.

export class ValidationError extends Error {
  constructor(message) {
    super(message);
    this.name = "ValidationError";
  }
}

function fail(message) {
  throw new ValidationError(message);
}

// ---------------------------------------------------------------------------
// Vocabularios cerrados (espejo de schema_n3_v1_1.yaml / src/models.py)
// ---------------------------------------------------------------------------

export const STATEMENT_TYPES = new Set([
  "regla", "principio", "definicion", "remision",
  "presuncion", "ficcion", "regla_interpretativa", "norma_organica",
]);

export const STRUCTURES = new Set([
  "supuesto_consecuencia", "supuesto_consecuencia_con_excepcion",
  "definicion_pura", "enumeracion_taxativa", "enumeracion_enunciativa",
  "remision_pura", "principio_abierto",
]);

export const DEONTIC_MODALITIES = new Set(["obligacion", "prohibicion", "permiso", "ninguno"]);
export const HOHFELDIAN_POSITIONS = new Set([
  "deber", "derecho_subjetivo", "privilegio", "potestad", "sujecion", "inmunidad", "ninguno",
]);
export const DEROGABILITY_VALUES = new Set(["inderogable", "derogable_por_pacto", "indeterminada"]);
export const ADDRESSEES = new Set(["partes", "juez", "funcionario_o_notario", "tercero", "indeterminado"]);
export const ANTECEDENT_OPERATORS = new Set(["si", "cuando", "siempre_que", "en_caso_de", "ninguno_explicito"]);
export const EXCEPTION_SCOPES = new Set(["interna", "por_remision", "implicita"]);

export const COMPATIBILITY = {
  regla: new Set(["supuesto_consecuencia", "supuesto_consecuencia_con_excepcion", "enumeracion_taxativa", "enumeracion_enunciativa"]),
  principio: new Set(["principio_abierto"]),
  definicion: new Set(["definicion_pura", "enumeracion_taxativa", "enumeracion_enunciativa"]),
  remision: new Set(["remision_pura"]),
  presuncion: new Set(["supuesto_consecuencia", "supuesto_consecuencia_con_excepcion"]),
  ficcion: new Set(["supuesto_consecuencia", "definicion_pura"]),
  regla_interpretativa: new Set(["supuesto_consecuencia", "supuesto_consecuencia_con_excepcion", "principio_abierto"]),
  norma_organica: new Set(["supuesto_consecuencia", "remision_pura", "definicion_pura"]),
};

// Idéntico al original Python (src/models.py) — mismo orden de alternativas,
// mismos grupos, mismo flag "i" (case-insensitive; no hace falta "u" acá,
// ninguna alternativa usa clases Unicode extendidas).
export const DEROGABILITY_MARKER_RE =
  /no\s+(se\s+)?podr[áa](n)?\s+renunciar|irrenunciab|no\s+es\s+renunciable|es\s+nul[ao]\s+(todo|toda|cualquier)|no\s+vale\s+(la|el|toda)|no\s+producir[áa](n)?\s+efecto|se\s+tendr[áa](n)?\s+por\s+no\s+(escrit|puest)|proh[íi]bese|se\s+proh[íi]be|no\s+se\s+permit|salvo\s+(pacto|estipulaci[óo]n|convenci[óo]n)\s+en\s+contrario|a\s+falta\s+de\s+(pacto|estipulaci[óo]n|disposici[óo]n)|aunque\s+se\s+estipule/i;

// ---------------------------------------------------------------------------
// ExceptionInfo — port de la clase Pydantic homónima + su model_validator
// "_coherence".
// ---------------------------------------------------------------------------
export function makeExceptionInfo({ present = false, marker = null, scope = null } = {}) {
  if (scope !== null && !EXCEPTION_SCOPES.has(scope)) {
    fail(`scope inválido: '${scope}'. Valores permitidos: ${[...EXCEPTION_SCOPES].sort().join(", ")}.`);
  }
  if (present && scope === null) {
    fail("exception.present=True exige scope.");
  }
  if (!present && (marker || scope)) {
    fail("exception.present=False no admite marker ni scope.");
  }
  return { present, marker, scope };
}

// ---------------------------------------------------------------------------
// PresumptionInfo
// ---------------------------------------------------------------------------
export function makePresumptionInfo({ rebuttable, burdenShiftsTo = "ninguno", marker = null }) {
  if (rebuttable === false && burdenShiftsTo !== "ninguno") {
    fail(
      "Una presunción de derecho (rebuttable=False) no admite prueba en " +
      "contrario: no hay carga de la prueba que desplazar, por lo que " +
      "burden_shifts_to debe ser 'ninguno'."
    );
  }
  return { rebuttable, burdenShiftsTo, marker };
}

// ---------------------------------------------------------------------------
// TimeLimit — no expuesto como input de la API (StatementDraftRequest no
// tiene campo time_limit), pero NormativeStatement lo usa como
// default_factory=TimeLimit() interno. Se porta igual, mínimo, para que la
// construcción por defecto sea idéntica.
// ---------------------------------------------------------------------------
export function makeTimeLimit({ has = false, values = [], nature = null } = {}) {
  if (has && nature === null) fail("time_limit.has=True exige nature anotada.");
  if (!has && (values.length > 0 || nature !== null)) {
    fail("time_limit.has=False no admite values ni nature.");
  }
  return { has, values, nature };
}

// ---------------------------------------------------------------------------
// GeneralityProxies
// ---------------------------------------------------------------------------
export function makeGeneralityProxies({
  nConditions,
  hasEnumeration = false,
  enumerationClosed = null,
  indeterminateConcepts = [],
  nNamedEntitiesJuridicas = 0,
}) {
  if (nConditions === undefined || nConditions === null || nConditions < 0) {
    fail("generality.n_conditions debe ser un entero >= 0.");
  }
  if (!hasEnumeration && enumerationClosed !== null) {
    fail("enumeration_closed debe ser None si has_enumeration=False.");
  }
  if (hasEnumeration && enumerationClosed === null) {
    fail("has_enumeration=True exige enumeration_closed.");
  }
  const self = { nConditions, hasEnumeration, enumerationClosed, indeterminateConcepts, nNamedEntitiesJuridicas };
  self.deriveGenerality = function deriveGenerality() {
    if (indeterminateConcepts.length > 0 && nConditions <= 1 && !hasEnumeration) {
      return "clausula_general";
    }
    if (nConditions >= 3 || (hasEnumeration && enumerationClosed === true)) {
      return "casuistica";
    }
    return "intermedia";
  };
  return self;
}

// ---------------------------------------------------------------------------
// NormativeStatement — la pieza que /v1/statements/validate construye para
// dejar que las reglas decidan. Replica el model_validator "_rules" y los
// dos computed_field (generality_level, derogability_marker_detected) EN EL
// MISMO ORDEN que el Python original, para que el primer error que dispara
// sea siempre el mismo entre ambos motores.
// ---------------------------------------------------------------------------
export function makeNormativeStatement({
  statementId,
  spanType,
  spanIndex = null,
  textSpan = null,
  statementType,
  structure,
  deonticModality,
  hohfeldianPosition,
  derogability,
  addressee,
  antecedentOperator,
  exception,
  presumption = null,
  timeLimit = null,
  generality,
  annotatedBy = "human",
  verified = false,
}) {
  const exc = exception ?? makeExceptionInfo();
  const tl = timeLimit ?? makeTimeLimit();

  const allowed = COMPATIBILITY[statementType];
  if (!allowed) fail(`statement_type desconocido: '${statementType}'.`);
  if (!allowed.has(structure)) {
    fail(
      `combinación ilegal: statement_type=${statementType} con ` +
      `structure=${structure}. Permitidas: ${JSON.stringify([...allowed].sort())}`
    );
  }
  if (structure === "supuesto_consecuencia_con_excepcion" && !exc.present) {
    fail("structure con excepción exige exception.present=True.");
  }
  if (statementType === "presuncion" && presumption === null) {
    fail("statement_type='presuncion' exige el bloque presumption.");
  }
  if (statementType !== "presuncion" && presumption !== null) {
    fail("presumption solo se admite en statement_type='presuncion'.");
  }
  if (presumption !== null && presumption.rebuttable === false && derogability !== "inderogable") {
    fail(
      "Una presunción de derecho no admite prueba en contrario: " +
      "derogability debe ser 'inderogable'."
    );
  }
  if (spanType === "articulo_completo" && spanIndex !== null) {
    fail("span_type=articulo_completo no admite span_index.");
  }
  if (spanType !== "articulo_completo" && spanIndex === null) {
    fail(`span_type=${spanType} exige span_index.`);
  }

  const generalityLevel = generality.deriveGenerality();
  const derogabilityMarkerDetected = Boolean(textSpan && DEROGABILITY_MARKER_RE.test(textSpan));

  return {
    statementId,
    spanType,
    spanIndex,
    textSpan,
    statementType,
    structure,
    deonticModality,
    hohfeldianPosition,
    derogability,
    addressee,
    antecedentOperator,
    exception: exc,
    presumption,
    timeLimit: tl,
    generality,
    annotatedBy,
    verified,
    generalityLevel,
    derogabilityMarkerDetected,
  };
}
