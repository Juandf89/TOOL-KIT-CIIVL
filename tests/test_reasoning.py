"""test_reasoning.py — test de oro del motor de razonamiento (src/reasoning).

Reproduce el escenario del Apéndice A/B de Satoh et al. 2010 ("PROLEG: An
Implementation of the Presupposed Ultimate Fact Theory of Japanese Civil
Code by PROLOG Technology", JURISIN 2010):

  * El demandado (defendant) ADMITE las 6 condiciones del cuerpo de
    `cancellation_due_to_sublease` -> esa regla se prueba para plaintiff.
  * El demandado alega defensa `get_approval_of_sublease`: alega + provee
    evidencia de `approval_of_sublease` y `approval_before_cancellation`,
    pero nadie los admite ni el juez los declara plausibles -> ambos
    ultimate facts fallan -> `get_approval_of_sublease` falla como defensa.
  * El demandado alega defensa `nonabuse_of_confidence`: alega + provee
    evidencia de `fact_of_nonabuse_of_confidence`, y ADEMÁS el juez lo
    declara plausible -> `nonabuse_of_confidence` se prueba...
  * ...pero el demandante contraataca con la excepción `abuse_of_confidence`
    de esa misma defensa: alega + provee evidencia de
    `fact_of_abuse_of_confidence`, y también hay determinación de
    plausibilidad -> `abuse_of_confidence` se prueba -> derrota a
    `nonabuse_of_confidence` como defensa.
  * Ninguna defensa del demandado sobrevive -> `cancellation_due_to_sublease`
    queda probada -> `contract_end` se prueba para el demandante.
"""

from __future__ import annotations

from src.reasoning.engine import prove
from src.reasoning.models import FactAction, FactBase, FactEntry, Party
from src.reasoning.rulesets import RULEBASES

RULEBASE = RULEBASES["jp-civil-612-sublease-demo"]

# Los 6 ultimate facts que componen cancellation_due_to_sublease, según el
# Apéndice A del paper.
_CANCELLATION_CONDITIONS = [
    "agreement_of_lease_contract",
    "agreement_of_sublease_contract",
    "handover_to_lessee",
    "handover_to_sublessee",
    "using_leased_thing",
    "manifestation_cancellation",
]


def _appendix_b_factbase() -> FactBase:
    entries: list[FactEntry] = []

    # El demandado admite las 6 condiciones de cancellation_due_to_sublease.
    for fact in _CANCELLATION_CONDITIONS:
        entries.append(FactEntry(action=FactAction.ADMISSION, fact=fact, party=Party.DEFENDANT))

    # Defensa 1: get_approval_of_sublease. El demandado alega y provee
    # evidencia de ambos ultimate facts de su cuerpo, pero nadie los admite
    # ni el juez los declara plausibles -> la defensa debe fallar.
    for fact in ("approval_of_sublease", "approval_before_cancellation"):
        entries.append(FactEntry(action=FactAction.ALLEGE, fact=fact, party=Party.DEFENDANT))
        entries.append(FactEntry(action=FactAction.PROVIDE_EVIDENCE, fact=fact, party=Party.DEFENDANT))

    # Defensa 2: nonabuse_of_confidence. El demandado alega + provee
    # evidencia, y el juez lo declara plausible -> la defensa se prueba...
    entries.append(FactEntry(action=FactAction.ALLEGE, fact="fact_of_nonabuse_of_confidence", party=Party.DEFENDANT))
    entries.append(FactEntry(action=FactAction.PROVIDE_EVIDENCE, fact="fact_of_nonabuse_of_confidence", party=Party.DEFENDANT))
    entries.append(FactEntry(action=FactAction.PLAUSIBLE, fact="fact_of_nonabuse_of_confidence", party=None))

    # ...pero el demandante prueba la excepción abuse_of_confidence: alega +
    # provee evidencia, y también hay determinación de plausibilidad ->
    # deroga a nonabuse_of_confidence como defensa.
    entries.append(FactEntry(action=FactAction.ALLEGE, fact="fact_of_abuse_of_confidence", party=Party.PLAINTIFF))
    entries.append(FactEntry(action=FactAction.PROVIDE_EVIDENCE, fact="fact_of_abuse_of_confidence", party=Party.PLAINTIFF))
    entries.append(FactEntry(action=FactAction.PLAUSIBLE, fact="fact_of_abuse_of_confidence", party=None))

    return FactBase(entries=entries)


def test_appendix_b_contract_end_proved_for_plaintiff():
    factbase = _appendix_b_factbase()

    result = prove("contract_end", Party.PLAINTIFF, RULEBASE, factbase)

    assert result.proved is True
    assert result.goal == "contract_end"
    assert result.party == Party.PLAINTIFF
    assert len(result.trace) > 0


