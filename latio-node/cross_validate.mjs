// cross_validate.mjs — corre el mismo factbase (Apéndice B del paper
// PROLEG, exactamente como en tests/test_reasoning.py del repo Python) por
// AMBOS motores — el Python original (oráculo, invocado vía `python3 -c`
// importando src.reasoning directamente, sin pasar por HTTP) y el server
// Node.js levantado en este mismo proceso — y compara los ProofResult
// campo a campo. También corre el caso CO-256 y varios textos por
// labeling/rules.
//
// Uso: node cross_validate.mjs   (desde /home/claude/latio-node; asume
// que /home/claude/latio existe con el venv/deps de pytest ya instaladas).

import { execFileSync } from "node:child_process";

// app.mjs arranca un servidor apenas se lo importa (lsnode lo exige; ver el
// comentario al final de ese archivo). Acá ese servidor sobra: se lo manda a
// un puerto efímero para que no choque con nada que ya esté escuchando, y el
// script termina con process.exit() explícito, porque si no ese servidor deja
// el proceso vivo para siempre. El import es dinámico para que PORT quede
// fijado ANTES de que app.mjs se evalúe.
process.env.PORT = "0";
const { createApp } = await import("./server/app.mjs");

// La ruta del repo Python y el nombre del intérprete se pueden fijar por
// entorno: en Windows el binario es `python` (no existe `python3`) y el repo
// no está en /home/claude. Sin esto, el script solo corría en un entorno.
const PY_REPO = process.env.LATIO_PY_REPO || "/home/claude/latio";
const PY_BIN = process.env.LATIO_PY_BIN || (process.platform === "win32" ? "python" : "python3");

function runPython(code) {
  const out = execFileSync(PY_BIN, ["-c", code], { cwd: PY_REPO, encoding: "utf-8" });
  return JSON.parse(out);
}

let failures = 0;
function check(label, expected, actual) {
  const a = JSON.stringify(expected);
  const b = JSON.stringify(actual);
  if (a === b) {
    console.log(`OK   ${label}`);
  } else {
    failures++;
    console.log(`FAIL ${label}`);
    console.log(`  python: ${a}`);
    console.log(`  node:   ${b}`);
  }
}

