"""
engine.py — Meta-intérprete de razonamiento jurídico derrotable.

Reimplementa fielmente el algoritmo de la Fig. 1 de Satoh et al. 2010
("PROLEG: An Implementation of the Presupposed Ultimate Fact Theory of
Japanese Civil Code by PROLOG Technology", JURISIN 2010): `prove(S, P)` y
`alleged_and_having_evidence(S, P)`.

Distinción central del paper (teoría del "ultimate fact" presupuesto):

  * "ultimate fact" — un literal S sin regla cuyo head coincida en el
    RuleBase. Se prueba únicamente por determinación de plausibilidad del
    juez (`factbase.is_plausible`) o por admisión de la parte contraria
    (`factbase.has_admission(S, opposite(party))`). Que una parte lo haya
    alegado y provisto evidencia NO alcanza para probarlo — ese acto es un
    requisito procesal (pleading), no una prueba sustantiva.

  * "intermediate concept" — un literal S con al menos una Rule cuyo head
    coincide. Antes de intentar probar su cuerpo, el tribunal exige que
    TODOS los ultimate facts que aparecen directamente en ese cuerpo hayan
    sido alegados+evidenciados por `party`, o admitidos por la contraria
    (`alleged_and_having_evidence`) — si falta alguno, la regla ni siquiera
    se examina. Si el cuerpo se prueba, se revisan las excepciones
    (`RuleBase.exceptions`) registradas para ese head: si la parte
    contraria logra probar alguna, la regla original queda derrotada
    (default logic / negation as failure sobre la excepción contraria).

Cada paso del algoritmo se registra como un TraceStep estructurado — no solo
texto — para poder tanto renderizar la traza legible del Apéndice B del
paper como consumirla desde una API JSON.
"""

from __future__ import annotations

from src.reasoning.models import (
    FactBase,
    Party,
    ProofResult,
    Rule,
    RuleBase,
    TraceStep,
)


def opposite(party: Party) -> Party:
    """La parte contraria: PLAINTIFF <-> DEFENDANT."""
    return Party.DEFENDANT if party is Party.PLAINTIFF else Party.PLAINTIFF


def _rules_for(head: str, rulebase: RuleBase) -> list[Rule]:
    return [r for r in rulebase.rules if r.head == head]


def _is_ultimate_fact(literal: str, rulebase: RuleBase) -> bool:
    """Un literal es un 'ultimate fact' si ninguna Rule del RuleBase tiene
    ese literal como head — es decir, no hay forma de descomponerlo más."""
    return len(_rules_for(literal, rulebase)) == 0


def _alleged_and_having_evidence(
    rule: Rule, party: Party, rulebase: RuleBase, factbase: FactBase
) -> bool:
    """Gate procesal (pleading) previo a intentar probar el cuerpo de
    `rule` para `party`: cada literal del cuerpo que sea un ultimate fact
    debe estar alegado+evidenciado por `party`, o admitido por la
    contraria. Los literales del cuerpo que sean intermediate concepts no
    se chequean aquí — su propio gate se aplica recursivamente cuando
    `prove()` los alcance."""
    opp = opposite(party)
    for literal in rule.body:
        if not _is_ultimate_fact(literal, rulebase):
            continue
        if factbase.has_allege_and_evidence(literal, party):
            continue
        if factbase.has_admission(literal, opp):
            continue
        return False
    return True


def _prove(goal: str, party: Party, rulebase: RuleBase, factbase: FactBase, trace: list[TraceStep]) -> bool:
    trace.append(TraceStep(kind="try_prove", actor=party, subject=goal))

    rules = _rules_for(goal, rulebase)

    if not rules:
        # ultimate fact: solo lo prueban la plausibilidad del juez o la
        # admisión de la parte contraria — nunca el allege+evidence propio.
        opp = opposite(party)
        if factbase.has_admission(goal, opp):
            trace.append(TraceStep(kind="admitted", actor=opp, subject=goal))
            return True
        if factbase.is_plausible(goal):
            trace.append(TraceStep(kind="plausible_true", subject=goal))
            return True
        trace.append(TraceStep(kind="failed_ultimate_fact", actor=party, subject=goal))
        return False

    # intermediate concept: puede tener varias reglas alternativas (OR);
    # basta con que una de ellas se pruebe y sobreviva a sus excepciones.
    for rule in rules:
        if not _alleged_and_having_evidence(rule, party, rulebase, factbase):
            trace.append(TraceStep(kind="no_rule", actor=party, subject=goal))
            continue

        trace.append(TraceStep(kind="rule_matched", actor=party, subject=goal))

        body_proved = True
        for literal in rule.body:
            if not _prove(literal, party, rulebase, factbase, trace):
                body_proved = False
                break
        if not body_proved:
            continue

        exception_heads = [
            link.exception_head for link in rulebase.exceptions if link.rule_head == goal
        ]
        opp = opposite(party)
        defeated = False
        for exception_head in exception_heads:
            trace.append(
                TraceStep(kind="alleges_defense", actor=opp, subject=exception_head, against=goal)
            )
            if _prove(exception_head, opp, rulebase, factbase, trace):
                trace.append(
                    TraceStep(kind="defense_succeeded", actor=opp, subject=exception_head, against=goal)
                )
                defeated = True
                break
            trace.append(
                TraceStep(kind="defense_failed", actor=opp, subject=exception_head, against=goal)
            )

        if defeated:
            continue

        trace.append(TraceStep(kind="proved", actor=party, subject=goal))
        return True

    trace.append(TraceStep(kind="failed", actor=party, subject=goal))
    return False


def prove(goal: str, party: Party, rulebase: RuleBase, factbase: FactBase) -> ProofResult:
    """Punto de entrada público: intenta probar `goal` para `party` bajo
    `rulebase`/`factbase`, siguiendo fielmente el meta-intérprete de la
    Fig. 1 del paper PROLEG. Devuelve el resultado junto con la traza
    completa de la derivación."""
    trace: list[TraceStep] = []
    proved = _prove(goal, party, rulebase, factbase, trace)
    return ProofResult(goal=goal, party=party, proved=proved, trace=trace)
