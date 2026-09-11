"""schemas.py — contrato de salida del etiquetado por reglas (Paso 1).

LabelProposal es deliberadamente parcial: cada campo que las reglas no
pueden determinar con confianza queda en None y se lista en
`undetermined_fields`, en vez de forzar un valor plausible. El llamador
(la UI, o un humano) completa lo que falta y el resultado final siempre
pasa por POST /v1/statements/validate (src/api.py), que es la única
fuente de verdad sobre si la combinación es jurídicamente válida.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from src.models import AntecedentOperator, StatementType, Structure


class LabelProposal(BaseModel):
    statement_type: Optional[StatementType] = None
    structure: Optional[Structure] = None
    antecedent_operator: Optional[AntecedentOperator] = None

    exception_present: bool = False
    exception_marker: Optional[str] = None
    exception_scope: Optional[str] = None

    presumption_rebuttable: Optional[bool] = None

    determined_fields: list[str] = Field(default_factory=list)
    undetermined_fields: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    annotated_by: str = "heuristica_local"
