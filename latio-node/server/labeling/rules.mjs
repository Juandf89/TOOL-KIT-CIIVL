// labeling/rules.mjs — port de src/labeling/rules.py.
//
// Motor de reglas deterministas para el etiquetado N3. Mismo contrato que el
// original: determined_fields (marcador léxico de baja ambigüedad),
// default_fields (sin marcador, valor modal documentado) y
// undetermined_fields (sin evidencia, nunca adivinado). No usa red, no usa
// LLM, no tiene costo — igual que la versión Python.

import * as lex from "./lexicalMarkers.mjs";
import { COMPATIBILITY } from "../models.mjs";
import { prove } from "../reasoning/engine.mjs";
import { Party, FactAction } from "../reasoning/models.mjs";
import { RuleBase, Rule, ExceptionLink, FactBase, FactEntry } from "../reasoning/models.mjs";

function detectAntecedentOperator(text) {
  for (const [label, pattern] of lex.ANTECEDENT_PATTERNS) {
    if (pattern.test(text)) return label;
  }
  return "ninguno_explicito";
}

function detectException(text) {
  for (const [markerLabel, pattern] of lex.EXCEPTION_PATTERNS) {
    const match = pattern.exec(text);
    if (match) {
      const tail = text.slice(match.index, match.index + 300);
      const scope = lex.ARTICLE_REFERENCE_RE.test(tail) ? "por_remision" : "interna";
      return { present: true, marker: markerLabel, scope };
    }
  }
  return { present: false, marker: null, scope: null };
}

function detectPresumption(text) {
  if (lex.PRESUMPTION_DE_DERECHO_RE.test(text)) return { isPresumption: true, rebuttable: false };
  if (lex.PRESUMPTION_LEGAL_RE.test(text)) return { isPresumption: true, rebuttable: true };
  return { isPresumption: false, rebuttable: null };
}

function detectRemision(text) {
  // Python: len(text.split()) — split() sin argumento colapsa cualquier
  // corrida de whitespace y descarta vacíos al inicio/fin. Equivalente en
  // JS: split en \s+ sobre el texto trimeado, filtrando vacío residual si
  // el texto es "".
  const trimmed = text.trim();
  const nWords = trimmed === "" ? 0 : trimmed.split(/\s+/).length;
  return nWords <= lex.REMISION_MAX_WORDS && lex.REMISION_LEAD_RE.test(text);
}

function detectDefinicion(text) {
  return lex.DEFINICION_LEAD_RE.test(text);
}

// Von Wright: obligación / prohibición / permiso. Orden importa — prohibición
// antes que permiso ("no podrá" no debe matchear "podrá").
function detectDeonticModality(text) {
  if (lex.DEONTIC_PROHIBICION_RE.test(text)) return "prohibicion";
  if (lex.DEONTIC_OBLIGACION_RE.test(text)) return "obligacion";
  if (lex.DEONTIC_PERMISO_RE.test(text)) return "permiso";
  return null;
}

// Correlato hohfeldiano por defecto de la modalidad deóntica detectada —
// simplificación declarada, no análisis bilateral completo de Hohfeld (no
// identifica contraparte). Ver docstring del original Python para la
// justificación completa de la bifurcación permiso->potestad/privilegio.
function deriveHohfeldFromDeontic(deonticModality, addressee) {
  if (deonticModality === "obligacion" || deonticModality === "prohibicion") return "deber";
  if (deonticModality === "permiso") {
    if (addressee === "juez" || addressee === "funcionario_o_notario") return "potestad";
    return "privilegio";
  }
  return "ninguno";
}

function detectAddressee(text) {
  if (lex.ADDRESSEE_JUEZ_RE.test(text)) return "juez";
  if (lex.ADDRESSEE_FUNCIONARIO_RE.test(text)) return "funcionario_o_notario";
  if (lex.ADDRESSEE_TERCERO_RE.test(text)) return "tercero";
  return null;
}

function detectEnumeration(text) {
  if (!lex.ENUMERATION_ITEM_RE.test(text)) return { has: false, closed: null };
  if (lex.ENUMERATION_CLOSED_RE.test(text)) return { has: true, closed: true };
  if (lex.ENUMERATION_OPEN_RE.test(text)) return { has: true, closed: false };
  return { has: true, closed: null }; // hay lista, abierta/cerrada sin determinar
}

