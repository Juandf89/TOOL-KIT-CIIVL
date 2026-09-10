"""src/reasoning — motor de razonamiento jurídico derrotable (estilo PROLEG).

Ver:
  * `src.reasoning.models`   — Party, Rule, RuleBase, FactEntry, FactBase,
                                TraceStep, ProofResult.
  * `src.reasoning.engine`   — prove().
  * `src.reasoning.rulesets` — RULEBASES: dict[str, RuleBase].
"""

from src.reasoning.engine import opposite, prove
from src.reasoning.models import (
    ExceptionLink,
    FactAction,
    FactBase,
    FactEntry,
    Party,
    ProofResult,
    Rule,
    RuleBase,
    TraceStep,
)

__all__ = [
    "ExceptionLink",
    "FactAction",
    "FactBase",
    "FactEntry",
    "Party",
    "ProofResult",
    "Rule",
    "RuleBase",
    "TraceStep",
    "opposite",
    "prove",
]