async function main() {
  const app = await createApp();
  const server = app.listen(0);
  const port = server.address().port;
  const base = `http://127.0.0.1:${port}`;

  async function nodeProve(rulebaseId, goal, party, facts) {
    const res = await fetch(`${base}/v1/reasoning/prove`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ rulebase_id: rulebaseId, goal, party, facts }),
    });
    return res.json();
  }

  async function nodePropose(textSpan) {
    const res = await fetch(`${base}/v1/statements/propose`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text_span: textSpan }),
    });
    // Un 429 del limitador devolvía un cuerpo sin los campos esperados y la
    // comparación lo reportaba como "discrepancia con Python", que manda a
    // buscar el bug al lugar equivocado. Acá el limitador no es lo que se
    // está probando: si aparece, hay que decirlo con todas las letras.
    if (!res.ok) {
      throw new Error(
        `el servidor Node respondió ${res.status} en /v1/statements/propose. ` +
        (res.status === 429
          ? "Es el límite de tasa: corré con LATIO_RATE_LIMIT_ENABLED=0, este script no prueba el limitador."
          : "")
      );
    }
    return res.json();
  }

  // ---------------------------------------------------------------------
  // 1) Caso de oro Apéndice B — jp-civil-612-sublease-demo
  // ---------------------------------------------------------------------
  const appendixBFacts = [
    ...[
      "agreement_of_lease_contract",
      "agreement_of_sublease_contract",
      "handover_to_lessee",
      "handover_to_sublessee",
      "using_leased_thing",
      "manifestation_cancellation",
    ].map((fact) => ({ action: "admission", fact, party: "defendant" })),
    { action: "allege", fact: "approval_of_sublease", party: "defendant" },
    { action: "provide_evidence", fact: "approval_of_sublease", party: "defendant" },
    { action: "allege", fact: "approval_before_cancellation", party: "defendant" },
    { action: "provide_evidence", fact: "approval_before_cancellation", party: "defendant" },
    { action: "allege", fact: "fact_of_nonabuse_of_confidence", party: "defendant" },
    { action: "provide_evidence", fact: "fact_of_nonabuse_of_confidence", party: "defendant" },
    { action: "plausible", fact: "fact_of_nonabuse_of_confidence", party: null },
    { action: "allege", fact: "fact_of_abuse_of_confidence", party: "plaintiff" },
    { action: "provide_evidence", fact: "fact_of_abuse_of_confidence", party: "plaintiff" },
    { action: "plausible", fact: "fact_of_abuse_of_confidence", party: null },
  ];

  const pyFactbaseCode = `
import json as _json
entries = _json.loads(r'''${JSON.stringify(appendixBFacts)}''')
`;

  for (const [goal, party] of [
    ["contract_end", "plaintiff"],
    ["cancellation_due_to_sublease", "plaintiff"],
    ["get_approval_of_sublease", "defendant"],
    ["nonabuse_of_confidence", "defendant"],
    ["abuse_of_confidence", "plaintiff"],
  ]) {
    const pyCode = `
import json
from src.reasoning.engine import prove
from src.reasoning.models import FactAction, FactBase, FactEntry, Party
from src.reasoning.rulesets import RULEBASES

RULEBASE = RULEBASES["jp-civil-612-sublease-demo"]
${pyFactbaseCode}
factbase = FactBase(entries=[FactEntry(action=FactAction(e["action"]), fact=e["fact"], party=Party(e["party"]) if e["party"] else None) for e in entries])
result = prove("${goal}", Party("${party}"), RULEBASE, factbase)
print(json.dumps({"goal": result.goal, "party": result.party.value, "proved": result.proved, "trace_length": len(result.trace)}))
`;
    const pyResult = runPython(pyCode);
    const nodeResult = await nodeProve("jp-civil-612-sublease-demo", goal, party, appendixBFacts);
    check(
      `prove(${goal}, ${party}) [apendice B]`,
      pyResult,
      { goal: nodeResult.goal, party: nodeResult.party, proved: nodeResult.proved, trace_length: nodeResult.trace.length }
    );
  }

  // ---------------------------------------------------------------------
  // 2) CO-256 visitas — un par de escenarios simples (derecho por defecto
  //    del progenitor, y su derrota por victimario condenado).
  // ---------------------------------------------------------------------
  const co256Cases = [
    {
      label: "derecho_de_visitas_progenitor sin excepción",
      facts: [
        { action: "admission", fact: "no_tiene_cuidado_personal_hijos", party: "defendant" },
      ],
      goal: "derecho_de_visitas_progenitor",
      party: "plaintiff",
    },
    {
      label: "derecho_de_visitas_progenitor derrotado por victimario condenado",
      facts: [
        { action: "admission", fact: "no_tiene_cuidado_personal_hijos", party: "defendant" },
        ...["condena_ejecutoriada_violencia_intrafamiliar", "es_victima_o_hermano_del_solicitante"].flatMap((fact) => [
          { action: "allege", fact, party: "defendant" },
          { action: "provide_evidence", fact, party: "defendant" },
          { action: "plausible", fact, party: null },
        ]),
      ],
      goal: "derecho_de_visitas_progenitor",
      party: "plaintiff",
    },
  ];

  for (const { label, facts, goal, party } of co256Cases) {
    const pyCode = `
import json
from src.reasoning.engine import prove
from src.reasoning.models import FactAction, FactBase, FactEntry, Party
from src.reasoning.rulesets import RULEBASES

RULEBASE = RULEBASES["co-civil-256-visitas"]
import json as _json
entries = _json.loads(r'''${JSON.stringify(facts)}''')
factbase = FactBase(entries=[FactEntry(action=FactAction(e["action"]), fact=e["fact"], party=Party(e["party"]) if e["party"] else None) for e in entries])
result = prove("${goal}", Party("${party}"), RULEBASE, factbase)
print(json.dumps({"proved": result.proved, "trace_length": len(result.trace)}))
`;
    const pyResult = runPython(pyCode);
    const nodeResult = await nodeProve("co-civil-256-visitas", goal, party, facts);
    check(`prove co-256: ${label}`, pyResult, { proved: nodeResult.proved, trace_length: nodeResult.trace.length });
  }

  // ---------------------------------------------------------------------
  // 3) labeling/rules — proposeFromText sobre varios textos.
  // ---------------------------------------------------------------------
  // OJO: los cinco primeros textos están escritos SIN TILDES, y durante
  // mucho tiempo fueron los únicos. Eso ocultó la peor divergencia que tuvo
  // este puerto: `\b` en JavaScript es ASCII, así que /podr[áa]\b/ nunca
  // matchea "podrá", mientras que en Python sí. Con texto sin tildes los dos
  // motores coincidían siempre; con texto real, ~2.000 artículos quedaban
  // clasificados distinto. Los textos ACENTUADOS de abajo existen para que
  // esa clase de error no pueda volver a esconderse: no los quites ni los
  // "normalices" sacándoles las tildes.
  const textos = [
    "Salvo que se pruebe lo contrario, se presume de derecho que el deudor conocia la obligacion.",
    "Se entiende por contrato de arrendamiento aquel en que una parte se obliga a conceder el uso de una cosa.",
    "Lo dispuesto en el articulo 5 rige tambien para los contratos de subarrendamiento.",
    "El notario debera verificar la identidad de las partes cuando se trate de un acto de disposicion.",
    "Queda prohibido el pacto que renuncie a este derecho; sera nulo cualquier pacto en contrario.",
    // Con tilde y en singular: el caso exacto que el `\b` de JS no ve.
    "El juez podrá reducir la pena cuando concurran atenuantes.",
    "El vendedor no podrá retener la cosa vendida.",
    "El comprador deberá pagar el precio en el plazo estipulado.",
    // Presente de indicativo (Vélez 1869, Perú, Brasil).
    "El locatario puede subarrendar en todo o en parte la cosa arrendada.",
    "El legado en dinero debe ser pagado en esta especie.",
    "El plazo del arrendamiento no puede exceder de diez años.",
    // Negación que invierte el signo, y cuantificador negativo.
    "El apoderado no está obligado a rendir cuentas de los frutos percibidos.",
    "Nadie puede construir cerca de una pared ajena hornos ni chimeneas.",
    "Únicamente en los siguientes casos procede la acción.",
  ];

  for (const texto of textos) {
    const pyCode = `
import json
from src.labeling.rules import propose_from_text

result = propose_from_text(${JSON.stringify(texto)})
print(result.model_dump_json())
`;
    const pyResult = runPython(pyCode);
    const nodeResult = await nodePropose(texto);
    // Comparamos solo el subconjunto de campos determinísticos de más alto
    // valor (evita falsos negativos por diferencias triviales de orden en
    // listas de "notes" que no cambian el resultado jurídico).
    const project = (o) => ({
      statement_type: o.statement_type,
      structure: o.structure,
      deontic_modality: o.deontic_modality,
      addressee: o.addressee,
      antecedent_operator: o.antecedent_operator,
      exception_present: o.exception_present,
      exception_marker: o.exception_marker,
      exception_scope: o.exception_scope,
      presumption_rebuttable: o.presumption_rebuttable,
    });
    check(`propose: "${texto.slice(0, 40)}..."`, project(pyResult), project(nodeResult));
  }

  await new Promise((resolve) => server.close(resolve));

  console.log("");
  if (failures > 0) {
    console.log(`${failures} discrepancia(s) encontradas.`);
    process.exit(1);
  } else {
    console.log("Todos los casos coinciden entre Python (oráculo) y Node.");
    process.exit(0);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
