// tests/unit.test.mjs — subconjunto representativo de
// tests/test_labeling_rules.py, tests/test_reasoning.py,
// tests/test_reasoning_co_256.py y tests/test_models.py (Python), portado
// a node:test. No es un clon 1:1 de los 92 tests originales (ver
// cross_validate.mjs para la verificación exhaustiva contra el oráculo
// Python real) — es la red de seguridad rápida para correr en cada cambio
// sin depender de que el repo Python esté disponible.

import test from "node:test";
import assert from "node:assert/strict";

import { proposeFromText } from "../server/labeling/rules.mjs";
import { prove } from "../server/reasoning/engine.mjs";
import { RULEBASES } from "../server/reasoning/rulesets/index.mjs";
import { FactBase, FactEntry, Party, FactAction } from "../server/reasoning/models.mjs";
import {
  ValidationError,
  makeExceptionInfo,
  makePresumptionInfo,
  makeGeneralityProxies,
  makeNormativeStatement,
} from "../server/models.mjs";

// ---------------------------------------------------------------------
// labeling/rules — espejo de tests/test_labeling_rules.py
// ---------------------------------------------------------------------

test("antecedent_operator: siempre_que detectado", () => {
  const p = proposeFromText("Siempre que el comprador pague el precio, el vendedor entrega la cosa.");
  assert.equal(p.antecedentOperator, "siempre_que");
});

// Espejo de los tests deónticos de tests/test_labeling_rules.py. Sin estos,
// la paridad Python/Node en la detección de Von Wright dependía de revisión
// manual en cada cambio, que es exactamente como se cuela una regresión.
test("deontica: presente de indicativo, no solo futuro", () => {
  assert.equal(
    proposeFromText("El legado en dinero debe ser pagado en esta especie.").deonticModality,
    "obligacion");
  assert.equal(
    proposeFromText("El locatario puede subarrendar en todo o en parte la cosa arrendada.").deonticModality,
    "permiso");
  assert.equal(
    proposeFromText("El plazo del arrendamiento no puede exceder de diez años.").deonticModality,
    "prohibicion");
});

test("deontica: la negacion no se lee como la modalidad afirmativa", () => {
  assert.equal(
    proposeFromText("El apoderado no está obligado a rendir cuentas de los frutos percibidos.").deonticModality,
    "ninguno");
  assert.equal(
    proposeFromText("El usufructuario no tiene derecho a pedir cosa alguna por las mejoras.").deonticModality,
    "ninguno");
});

test("deontica: cuantificador negativo es prohibicion aunque el verbo sea afirmativo", () => {
  assert.equal(
    proposeFromText("Nadie puede construir cerca de una pared ajena hornos ni chimeneas.").deonticModality,
    "prohibicion");
  assert.equal(
    proposeFromText("Ninguno de los comuneros podrá inquietar a los otros en sus porciones.").deonticModality,
    "prohibicion");
});

test("deontica: 'puede ser' descriptivo no es permiso", () => {
  assert.equal(
    proposeFromText("La aceptación puede ser expresa o tácita.").deonticModality,
    "ninguno");
});

// Espejo de los tests de negación, perífrasis y portugués de
// tests/test_labeling_rules.py.
const deontica = (t) => proposeFromText(t).deonticModality;

test("deontica: negacion con pronombre intermedio es prohibicion", () => {
  assert.equal(deontica("No se puede empeñar una cosa, sino por persona que tenga facultad de enajenarla."), "prohibicion");
  assert.equal(deontica("Si fueren varios los propietarios, no se podrán imponer servidumbres."), "prohibicion");
  assert.equal(deontica("O direito de preferência não se pode ceder nem passa aos herdeiros."), "prohibicion");
});

test("deontica: 'no deber' + infinitivo es prohibicion; sin infinitivo, no se adeuda", () => {
  assert.equal(deontica("Las molestias por actividades en inmuebles vecinos no deben exceder la normal tolerancia."), "prohibicion");
  assert.equal(deontica("Não devem casar os ascendentes com os descendentes."), "prohibicion");
  assert.equal(deontica("No se deben intereses de los intereses."), "ninguno");
  assert.notEqual(deontica("El dueño no debe responder por el hecho del tercero."), "prohibicion");
});