// Usa COMPATIBILITY para derivar structure solo cuando queda un único
// candidato posible — nunca elige entre varios igual de válidos.
function deriveStructure(statementType, exceptionPresent, hasEnumeration) {
  if (statementType === null) return null;
  const candidates = COMPATIBILITY[statementType];
  if (!candidates || candidates.size === 0) return null;
  if (exceptionPresent) {
    return candidates.has("supuesto_consecuencia_con_excepcion")
      ? "supuesto_consecuencia_con_excepcion"
      : null;
  }
  let remaining = new Set(candidates);
  remaining.delete("supuesto_consecuencia_con_excepcion");
  if (!hasEnumeration) {
    remaining.delete("enumeracion_taxativa");
    remaining.delete("enumeracion_enunciativa");
  }
  if (remaining.size === 1) return [...remaining][0];
  return null;
}

// Instancia una RuleBase mínima y GENÉRICA a partir de la estructura ya
// detectada (regla + excepción) y corre el motor PROLEG real dos veces: sin
// la excepción probada, y con ella. No fabrica contenido semántico del
// artículo — ver docstring completo en el original Python (build_proleg_preview)
// para la distinción presunción/excepción sustantiva que documenta `note`.
export function buildProlegPreview(exceptionMarker, exceptionScope, statementType = null) {
  const rulebase = new RuleBase({
    id: "preview_derrotabilidad",
    description: `Estructura genérica derivada del artículo: regla con excepción ("${exceptionMarker}", scope=${exceptionScope}).`,
    rules: [
      new Rule({
        head: "consecuencia_aplica",
        body: ["antecedente_cumplido"],
        sourceNote: "Regla base detectada por reglas léxicas (no contenido inventado).",
      }),
    ],
    exceptions: [
      new ExceptionLink({ ruleHead: "consecuencia_aplica", exceptionHead: "excepcion_probada" }),
    ],
  });

  const baseFacts = new FactBase({
    entries: [
      new FactEntry({ action: FactAction.ALLEGE, fact: "antecedente_cumplido", party: Party.PLAINTIFF }),
      new FactEntry({ action: FactAction.PROVIDE_EVIDENCE, fact: "antecedente_cumplido", party: Party.PLAINTIFF }),
      new FactEntry({ action: FactAction.PLAUSIBLE, fact: "antecedente_cumplido", party: null }),
    ],
  });

  const withoutException = prove("consecuencia_aplica", Party.PLAINTIFF, rulebase, baseFacts);

  const withExceptionFacts = new FactBase({
    entries: [
      ...baseFacts.entries,
      new FactEntry({ action: FactAction.PLAUSIBLE, fact: "excepcion_probada", party: null }),
    ],
  });
  const withException = prove("consecuencia_aplica", Party.PLAINTIFF, rulebase, withExceptionFacts);

  let note;
  if (statementType === "presuncion") {
    note =
      "Vista previa estructural: usa el motor de razonamiento real sobre " +
      "una regla genérica con la misma forma detectada en el artículo. En " +
      "una presunción, esto modela la PRUEBA EN CONTRARIO (desplazamiento " +
      "de la carga de la prueba hacia quien quiere desvirtuarla), no la " +
      "derrota de una regla sustantiva — son figuras procesales distintas " +
      "aunque el motor las calcule con el mismo mecanismo. No es un " +
      "análisis semántico del contenido específico del artículo.";
  } else {
    note =
      "Vista previa estructural: usa el motor de razonamiento real sobre " +
      "una regla genérica con la misma forma detectada en el artículo " +
      "(regla + excepción sustantiva). No es un análisis semántico del " +
      "contenido específico del artículo — muestra que la excepción " +
      "detectada, si se prueba, efectivamente derrota la regla bajo el " +
      "motor determinista.";
  }

  return {
    rulebaseId: rulebase.id,
    withoutException: { proved: withoutException.proved, traceLength: withoutException.trace.length },
    withException: { proved: withException.proved, traceLength: withException.trace.length },
    note,
  };
}

