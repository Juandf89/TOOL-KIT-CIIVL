// coCivil256Visitas.mjs — port 1:1 de src/reasoning/rulesets/co_civil_256_visitas.py.
//
// Régimen de visitas del Art. 256 del Código Civil colombiano (modificado
// por la Ley 2229 de 2022). Ver el módulo fuente Python para el texto legal
// completo citado, la verificación contra fuentes (2026-09-10) y la
// advertencia sobre qué reglas están respaldadas por el N0 real del proyecto
// (data/processed/CO-CC_articles.json, codificación de 1887 sin la reforma
// de 2022) y cuáles no (`_NOT_IN_PROJECT_CORPUS`).

import { Rule, RuleBase, ExceptionLink } from "../models.mjs";

const SOURCE_UID = "CO-CC-1873-ART-256";
const SOURCE_NOTE =
  "Art. 256 Código Civil colombiano, modificado por la Ley 2229 de 2022 " +
  "(régimen de visitas) — verificado 2026-09-10 contra fuentes " +
  "independientes coincidentes, no contra el Diario Oficial.";
const NOT_IN_PROJECT_CORPUS =
  " — NO respaldado por el corpus del proyecto (N0 pre-reforma 2022); " +
  "cita el texto vigente hoy, verificado externamente, no data/processed/.";

export const RULEBASE = new RuleBase({
  id: "co-civil-256-visitas",
  description:
    "Régimen de visitas del Art. 256 del Código Civil colombiano " +
    "(modificado por la Ley 2229 de 2022): derecho por defecto del " +
    "progenitor sin custodia y régimen judicial para abuelos, ambos " +
    "derrotados por la excepción absoluta de victimario condenado.",
  rules: [
    new Rule({
      head: "derecho_de_visitas_progenitor",
      body: ["no_tiene_cuidado_personal_hijos"],
      sourceUid: SOURCE_UID,
      sourceNote: SOURCE_NOTE + " — inciso 1.",
    }),
    new Rule({
      head: "regimen_visitas_abuelos",
      body: [
        "es_ascendiente_segundo_grado",
        "no_tiene_cuidado_personal_nietos",
        "justifica_regulacion",
      ],
      sourceUid: SOURCE_UID,
      sourceNote: SOURCE_NOTE + " — inciso 2." + NOT_IN_PROJECT_CORPUS,
    }),
    new Rule({
      head: "justifica_regulacion",
      body: ["progenitores_niegan_relacion"],
      sourceUid: SOURCE_UID,
      sourceNote: SOURCE_NOTE + " — inciso 2 (rama: negación del vínculo)." + NOT_IN_PROJECT_CORPUS,
    }),
    new Rule({
      head: "justifica_regulacion",
      body: ["caso_justifica_interes_superior"],
      sourceUid: SOURCE_UID,
      sourceNote: SOURCE_NOTE + " — inciso 2 (rama: interés superior del NNA)." + NOT_IN_PROJECT_CORPUS,
    }),
    new Rule({
      head: "es_victimario_absoluto",
      body: ["es_condenado_violencia_o_sexual", "es_victima_o_hermano_del_solicitante"],
      sourceUid: SOURCE_UID,
      sourceNote: SOURCE_NOTE + " — parágrafo, segunda frase (\"en ningún caso\")." + NOT_IN_PROJECT_CORPUS,
    }),
    new Rule({
      head: "es_condenado_violencia_o_sexual",
      body: ["condena_ejecutoriada_violencia_intrafamiliar"],
      sourceUid: SOURCE_UID,
      sourceNote:
        SOURCE_NOTE + " — parágrafo, primera frase (rama: violencia intrafamiliar)." + NOT_IN_PROJECT_CORPUS,
    }),
    new Rule({
      head: "es_condenado_violencia_o_sexual",
      body: ["condena_ejecutoriada_delito_sexual"],
      sourceUid: SOURCE_UID,
      sourceNote: SOURCE_NOTE + " — parágrafo, primera frase (rama: delito sexual)." + NOT_IN_PROJECT_CORPUS,
    }),
  ],
  exceptions: [
    new ExceptionLink({
      ruleHead: "derecho_de_visitas_progenitor",
      exceptionHead: "es_victimario_absoluto",
    }),
    new ExceptionLink({
      ruleHead: "regimen_visitas_abuelos",
      exceptionHead: "es_victimario_absoluto",
    }),
  ],
});
