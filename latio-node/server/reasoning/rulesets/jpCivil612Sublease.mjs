// jpCivil612Sublease.mjs — port 1:1 de src/reasoning/rulesets/jp_civil_612_sublease.py.
//
// Codifica el ejemplo completo del Apéndice A de Satoh et al. 2010 ("PROLEG:
// An Implementation of the Presupposed Ultimate Fact Theory of Japanese
// Civil Code by PROLOG Technology", JURISIN 2010): cancelación de un
// contrato de arrendamiento por subarriendo no autorizado, Art. 612 del
// Código Civil japonés. Es el "caso de oro" que verify_prod compara contra
// el Apéndice B del propio paper (proved=true, traza no vacía) — ver
// tests/reasoning.test.mjs.
//
// Estructura lógica (idéntica al original Python, no repetida acá en el
// comentario — ver el módulo fuente para la jerarquía completa de reglas y
// excepciones si hace falta releerla).

import { Rule, RuleBase, ExceptionLink } from "../models.mjs";

const SOURCE_NOTE = "Art. 612 Código Civil japonés — Satoh et al., JURISIN 2010";

export const RULEBASE = new RuleBase({
  id: "jp-civil-612-sublease-demo",
  description:
    "Cancelación de arrendamiento por subarriendo no autorizado " +
    "(Art. 612 Código Civil japonés) — ejemplo de referencia del paper " +
    "PROLEG (Satoh et al., JURISIN 2010), Apéndice A.",
  rules: [
    new Rule({
      head: "contract_end",
      body: ["cancellation_due_to_sublease"],
      sourceNote: SOURCE_NOTE,
    }),
    new Rule({
      head: "contract_end",
      body: ["expiration_of_the_term_of_the_lease_contract"],
      sourceNote: SOURCE_NOTE,
    }),
    new Rule({
      head: "cancellation_due_to_sublease",
      body: [
        "agreement_of_lease_contract",
        "handover_to_lessee",
        "agreement_of_sublease_contract",
        "handover_to_sublessee",
        "using_leased_thing",
        "manifestation_cancellation",
      ],
      sourceNote: SOURCE_NOTE,
    }),
    new Rule({
      head: "get_approval_of_sublease",
      body: ["approval_of_sublease", "approval_before_cancellation"],
      sourceNote: SOURCE_NOTE,
    }),
    new Rule({
      head: "nonabuse_of_confidence",
      body: ["fact_of_nonabuse_of_confidence"],
      sourceNote: SOURCE_NOTE,
    }),
    new Rule({
      head: "abuse_of_confidence",
      body: ["fact_of_abuse_of_confidence"],
      sourceNote: SOURCE_NOTE,
    }),
  ],
  exceptions: [
    new ExceptionLink({
      ruleHead: "cancellation_due_to_sublease",
      exceptionHead: "get_approval_of_sublease",
    }),
    new ExceptionLink({
      ruleHead: "cancellation_due_to_sublease",
      exceptionHead: "nonabuse_of_confidence",
    }),
    new ExceptionLink({
      ruleHead: "nonabuse_of_confidence",
      exceptionHead: "abuse_of_confidence",
    }),
  ],
});