test("deontica: formas perifrasticas en presente y futuro", () => {
  assert.equal(deontica("El gestor estará obligado a pagarla, aunque hubiese perdido."), "obligacion");
  assert.equal(deontica("El vendedor será obligado a reembolsar al comprador."), "obligacion");
  assert.equal(deontica("Los usuarios quedan obligados a todos los gastos de cultivo."), "obligacion");
  assert.equal(deontica("Es lícito a cualquier persona apropiarse los enjambres."), "permiso");
  assert.equal(deontica("No es lícito al propietario hacer cosa alguna que perjudique al usufructuario."), "prohibicion");
  assert.notEqual(deontica("Nadie está obligado a vender, excepto que se encuentre sometido a una necesidad jurídica."), "obligacion");
  assert.equal(proposeFromText("El fiduciario tiene derecho al reembolso de los gastos.").hohfeldianPosition, "derecho_subjetivo");
});

test("presuncion absoluta con otras redacciones", () => {
  for (const texto of [
    "Se presume, sin admitirse prueba en contrario, que toda persona tiene conocimiento del contenido de las inscripciones.",
    "El reglamento se presume conocido por todo propietario sin admitir prueba en contrario.",
    "El error en materia de derecho constituye una presunción de mala fe, que no admite prueba en contrario.",
  ]) {
    const p = proposeFromText(texto);
    assert.equal(p.statementType, "presuncion", texto);
    assert.equal(p.presumptionRebuttable, false, texto);
  }
  assert.equal(proposeFromText("Se presume la buena fe del poseedor, salvo prueba en contrario.").presumptionRebuttable, true);
});

test("portugues: modales en todas sus formas", () => {
  const casos = {
    "O herdeiro pode demandar o reconhecimento de seu direito sucessório.": "permiso",
    "Podem os nubentes requerer prazo razoável para fazer prova contrária.": "permiso",
    "Qualquer dos nubentes poderá acrescer ao seu o sobrenome do outro.": "permiso",
    "Pode-se exigir que cesse a ameaça a direito da personalidade.": "permiso",
    "É lícito às partes fixar o preço em função de índices.": "permiso",
    "O instrumento do penhor deverá ser levado a registro.": "obligacion",
    "O mutuário é obrigado a restituir ao mutuante o que dele recebeu.": "obligacion",
    "O devedor não poderá alienar os animais empenhados.": "prohibicion",
    "Não pode o credor exigir indenização suplementar.": "prohibicion",
    "É vedada contribuição que consista em prestação de serviços.": "prohibicion",
    "Não é lícito encostar à parede divisória chaminés.": "prohibicion",
    "Ninguém pode ser constrangido a submeter-se a tratamento médico.": "prohibicion",
    "Desembarcadas as mercadorias, o transportador não é obrigado a dar aviso ao destinatário.": "ninguno",
    "A dispensa da colação pode ser outorgada pelo doador em testamento.": "ninguno",
  };
  for (const [texto, esperado] of Object.entries(casos)) assert.equal(deontica(texto), esperado, texto);
});

test("portugues: direito subjetivo, potestad del juiz, excepcion y presuncion", () => {
  assert.equal(proposeFromText("O possuidor de título ao portador tem direito à prestação nele indicada.").hohfeldianPosition, "derecho_subjetivo");
  assert.equal(proposeFromText("Aquele que restituir a coisa achada terá direito a uma recompensa.").hohfeldianPosition, "derecho_subjetivo");
  const juiz = proposeFromText("Para fiscalização dos atos do tutor, pode o juiz nomear um protutor.");
  assert.equal(juiz.addressee, "juez");
  assert.equal(juiz.hohfeldianPosition, "potestad");
  const exc = proposeFromText("O devedor responde pelos prejuízos, salvo se provar caso fortuito.");
  assert.equal(exc.exceptionPresent, true);
  assert.equal(exc.exceptionMarker, "salvo se");
  const pres = proposeFromText("Presumem-se verdadeiras as declarações constantes de documentos assinados.");
  assert.equal(pres.statementType, "presuncion");
  assert.equal(pres.presumptionRebuttable, true);
});

