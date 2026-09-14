// rulesets/index.mjs — port de src/reasoning/rulesets/__init__.py.
// RULEBASES es el registro público: RULEBASES[id] -> RuleBase.

import { RULEBASE as JP_CIVIL_612_SUBLEASE } from "./jpCivil612Sublease.mjs";
import { RULEBASE as CO_CIVIL_256_VISITAS } from "./coCivil256Visitas.mjs";

export const RULEBASES = {
  [JP_CIVIL_612_SUBLEASE.id]: JP_CIVIL_612_SUBLEASE,
  [CO_CIVIL_256_VISITAS.id]: CO_CIVIL_256_VISITAS,
};
