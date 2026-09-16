"""schemas.py — contrato de salida de la determinación deóntica por reglas.

LabelProposal reporta la determinación deóntica (Von Wright) y el correlato
hohfeldiano por defecto que las reglas léxicas deterministas (ver rules.py)
logran derivar del texto, con `notes` documentando los criterios y límites
aplicados. Cuando no hay evidencia suficiente para un campo, este queda en
None (u "ninguno"/"ninguno_explicito", según el vocabulario del campo).
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from src.models import (
    Addressee,
    AntecedentOperator,
    DeonticModality,
    HohfeldianPosition,
    StatementType,
    Structure,
)


class ProlegRunResult(BaseModel):
    proved: bool
    trace_length: int


class ProlegPreview(BaseModel):
    rulebase_id: str
    without_exception: ProlegRunResult
    with_exception: ProlegRunResult
    note: str


class LabelProposal(BaseModel):
    statement_type: Optional[StatementType] = None
    structure: Optional[Structure] = None
    deontic_modality: DeonticModality = "ninguno"
    hohfeldian_position: HohfeldianPosition = "ninguno"
    addressee: Optional[Addressee] = None
    antecedent_operator: Optional[AntecedentOperator] = None

    exception_present: bool = False
    exception_marker: Optional[str] = None
    exception_scope: Optional[str] = None

    presumption_rebuttable: Optional[bool] = None

    notes: list[str] = Field(default_factory=list)

    proleg_preview: Optional[ProlegPreview] = None

    annotated_by: str = "heuristica_local"