test("portugues: letra inicial tachada se une a su palabra", () => {
  assert.equal(deontica("§ 1 o ~~N~~ ão pode o devedor obrigar o credor a receber parte."), "prohibicion");
  assert.equal(proposeFromText("§ 1 o ~~S~~ alvo quando exigidos por lei outros requisitos, a escritura é válida.").exceptionPresent, true);
});

test("portugues: no contamina el castellano", () => {
  assert.equal(proposeFromText("El juez o tribunal resolverá lo que corresponda.").addressee, "juez");
  assert.equal(proposeFromText("Los frutos se deben desde que se interpuso la demanda.").antecedentOperator, "ninguno_explicito");
});

test("hohfeld: 'tiene derecho a' es derecho_subjetivo, no privilegio", () => {
  const p = proposeFromText("El arrendatario tiene derecho a la terminación del arrendamiento.");
  assert.equal(p.hohfeldianPosition, "derecho_subjetivo");
  assert.equal(p.deonticModality, "ninguno");
});

test("hohfeld: 'no tiene derecho a' no afirma derecho subjetivo", () => {
  const p = proposeFromText("El usufructuario no tiene derecho a pedir cosa alguna por las mejoras.");
  assert.notEqual(p.hohfeldianPosition, "derecho_subjetivo");
});

test("deontica: 'libremente' solo no es permiso", () => {
  assert.equal(
    proposeFromText("Las partes interesadas, siendo capaces de disponer libremente de lo suyo, consienten en darla por nula.").deonticModality,
    "ninguno");
});

test("deontica: la nulidad no es prohibicion", () => {
  assert.equal(
    proposeFromText("Es nula la donación que comprenda la totalidad de los bienes del donante.").deonticModality,
    "ninguno");
});

test("antecedent_operator: ausencia de marcador es ninguno_explicito, no undetermined", () => {
  const p = proposeFromText("El comprador debe pagar el precio en el plazo estipulado.");
  assert.equal(p.antecedentOperator, "ninguno_explicito");
});

test("excepcion: interna sin referencia a otro articulo", () => {
  const p = proposeFromText("El deudor debe restituir la cosa, salvo que haya perecido por caso fortuito.");
  assert.equal(p.exceptionPresent, true);
  assert.equal(p.exceptionMarker, "salvo que");
  assert.equal(p.exceptionScope, "interna");
});

test("excepcion: por_remision con referencia numerica", () => {
  const p = proposeFromText("El plazo corre desde la notificación, salvo lo dispuesto en el artículo 45.");
  assert.equal(p.exceptionPresent, true);
  assert.equal(p.exceptionScope, "por_remision");
});

test("excepcion: sin marcador, exception_present false", () => {
  const p = proposeFromText("El comprador debe pagar el precio en el plazo estipulado.");
  assert.equal(p.exceptionPresent, false);
  assert.equal(p.exceptionMarker, null);
  assert.equal(p.exceptionScope, null);
});

test("presuncion de derecho: irrebuttable", () => {
  const p = proposeFromText("Se presume de derecho que el menor de diez años es incapaz.");
  assert.equal(p.statementType, "presuncion");
  assert.equal(p.presumptionRebuttable, false);
  assert.equal(p.structure, "supuesto_consecuencia");
});

test("presuncion legal: rebuttable", () => {
  const p = proposeFromText("Se presume la buena fe del poseedor.");
  assert.equal(p.statementType, "presuncion");
  assert.equal(p.presumptionRebuttable, true);
});

test("remision corta al inicio detectada", () => {
  const p = proposeFromText("Lo dispuesto en el artículo 120 se aplica a este contrato.");
  assert.equal(p.statementType, "remision");
  assert.equal(p.structure, "remision_pura");
});

// ---------------------------------------------------------------------
// reasoning/engine — caso de oro Apéndice B (jp-civil-612-sublease-demo)
// ---------------------------------------------------------------------

