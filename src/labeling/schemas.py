"""schemas.py — contrato de salida del etiquetado por reglas.

LabelProposal es deliberadamente parcial: cada campo se reporta en una de
tres categorías —`determined_fields` (marcador léxico de baja ambigüedad),
`default_fields` (sin marcador, pero con un valor modal razonable y
documentado en `notes`), o `undetermined_fields` (sin evidencia suficiente,
se deja en None). El llamador (la UI, o un humano) completa lo que falta y
el resultado final siempre pasa por POST /v1/statements/validate
(src/api.py), la única fuente de verdad sobre si la combinación es
jurídicamente válida.
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

    determined_fields: list[str] = Field(default_factory=list)
    default_fields: list[str] = Field(default_factory=list)
    undetermined_fields: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    proleg_preview: Optional[ProlegPreview] = None

    annotated_by: str = "heuristica_local"
