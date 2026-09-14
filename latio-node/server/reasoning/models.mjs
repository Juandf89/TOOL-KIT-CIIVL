// reasoning/models.mjs — port 1:1 de src/reasoning/models.py (Python, verificado
// y en producción). Estructuras de datos del meta-intérprete PROLEG.
//
// No usa ninguna librería de validación (ni Zod ni Joi): las clases son
// simples contenedores + los métodos de consulta de FactBase que engine.mjs
// necesita. La validación de forma (qué campos son obligatorios, qué shape
// tiene un FactEntry) la hace server/app.mjs al construir estos objetos desde
// el body de la request — igual que en Python Pydantic la hacía al nivel del
// endpoint (ProveRequest), no acá.
//
// Referencia exacta: src/reasoning/models.py del repo Python (LATIO), commit
// verificado con tests (92/92 pasan) antes de este port.

export const Party = Object.freeze({
  PLAINTIFF: "plaintiff",
  DEFENDANT: "defendant",
});

export function opposite(party) {
  return party === Party.PLAINTIFF ? Party.DEFENDANT : Party.PLAINTIFF;
}

export const FactAction = Object.freeze({
  ALLEGE: "allege",
  PROVIDE_EVIDENCE: "provide_evidence",
  ADMISSION: "admission",
  PLAUSIBLE: "plausible",
});

// Rule: head :- body. `head` es un "intermediate concept"; cada literal de
// `body` puede ser a su vez un intermediate concept o un "ultimate fact" —
// la distinción es estructural, se calcula en engine.mjs (_isUltimateFact),
// nunca se anota acá.
export class Rule {
  constructor({ head, body = [], sourceUid = null, sourceNote = null }) {
    this.head = head;
    this.body = body;
    this.sourceUid = sourceUid;
    this.sourceNote = sourceNote;
  }
}

// exception(ruleHead, exceptionHead): si exceptionHead se prueba para la
// parte contraria, ruleHead deja de estar probado aunque su cuerpo se haya
// probado.
export class ExceptionLink {
  constructor({ ruleHead, exceptionHead }) {
    this.ruleHead = ruleHead;
    this.exceptionHead = exceptionHead;
  }
}

export class RuleBase {
  constructor({ id, description, rules = [], exceptions = [] }) {
    this.id = id;
    this.description = description;
    this.rules = rules;
    this.exceptions = exceptions;
  }
}

export class FactEntry {
  // party es null únicamente válido para PLAUSIBLE — determinación del
  // juez, no acto procesal de una parte.
  constructor({ action, fact, party = null }) {
    this.action = action;
    this.fact = fact;
    this.party = party;
  }
}

export class FactBase {
  constructor({ entries = [] } = {}) {
    this.entries = entries;
  }

  // True si `party` alegó Y proveyó evidencia de `fact` (ambos actos, no
  // alcanza con uno solo — requisito de "pleading" del paper).
  hasAllegeAndEvidence(fact, party) {
    let alleged = false;
    let evidenced = false;
    for (const e of this.entries) {
      if (e.fact !== fact || e.party !== party) continue;
      if (e.action === FactAction.ALLEGE) alleged = true;
      else if (e.action === FactAction.PROVIDE_EVIDENCE) evidenced = true;
    }
    return alleged && evidenced;
  }

  // True si `party` admitió `fact` (para que le sirva a la contraria, se
  // consulta con opposite(party) desde el llamador).
  hasAdmission(fact, party) {
    return this.entries.some(
      (e) => e.action === FactAction.ADMISSION && e.fact === fact && e.party === party
    );
  }

  // True si el juez determinó `fact` como plausible (party=null).
  isPlausible(fact) {
    return this.entries.some((e) => e.action === FactAction.PLAUSIBLE && e.fact === fact);
  }
}

export class TraceStep {
  constructor({ kind, actor = null, subject, against = null }) {
    this.kind = kind;
    this.actor = actor;
    this.subject = subject;
    this.against = against;
  }
}

export class ProofResult {
  constructor({ goal, party, proved, trace = [] }) {
    this.goal = goal;
    this.party = party;
    this.proved = proved;
    this.trace = trace;
  }
}