function appendixBFactbase() {
  const entries = [];
  for (const fact of [
    "agreement_of_lease_contract",
    "agreement_of_sublease_contract",
    "handover_to_lessee",
    "handover_to_sublessee",
    "using_leased_thing",
    "manifestation_cancellation",
  ]) {
    entries.push(new FactEntry({ action: FactAction.ADMISSION, fact, party: Party.DEFENDANT }));
  }
  for (const fact of ["approval_of_sublease", "approval_before_cancellation"]) {
    entries.push(new FactEntry({ action: FactAction.ALLEGE, fact, party: Party.DEFENDANT }));
    entries.push(new FactEntry({ action: FactAction.PROVIDE_EVIDENCE, fact, party: Party.DEFENDANT }));
  }
  entries.push(new FactEntry({ action: FactAction.ALLEGE, fact: "fact_of_nonabuse_of_confidence", party: Party.DEFENDANT }));
  entries.push(new FactEntry({ action: FactAction.PROVIDE_EVIDENCE, fact: "fact_of_nonabuse_of_confidence", party: Party.DEFENDANT }));
  entries.push(new FactEntry({ action: FactAction.PLAUSIBLE, fact: "fact_of_nonabuse_of_confidence", party: null }));
  entries.push(new FactEntry({ action: FactAction.ALLEGE, fact: "fact_of_abuse_of_confidence", party: Party.PLAINTIFF }));
  entries.push(new FactEntry({ action: FactAction.PROVIDE_EVIDENCE, fact: "fact_of_abuse_of_confidence", party: Party.PLAINTIFF }));
  entries.push(new FactEntry({ action: FactAction.PLAUSIBLE, fact: "fact_of_abuse_of_confidence", party: null }));
  return new FactBase({ entries });
}

test("apendice B: contract_end se prueba para plaintiff", () => {
  const rulebase = RULEBASES["jp-civil-612-sublease-demo"];
  const result = prove("contract_end", Party.PLAINTIFF, rulebase, appendixBFactbase());
  assert.equal(result.proved, true);
  assert.equal(result.goal, "contract_end");
  assert.equal(result.party, Party.PLAINTIFF);
  assert.ok(result.trace.length > 0);
});

test("apendice B: cancellation_due_to_sublease se prueba directamente", () => {
  const rulebase = RULEBASES["jp-civil-612-sublease-demo"];
  const result = prove("cancellation_due_to_sublease", Party.PLAINTIFF, rulebase, appendixBFactbase());
  assert.equal(result.proved, true);
});

test("apendice B: get_approval_of_sublease falla (alegado pero no admitido ni plausible)", () => {
  const rulebase = RULEBASES["jp-civil-612-sublease-demo"];
  const result = prove("get_approval_of_sublease", Party.DEFENDANT, rulebase, appendixBFactbase());
  assert.equal(result.proved, false);
  assert.ok(result.trace.some((s) => s.kind === "failed_ultimate_fact"));
});

test("apendice B: nonabuse_of_confidence derrotado por abuse_of_confidence", () => {
  const rulebase = RULEBASES["jp-civil-612-sublease-demo"];
  const factbase = appendixBFactbase();

  const isolated = prove("nonabuse_of_confidence", Party.DEFENDANT, rulebase, factbase);
  assert.equal(isolated.proved, false);
  assert.ok(isolated.trace.some((s) => s.kind === "defense_succeeded"));

  const abuse = prove("abuse_of_confidence", Party.PLAINTIFF, rulebase, factbase);
  assert.equal(abuse.proved, true);
});

// ---------------------------------------------------------------------
// reasoning: CO-256 visitas
// ---------------------------------------------------------------------

test("CO-256: derecho de visitas del progenitor sin excepcion se prueba", () => {
  const rulebase = RULEBASES["co-civil-256-visitas"];
  const factbase = new FactBase({
    entries: [
      new FactEntry({ action: FactAction.ADMISSION, fact: "no_tiene_cuidado_personal_hijos", party: Party.DEFENDANT }),
    ],
  });
  const result = prove("derecho_de_visitas_progenitor", Party.PLAINTIFF, rulebase, factbase);
  assert.equal(result.proved, true);
});

