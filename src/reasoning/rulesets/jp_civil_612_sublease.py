"""
jp_civil_612_sublease.py — Ruleset de referencia del motor de razonamiento.

Codifica el ejemplo completo del Apéndice A de Satoh et al. 2010 ("PROLEG:
An Implementation of the Presupposed Ultimate Fact Theory of Japanese Civil
Code by PROLOG Technology", JURISIN 2010): la cancelación de un contrato de
arrendamiento por subarriendo no autorizado, bajo el Art. 612 del Código
Civil japonés, con sus dos defensas (aprobación del subarriendo; ausencia de
abuso de confianza) y la contra-excepción de esta última (abuso de
confianza).

Es el primer y único ruleset de contenido jurídico real del motor: se eligió
deliberadamente el ejemplo del propio paper —citable, y con una traza de
ejecución completa en el Apéndice B que sirve de test de oro— en vez de
inventar contenido latinoamericano no verificado. Los 8 corpus reales
(LATAM) no tienen todavía anotación N2/N3 suficiente para alimentar un
ruleset de este tipo; cuando la haya, sus Rule.source_uid podrán enlazar a
ArticleRecord.uid (src/models.py).

Estructura lógica (jerarquía de reglas y excepciones):

    contract_end
      :- cancellation_due_to_sublease
      :- expiration_of_the_term_of_the_lease_contract

    cancellation_due_to_sublease
      :- agreement_of_lease_contract,
         handover_to_lessee,
         agreement_of_sublease_contract,
         handover_to_sublessee,
         using_leased_thing,
         manifestation_cancellation
      excepción: get_approval_of_sublease
      excepción: nonabuse_of_confidence

    get_approval_of_sublease
      :- approval_of_sublease, approval_before_cancellation

    nonabuse_of_confidence
      :- fact_of_nonabuse_of_confidence
      excepción: abuse_of_confidence

    abuse_of_confidence
      :- fact_of_abuse_of_confidence

Los seis literales de cancellation_due_to_sublease (agreement_of_lease_contract,
handover_to_lessee, agreement_of_sublease_contract, handover_to_sublessee,
using_leased_thing, manifestation_cancellation — nombres exactos del Apéndice A
del paper, no paráfrasis), approval_of_sublease, approval_before_cancellation,
fact_of_nonabuse_of_confidence y fact_of_abuse_of_confidence son "ultimate
facts" (no tienen Rule propia):
solo se prueban por admisión de la contraria o por determinación de
plausibilidad del juez — nunca por el solo alegato+evidencia de quien los
invoca. expiration_of_the_term_of_the_lease_contract se deja como ultimate
fact alternativo (vía de terminación del contrato no ejercida en el
escenario del Apéndice B, pero parte del ruleset del paper).
"""

from __future__ import annotations

from src.reasoning.models import ExceptionLink, Rule, RuleBase

_SOURCE_NOTE = "Art. 612 Código Civil japonés — Satoh et al., JURISIN 2010"

RULEBASE = RuleBase(
    id="jp-civil-612-sublease-demo",
    description=(
        "Cancelación de arrendamiento por subarriendo no autorizado "
        "(Art. 612 Código Civil japonés) — ejemplo de referencia del paper "
        "PROLEG (Satoh et al., JURISIN 2010), Apéndice A."
    ),
    rules=[
        Rule(
            head="contract_end",
            body=["cancellation_due_to_sublease"],
            source_note=_SOURCE_NOTE,
        ),
        Rule(
            head="contract_end",
            body=["expiration_of_the_term_of_the_lease_contract"],
            source_note=_SOURCE_NOTE,
        ),
        Rule(
            head="cancellation_due_to_sublease",
            body=[
                "agreement_of_lease_contract",
                "handover_to_lessee",
                "agreement_of_sublease_contract",
                "handover_to_sublessee",
                "using_leased_thing",
                "manifestation_cancellation",
            ],
            source_note=_SOURCE_NOTE,
        ),
        Rule(
            head="get_approval_of_sublease",
            body=["approval_of_sublease", "approval_before_cancellation"],
            source_note=_SOURCE_NOTE,
        ),
        Rule(
            head="nonabuse_of_confidence",
            body=["fact_of_nonabuse_of_confidence"],
            source_note=_SOURCE_NOTE,
        ),
        Rule(
            head="abuse_of_confidence",
            body=["fact_of_abuse_of_confidence"],
            source_note=_SOURCE_NOTE,
        ),
    ],
    exceptions=[
        ExceptionLink(
            rule_head="cancellation_due_to_sublease",
            exception_head="get_approval_of_sublease",
        ),
        ExceptionLink(
            rule_head="cancellation_due_to_sublease",
            exception_head="nonabuse_of_confidence",
        ),
        ExceptionLink(
            rule_head="nonabuse_of_confidence",
            exception_head="abuse_of_confidence",
        ),
    ],
)
