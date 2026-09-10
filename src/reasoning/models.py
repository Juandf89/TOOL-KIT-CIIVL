"""
models.py — Modelo de datos del motor de razonamiento jurídico derrotable.

Implementación al estilo PROLEG (Satoh, Asai, Kogawa, Kubota, Nakamura,
Nishigai, Shirakawa, Takano — "PROLEG: An Implementation of the Presupposed
Ultimate Fact Theory of Japanese Civil Code by PROLOG Technology", JURISIN
2010): reglas por defecto ("ultimate facts" vs. "intermediate concepts"),
excepciones anidadas, y el requisito procesal de "allege + provide_evidence"
(o admisión de la contraria) antes de poder intentar probar una regla.

Este módulo define solo las estructuras de datos; el algoritmo de prueba
(`prove`) vive en `src.reasoning.engine`.

Contrato de interfaz: las firmas de estas clases están pactadas con el
agente `latio-implementador-integracion-razonamiento`, que las consume en
paralelo. No renombrar ni eliminar campos — solo se admiten adiciones.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import Field

from src.models import StrictModel


class Party(str, Enum):
    """Las dos partes de un proceso civil. `opposite()` vive en engine.py
    para mantener este módulo libre de lógica de negocio."""
    PLAINTIFF = "plaintiff"
    DEFENDANT = "defendant"


class Rule(StrictModel):
    """Una regla `head :- body` del meta-intérprete PROLEG.

    `head` es un "intermediate concept" (p. ej. "cancellation_due_to_sublease");
    cada literal de `body` puede ser a su vez un intermediate concept (si
    tiene su propia Rule en el RuleBase) o un "ultimate fact" (si no la
    tiene) — la distinción es estructural, no se anota aquí.
    """
    head: str
    body: list[str] = Field(default_factory=list)
    # futuro enlace a ArticleRecord.uid (src/models.py) cuando exista
    # contenido N2/N3 anotado de los 8 corpus reales — no poblar con datos
    # inventados mientras no exista esa fuente verificada.
    source_uid: Optional[str] = None
    # cita textual cuando no hay source_uid todavía (p. ej.
    # "Art. 612 Código Civil japonés").
    source_note: Optional[str] = None


class ExceptionLink(StrictModel):
    """`exception(rule_head, exception_head)` del paper: si `exception_head`
    se prueba para la parte contraria, `rule_head` deja de estar probado
    aunque su cuerpo se haya probado."""
    rule_head: str
    exception_head: str


class RuleBase(StrictModel):
    id: str
    description: str
    rules: list[Rule] = Field(default_factory=list)
    exceptions: list[ExceptionLink] = Field(default_factory=list)


class FactAction(str, Enum):
    ALLEGE = "allege"
    PROVIDE_EVIDENCE = "provide_evidence"
    ADMISSION = "admission"
    PLAUSIBLE = "plausible"


class FactEntry(StrictModel):
    action: FactAction
    fact: str
    # None es válido únicamente para "plausible": es una determinación del
    # juez sobre el hecho último, no un acto procesal de una parte.
    party: Optional[Party] = None


class FactBase(StrictModel):
    entries: list[FactEntry] = Field(default_factory=list)

    def has_allege_and_evidence(self, fact: str, party: Party) -> bool:
        """True si `party` alegó Y proveyó evidencia de `fact` (ambos actos,
        no alcanza con uno solo — es el requisito de "pleading" del paper)."""
        alleged = any(
            e.action == FactAction.ALLEGE and e.fact == fact and e.party == party
            for e in self.entries
        )
        evidenced = any(
            e.action == FactAction.PROVIDE_EVIDENCE and e.fact == fact and e.party == party
            for e in self.entries
        )
        return alleged and evidenced

    def has_admission(self, fact: str, party: Party) -> bool:
        """True si `party` admitió `fact` (nótese: para que le sirva a la
        parte contraria como prueba, se consulta con `opposite(party)`)."""
        return any(
            e.action == FactAction.ADMISSION and e.fact == fact and e.party == party
            for e in self.entries
        )

    def is_plausible(self, fact: str) -> bool:
        """True si el juez determinó `fact` como plausible (party=None)."""
        return any(
            e.action == FactAction.PLAUSIBLE and e.fact == fact
            for e in self.entries
        )


TraceStepKind = Literal[
    "try_prove",
    "admitted",
    "plausible_true",
    "failed_ultimate_fact",
    "rule_matched",
    "no_rule",
    "alleges_defense",
    "defense_failed",
    "defense_succeeded",
    "proved",
    "failed",
]


class TraceStep(StrictModel):
    kind: TraceStepKind
    actor: Optional[Party] = None
    subject: str
    against: Optional[str] = None


class ProofResult(StrictModel):
    goal: str
    party: Party
    proved: bool
    trace: list[TraceStep] = Field(default_factory=list)