test("CO-256: derecho de visitas derrotado por victimario condenado (excepcion absoluta)", () => {
  const rulebase = RULEBASES["co-civil-256-visitas"];
  const excepcion = [
    "condena_ejecutoriada_violencia_intrafamiliar",
    "es_victima_o_hermano_del_solicitante",
  ].flatMap((fact) => [
    new FactEntry({ action: FactAction.ALLEGE, fact, party: Party.DEFENDANT }),
    new FactEntry({ action: FactAction.PROVIDE_EVIDENCE, fact, party: Party.DEFENDANT }),
    new FactEntry({ action: FactAction.PLAUSIBLE, fact, party: null }),
  ]);
  const factbase = new FactBase({
    entries: [
      new FactEntry({ action: FactAction.ADMISSION, fact: "no_tiene_cuidado_personal_hijos", party: Party.DEFENDANT }),
      ...excepcion,
    ],
  });
  const result = prove("derecho_de_visitas_progenitor", Party.PLAINTIFF, rulebase, factbase);
  assert.equal(result.proved, false);
});

// ---------------------------------------------------------------------
// models.mjs — espejo parcial de tests/test_models.py
// ---------------------------------------------------------------------

test("ExceptionInfo: present=True exige scope", () => {
  assert.throws(() => makeExceptionInfo({ present: true, scope: null }), ValidationError);
});

test("ExceptionInfo: present=False no admite marker ni scope", () => {
  assert.throws(() => makeExceptionInfo({ present: false, marker: "salvo que" }), ValidationError);
});

test("PresumptionInfo: irrebuttable no admite burden_shifts_to distinto de ninguno", () => {
  assert.throws(
    () => makePresumptionInfo({ rebuttable: false, burdenShiftsTo: "partes" }),
    ValidationError
  );
});

test("GeneralityProxies: has_enumeration=True exige enumeration_closed", () => {
  assert.throws(
    () => makeGeneralityProxies({ nConditions: 1, hasEnumeration: true, enumerationClosed: null }),
    ValidationError
  );
});

test("NormativeStatement: combinacion ilegal statement_type/structure", () => {
  assert.throws(() => {
    makeNormativeStatement({
      statementId: 0,
      spanType: "articulo_completo",
      textSpan: "x",
      statementType: "definicion",
      structure: "supuesto_consecuencia",
      deonticModality: "ninguno",
      hohfeldianPosition: "ninguno",
      derogability: "indeterminada",
      addressee: "partes",
      antecedentOperator: "ninguno_explicito",
      exception: makeExceptionInfo(),
      generality: makeGeneralityProxies({ nConditions: 0 }),
    });
  }, ValidationError);
});

test("NormativeStatement: span_type distinto de articulo_completo exige span_index", () => {
  assert.throws(() => {
    makeNormativeStatement({
      statementId: 0,
      spanType: "parrafo",
      textSpan: "x",
      statementType: "regla",
      structure: "supuesto_consecuencia",
      deonticModality: "obligacion",
      hohfeldianPosition: "ninguno",
      derogability: "indeterminada",
      addressee: "partes",
      antecedentOperator: "ninguno_explicito",
      exception: makeExceptionInfo(),
      generality: makeGeneralityProxies({ nConditions: 1 }),
    });
  }, ValidationError);
});

test("NormativeStatement: caso valido calcula generality_level y derogability_marker_detected", () => {
  const stmt = makeNormativeStatement({
    statementId: 0,
    spanType: "articulo_completo",
    textSpan: "No podrán renunciar las partes a este derecho.",
    statementType: "regla",
    structure: "supuesto_consecuencia",
    deonticModality: "prohibicion",
    hohfeldianPosition: "ninguno",
    derogability: "inderogable",
    addressee: "partes",
    antecedentOperator: "ninguno_explicito",
    exception: makeExceptionInfo(),
    generality: makeGeneralityProxies({ nConditions: 1 }),
  });
  assert.equal(stmt.generalityLevel, "intermedia");
  assert.equal(stmt.derogabilityMarkerDetected, true);
});