export function proposeFromText(rawText) {
  // NFC: sin esto, el mismo texto en dos formas Unicode canónicamente
  // equivalentes (copiado desde macOS, o extraído de OCR, que suelen
  // producir NFD) puede no matchear los patrones léxicos (tildes
  // precompuestas) y dar un resultado distinto para el mismo enunciado.
  // text.normalize("NFC") de JS es equivalente a unicodedata.normalize de
  // Python — ambos implementan el mismo algoritmo Unicode estándar.
  const text = rawText.normalize("NFC").trim();

  const determined = [];
  const defaultFields = [];
  const undetermined = [];
  const notes = [];

  const antecedentOperator = detectAntecedentOperator(text);
  determined.push("antecedent_operator");

  const { present: exceptionPresent, marker: exceptionMarker, scope: exceptionScope } = detectException(text);
  determined.push("exception_present");
  if (exceptionPresent) {
    determined.push("exception_marker", "exception_scope");
  }

  let deonticModality = detectDeonticModality(text);
  const deonticDetermined = deonticModality !== null;
  if (deonticDetermined) {
    determined.push("deontic_modality");
  } else {
    deonticModality = "ninguno";
    undetermined.push("deontic_modality");
    notes.push(
      "Deóntica (Von Wright): sin marcador léxico de obligación/prohibición/" +
      "permiso — se deja 'ninguno' por defecto (correcto para definiciones/" +
      "remisiones, pero revisar si es una regla con deóntica implícita en " +
      "presente indicativo, ej. 'el comprador paga el precio' sin 'deberá')."
    );
  }

  // addressee se detecta ACÁ (antes de derivar Hohfeld) porque
  // deriveHohfeldFromDeontic necesita saber si el "permiso" se dirige a un
  // juez/funcionario (potestad) o a partes/tercero (privilegio).
  let addressee = detectAddressee(text);
  if (addressee !== null) {
    determined.push("addressee");
  } else if (deonticModality !== "ninguno") {
    addressee = "partes";
    defaultFields.push("addressee");
    notes.push(
      "Destinatario: sin marcador de juez/funcionario/tercero — se asume " +
      "'partes' por defecto (mayoría del derecho privado); revisar si el " +
      "artículo se dirige a otro destinatario."
    );
  } else {
    undetermined.push("addressee");
  }

  const hohfeldianPosition = deriveHohfeldFromDeontic(deonticDetermined ? deonticModality : null, addressee);
  if (deonticDetermined) {
    defaultFields.push("hohfeldian_position");
    notes.push(
      "Posición (Hohfeld): correlato por defecto de la deóntica detectada " +
      "(y, si es 'permiso', del destinatario) — no un análisis bilateral " +
      "de Hohfeld (no identifica contraparte) — ver " +
      "docs/limitaciones_conocidas.md §2."
    );
  } else {
    undetermined.push("hohfeldian_position");
  }

  let statementType = null;
  let statementTypeDetermined = false;
  let presumptionRebuttable = null;

  const { isPresumption, rebuttable } = detectPresumption(text);
  if (isPresumption) {
    statementType = "presuncion";
    presumptionRebuttable = rebuttable;
    statementTypeDetermined = true;
    determined.push("statement_type", "presumption_rebuttable");
  } else if (detectRemision(text)) {
    statementType = "remision";
    statementTypeDetermined = true;
    determined.push("statement_type");
  } else if (detectDefinicion(text)) {
    statementType = "definicion";
    statementTypeDetermined = true;
    determined.push("statement_type");
  } else if (deonticModality !== "ninguno") {
    // Hay marcador deóntico explícito y ningún otro marcador más específico:
    // el default modal es "regla".
    statementType = "regla";
    defaultFields.push("statement_type");
  } else {
    undetermined.push("statement_type");
    notes.push(
      "Tipo de norma: no determinado. Sin marcador léxico de presunción/" +
      "remisión/definición ni deóntica explícita. Distinguir " +
      "principio/regla_interpretativa/norma_organica/ficcion sin marcador " +
      "textual requiere criterio humano."
    );
  }

  const { has: hasEnumeration, closed: enumerationClosed } = detectEnumeration(text);

  const structure = deriveStructure(statementType, exceptionPresent, hasEnumeration);
  if (structure !== null) {
    (statementTypeDetermined ? determined : defaultFields).push("structure");
  } else {
    undetermined.push("structure");
    if (statementType !== null) {
      const candidates = [...(COMPATIBILITY[statementType] ?? new Set())].sort();
      notes.push(
        `Estructura: no determinada. El tipo de norma detectado ` +
        `('${statementType}') admite más de una estructura compatible sin ` +
        `más evidencia (${JSON.stringify(candidates)}).`
      );
    }
  }

  undetermined.push("generality");
  notes.push(
    "Generalidad (cantidad de condiciones, conceptos indeterminados, etc.) " +
    "queda fuera del alcance de este motor de reglas — completar manualmente."
  );

  let prolegPreview = null;
  if (exceptionPresent) {
    prolegPreview = buildProlegPreview(exceptionMarker, exceptionScope, statementType);
  }

  return {
    statementType,
    structure,
    deonticModality,
    hohfeldianPosition,
    addressee,
    antecedentOperator,
    exceptionPresent,
    exceptionMarker,
    exceptionScope,
    presumptionRebuttable,
    determinedFields: determined,
    defaultFields,
    undeterminedFields: undetermined,
    notes,
    prolegPreview,
    annotatedBy: "heuristica_local",
  };
}
