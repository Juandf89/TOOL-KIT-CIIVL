// reasoning/engine.mjs — port 1:1 de src/reasoning/engine.py (Python).
//
// Meta-intérprete de razonamiento jurídico derrotable, fiel al algoritmo de
// la Fig. 1 de Satoh et al. 2010 ("PROLEG: An Implementation of the
// Presupposed Ultimate Fact Theory of Japanese Civil Code by PROLOG
// Technology", JURISIN 2010): prove(S, P) y alleged_and_having_evidence(S, P).
//
// ADVERTENCIA para quien edite este archivo: es la parte más sensible de
// todo el port — un cambio de orden en los `for`, un `continue` vs `break`
// mal puesto, o invertir una condición, produce una conclusión jurídica
// distinta sin que ningún error de sintaxis lo delate. Cada rama de este
// archivo está verificada contra la salida real del motor Python (mismo
// factbase, mismo rulebase, mismo `proved` y misma secuencia de
// `trace[].kind` — ver tests/reasoning.test.mjs y cross_validate.mjs, que
// corre AMBOS motores lado a lado sobre los mismos casos). No "simplificar"
// esta lógica sin volver a correr esa comparación.

import { Party, opposite, TraceStep } from "./models.mjs";

function rulesFor(head, rulebase) {
  return rulebase.rules.filter((r) => r.head === head);
}

// Un literal es "ultimate fact" si ninguna Rule del RuleBase lo tiene como
// head — no hay forma de descomponerlo más.
function isUltimateFact(literal, rulebase) {
  return rulesFor(literal, rulebase).length === 0;
}

// Gate procesal (pleading) previo a intentar probar el cuerpo de `rule` para
// `party`: cada literal del cuerpo que sea un ultimate fact debe estar
// alegado+evidenciado por `party`, o admitido por la contraria. Los
// literales que sean intermediate concepts no se chequean acá — su propio
// gate se aplica recursivamente cuando prove() los alcance.
function allegedAndHavingEvidence(rule, party, rulebase, factbase) {
  const opp = opposite(party);
  for (const literal of rule.body) {
    if (!isUltimateFact(literal, rulebase)) continue;
    if (factbase.hasAllegeAndEvidence(literal, party)) continue;
    if (factbase.hasAdmission(literal, opp)) continue;
    return false;
  }
  return true;
}

function proveInternal(goal, party, rulebase, factbase, trace) {
  trace.push(new TraceStep({ kind: "try_prove", actor: party, subject: goal }));

  const rules = rulesFor(goal, rulebase);

  if (rules.length === 0) {
    // ultimate fact: solo lo prueban la plausibilidad del juez o la
    // admisión de la parte contraria — nunca el allege+evidence propio.
    const opp = opposite(party);
    if (factbase.hasAdmission(goal, opp)) {
      trace.push(new TraceStep({ kind: "admitted", actor: opp, subject: goal }));
      return true;
    }
    if (factbase.isPlausible(goal)) {
      trace.push(new TraceStep({ kind: "plausible_true", subject: goal }));
      return true;
    }
    trace.push(new TraceStep({ kind: "failed_ultimate_fact", actor: party, subject: goal }));
    return false;
  }

  // intermediate concept: puede tener varias reglas alternativas (OR); basta
  // con que una se pruebe y sobreviva a sus excepciones.
  for (const rule of rules) {
    if (!allegedAndHavingEvidence(rule, party, rulebase, factbase)) {
      trace.push(new TraceStep({ kind: "no_rule", actor: party, subject: goal }));
      continue;
    }

    trace.push(new TraceStep({ kind: "rule_matched", actor: party, subject: goal }));

    let bodyProved = true;
    for (const literal of rule.body) {
      if (!proveInternal(literal, party, rulebase, factbase, trace)) {
        bodyProved = false;
        break;
      }
    }
    if (!bodyProved) continue;

    const exceptionHeads = rulebase.exceptions
      .filter((link) => link.ruleHead === goal)
      .map((link) => link.exceptionHead);
    const opp = opposite(party);
    let defeated = false;
    for (const exceptionHead of exceptionHeads) {
      trace.push(
        new TraceStep({ kind: "alleges_defense", actor: opp, subject: exceptionHead, against: goal })
      );
      if (proveInternal(exceptionHead, opp, rulebase, factbase, trace)) {
        trace.push(
          new TraceStep({ kind: "defense_succeeded", actor: opp, subject: exceptionHead, against: goal })
        );
        defeated = true;
        break;
      }
      trace.push(
        new TraceStep({ kind: "defense_failed", actor: opp, subject: exceptionHead, against: goal })
      );
    }

    if (defeated) continue;

    trace.push(new TraceStep({ kind: "proved", actor: party, subject: goal }));
    return true;
  }

  trace.push(new TraceStep({ kind: "failed", actor: party, subject: goal }));
  return false;
}

// Punto de entrada público: intenta probar `goal` para `party` bajo
// `rulebase`/`factbase`. Devuelve { goal, party, proved, trace }.
export function prove(goal, party, rulebase, factbase) {
  const trace = [];
  const proved = proveInternal(goal, party, rulebase, factbase, trace);
  return { goal, party, proved, trace };
}

export { Party };