def test_cancellation_due_to_sublease_proved_directly():
    factbase = _appendix_b_factbase()
    result = prove("cancellation_due_to_sublease", Party.PLAINTIFF, RULEBASE, factbase)
    assert result.proved is True


def test_get_approval_of_sublease_fails_alleged_but_not_admitted_or_plausible():
    factbase = _appendix_b_factbase()
    result = prove("get_approval_of_sublease", Party.DEFENDANT, RULEBASE, factbase)
    assert result.proved is False
    kinds = [step.kind for step in result.trace]
    assert "failed_ultimate_fact" in kinds


def test_nonabuse_of_confidence_fails_as_defense_once_abuse_of_confidence_is_proved():
    factbase = _appendix_b_factbase()

    # nonabuse_of_confidence lleva su propia excepción (abuse_of_confidence)
    # registrada a nivel de RuleBase, así que se revisa cada vez que se
    # intenta probar nonabuse_of_confidence — también cuando se prueba de
    # forma aislada, no solo dentro del árbol de cancellation_due_to_sublease.
    # El cuerpo (fact_of_nonabuse_of_confidence) sí se prueba, pero
    # abuse_of_confidence también se prueba para la parte contraria y la
    # deroga: el resultado final es proved=False.
    isolated = prove("nonabuse_of_confidence", Party.DEFENDANT, RULEBASE, factbase)
    assert isolated.proved is False
    isolated_kinds = [step.kind for step in isolated.trace]
    assert "defense_succeeded" in isolated_kinds

    # abuse_of_confidence, probado directamente para el demandante, sí tiene
    # éxito (es lo que lo habilita como excepción derrotante arriba).
    abuse = prove("abuse_of_confidence", Party.PLAINTIFF, RULEBASE, factbase)
    assert abuse.proved is True

    full = prove("cancellation_due_to_sublease", Party.PLAINTIFF, RULEBASE, factbase)
    kinds = [(step.kind, step.subject, step.against) for step in full.trace]
    # nonabuse_of_confidence, invocada como defensa de cancellation_due_to_sublease,
    # ya llega derrotada (por su propia excepción abuse_of_confidence) cuando
    # el motor intenta probarla aquí -> se registra como defense_failed, no
    # defense_succeeded, frente a cancellation_due_to_sublease.
    assert ("defense_failed", "nonabuse_of_confidence", "cancellation_due_to_sublease") in kinds
    assert ("defense_failed", "get_approval_of_sublease", "cancellation_due_to_sublease") in kinds
    # La derrota de nonabuse_of_confidence sí quedó registrada un nivel más
    # abajo, contra su propia excepción.
    assert ("defense_succeeded", "abuse_of_confidence", "nonabuse_of_confidence") in kinds


def test_ultimate_fact_not_proved_by_allege_evidence_alone():
    """Núcleo de la teoría del ultimate fact presupuesto: alegar + proveer
    evidencia NO prueba un hecho por sí solo — hace falta admisión de la
    contraria o plausibilidad del juez."""
    factbase = FactBase(entries=[
        FactEntry(action=FactAction.ALLEGE, fact="approval_of_sublease", party=Party.DEFENDANT),
        FactEntry(action=FactAction.PROVIDE_EVIDENCE, fact="approval_of_sublease", party=Party.DEFENDANT),
    ])
    result = prove("approval_of_sublease", Party.DEFENDANT, RULEBASE, factbase)
    assert result.proved is False


def test_ultimate_fact_proved_by_admission_of_opposite_party():
    factbase = FactBase(entries=[
        FactEntry(action=FactAction.ADMISSION, fact="agreement_of_lease_contract", party=Party.DEFENDANT),
    ])
    result = prove("agreement_of_lease_contract", Party.PLAINTIFF, RULEBASE, factbase)
    assert result.proved is True


def test_rule_without_pleading_never_gets_examined():
    """Si ningún ultimate fact del cuerpo fue alegado+evidenciado ni
    admitido, la regla ni se intenta (gate 'alleged_and_having_evidence')."""
    factbase = FactBase(entries=[])
    result = prove("cancellation_due_to_sublease", Party.PLAINTIFF, RULEBASE, factbase)
    assert result.proved is False
    kinds = [step.kind for step in result.trace]
    assert "no_rule" in kinds


def test_contract_end_not_proved_without_any_facts():
    factbase = FactBase(entries=[])
    result = prove("contract_end", Party.PLAINTIFF, RULEBASE, factbase)
    assert result.proved is False
