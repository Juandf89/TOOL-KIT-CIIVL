"""
models.py — Modelo de datos del registro-artículo.

Proyecto: similitud estructural-normativa entre códigos civiles de LATAM.
Versión de esquema: n3_v1.1 (2026-09-07) — supersede n3_v1.0

===========================================================================
CHANGELOG v1.0 -> v1.1  (opción B del análisis de brechas de lógica jurídica)
===========================================================================

B1  PresumptionInfo: 'presuncion' era una etiqueta única que colapsaba dos
    objetos lógicos opuestos. La presunción legal es un default derrotable
    — el núcleo de la derrotabilidad que el proyecto declara central — y la
    presunción de derecho es funcionalmente una regla imperativa. Ahora se
    distinguen. Método: censo (~60 casos por código, casi todos marcados
    léxicamente con "se presume de derecho").

B2  Referral: N4 deja de ser una lista de uid y pasa a ser una lista de
    aristas TIPADAS con referral_function. El grafo era semánticamente
    plano: sabía que A apunta a B, no para qué. Una remisión que extiende
    analógicamente un régimen y una que introduce una excepción son
    operaciones lógicas opuestas y producían la misma arista.

    Método: MUESTRA, no censo. Medición sobre fixtures: solo el 5,0% (CL) y
    3,3% (CO) de las remisiones llevan marcador funcional reconocible en su
    contexto. El censo manual de ~3.000 aristas por código es inviable. Pero
    S4 compara DISTRIBUCIONES de función, no aristas individuales: 400
    aristas estratificadas con IC por bootstrap responden lo mismo.

B4  TimeLimit: los plazos concentran las reformas legislativas y son
    detectables por regex, así que 'has' y 'values' son derivados y solo
    'nature' se anota. Masa medida: 118 (CL) / 158 (CO); la diferencia de
    +34% excede la diferencia de tamaño entre códigos (+6%).

FIX derogability_marker degradado de ANOTADO a DERIVADO por regex. Con el
    léxico ampliado a ocho familias de marcadores: 41 aciertos en CL y 39 en
    CO sobre ~2.500 artículos = 1,6% de prevalencia y prácticamente idénticos
    entre códigos. Distribución degenerada: kappa alta y vacía, cero poder
    discriminante. Se conserva como derivado descriptivo, EXCLUIDO de S3.

Todas las cifras citadas proceden de fixtures no oficiales y están marcadas
UNVERIFIED. Se recalculan sobre N0 oficial.

Dependencia: pydantic >= 2.0
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

SCHEMA_VERSION = "n3_v1.1"
GENERALITY_RULE_VERSION = "gen_rule_v1"
REFERRAL_SAMPLE_SIZE = 400

# ---------------------------------------------------------------------------
# Vocabularios cerrados (espejo de schema_n3_v1_1.yaml)
# ---------------------------------------------------------------------------

StatementType = Literal[
    "regla", "principio", "definicion", "remision",
    "presuncion", "ficcion", "regla_interpretativa", "norma_organica",
]

Structure = Literal[
    "supuesto_consecuencia", "supuesto_consecuencia_con_excepcion",
    "definicion_pura", "enumeracion_taxativa", "enumeracion_enunciativa",
    "remision_pura", "principio_abierto",
]

DeonticModality = Literal["obligacion", "prohibicion", "permiso", "ninguno"]
HohfeldianPosition = Literal[
    "deber", "derecho_subjetivo", "privilegio", "potestad", "sujecion", "inmunidad", "ninguno",
]
Derogability = Literal["inderogable", "derogable_por_pacto", "indeterminada"]
Addressee = Literal["partes", "juez", "funcionario_o_notario", "tercero", "indeterminado"]
AntecedentOperator = Literal["si", "cuando", "siempre_que", "en_caso_de", "ninguno_explicito"]
ExceptionScope = Literal["interna", "por_remision", "implicita"]
GeneralityLevel = Literal["casuistica", "intermedia", "clausula_general"]
SpanType = Literal["articulo_completo", "inciso", "numeral"]
LevelType = Literal["parte", "libro", "titulo", "capitulo", "seccion", "parrafo", "subseccion"]
ValidityStatus = Literal["vigente", "derogado", "derogado_tacitamente", "inexequible", "modificado"]

# B1
BurdenShiftsTo = Literal["partes", "tercero", "ninguno"]

# B2
ReferralFunction = Literal[
    "aplicacion_analogica", "excepcion", "definicion",
    "procedimiento", "competencia", "indeterminada",
]

# B4
TimeLimitNature = Literal[
    "prescripcion", "caducidad", "plazo_de_ejercicio",
    "plazo_de_gracia", "plazo_sustantivo", "indeterminado",
]
TimeUnit = Literal["dias", "meses", "anios"]

COMPATIBILITY: dict[str, set[str]] = {
    "regla": {"supuesto_consecuencia", "supuesto_consecuencia_con_excepcion",
              "enumeracion_taxativa", "enumeracion_enunciativa"},
    "principio": {"principio_abierto"},
    "definicion": {"definicion_pura", "enumeracion_taxativa", "enumeracion_enunciativa"},
    "remision": {"remision_pura"},
    "presuncion": {"supuesto_consecuencia", "supuesto_consecuencia_con_excepcion"},
    "ficcion": {"supuesto_consecuencia", "definicion_pura"},
    "regla_interpretativa": {"supuesto_consecuencia", "supuesto_consecuencia_con_excepcion",
                             "principio_abierto"},
    "norma_organica": {"supuesto_consecuencia", "remision_pura", "definicion_pura"},
}

DEROGABILITY_MARKER_RE = re.compile(
    r"no\s+(se\s+)?podr[áa](n)?\s+renunciar|irrenunciab|no\s+es\s+renunciable"
    r"|es\s+nul[ao]\s+(todo|toda|cualquier)|no\s+vale\s+(la|el|toda)"
    r"|no\s+producir[áa](n)?\s+efecto"
    r"|se\s+tendr[áa](n)?\s+por\s+no\s+(escrit|puest)"
    r"|proh[íi]bese|se\s+proh[íi]be|no\s+se\s+permit"
    r"|salvo\s+(pacto|estipulaci[óo]n|convenci[óo]n)\s+en\s+contrario"
    r"|a\s+falta\s+de\s+(pacto|estipulaci[óo]n|disposici[óo]n)"
    r"|aunque\s+se\s+estipule",
    re.IGNORECASE,
)

class StrictModel(BaseModel):
    """Clase base compartida: `validate_assignment=True` re-valida los
    invariantes de cada model_validator también tras una mutación (no solo
    en construcción), y `extra='forbid'` rechaza claves desconocidas de
    forma uniforme en todo el árbol de modelos, no solo en ArticleRecord."""
    model_config = ConfigDict(validate_assignment=True, extra="forbid")

class PathNode(StrictModel):
    level_type: LevelType
    ordinal: Optional[str] = None
    label: Optional[str] = None
    depth: int = Field(ge=0)

class Architecture(StrictModel):
    path: list[PathNode]
    position_index: int = Field(ge=0)
    ordinal_in_parent: Optional[int] = None

    @computed_field
    @property
    def depth(self) -> int:
        return len(self.path)

    @model_validator(mode="after")
    def _check_depth_sequence(self) -> "Architecture":
        for i, node in enumerate(self.path):
            if node.depth != i:
                raise ValueError(f"path[{i}].depth={node.depth}, se esperaba {i}")
        return self

class Institution(StrictModel):
    primary: str
    secondary: list[str] = Field(default_factory=list)
    sali_lmss_mapping: Optional[str] = None
    annotation_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    annotated_by: Literal["human", "llm", "llm+human"] = "human"
    verified: bool = False
    out_of_vocabulary: bool = False

class ExceptionInfo(StrictModel):
    present: bool = False
    marker: Optional[str] = None
    scope: Optional[ExceptionScope] = None

    @model_validator(mode="after")
    def _coherence(self) -> "ExceptionInfo":
        if self.present and self.scope is None:
            raise ValueError("exception.present=True exige scope.")
        if not self.present and (self.marker or self.scope):
            raise ValueError("exception.present=False no admite marker ni scope.")
        return self

class PresumptionInfo(StrictModel):
    rebuttable: bool
    burden_shifts_to: BurdenShiftsTo = "ninguno"
    marker: Optional[str] = None

    @model_validator(mode="after")
    def _coherence(self) -> "PresumptionInfo":
        if self.rebuttable is False and self.burden_shifts_to != "ninguno":
            raise ValueError(
                "Una presunción de derecho (rebuttable=False) no admite prueba "
                "en contrario: no hay carga de la prueba que desplazar, por lo "
                "que burden_shifts_to debe ser 'ninguno'."
            )
        return self

class TimeLimit(StrictModel):
    has: bool = False
    values: list[tuple[int, TimeUnit]] = Field(default_factory=list)
    nature: Optional[TimeLimitNature] = None

    @model_validator(mode="after")
    def _coherence(self) -> "TimeLimit":
        if self.has and self.nature is None:
            raise ValueError("time_limit.has=True exige nature anotada.")
        if not self.has and (self.values or self.nature):
            raise ValueError("time_limit.has=False no admite values ni nature.")
        return self

    @computed_field
    @property
    def min_days(self) -> Optional[int]:
        if not self.values:
            return None
        factor = {"dias": 1, "meses": 30, "anios": 365}
        return min(v * factor[u] for v, u in self.values)

class GeneralityProxies(StrictModel):
    n_conditions: int = Field(ge=0)
    has_enumeration: bool = False
    enumeration_closed: Optional[bool] = None
    indeterminate_concepts: list[str] = Field(default_factory=list)
    n_named_entities_juridicas: int = Field(ge=0, default=0)

    @model_validator(mode="after")
    def _enum_coherence(self) -> "GeneralityProxies":
        if not self.has_enumeration and self.enumeration_closed is not None:
            raise ValueError("enumeration_closed debe ser None si has_enumeration=False.")
        if self.has_enumeration and self.enumeration_closed is None:
            raise ValueError("has_enumeration=True exige enumeration_closed.")
        return self

    def derive_generality(self) -> GeneralityLevel:
        if self.indeterminate_concepts and self.n_conditions <= 1 and not self.has_enumeration:
            return "clausula_general"
        if self.n_conditions >= 3 or (self.has_enumeration and self.enumeration_closed is True):
            return "casuistica"
        return "intermedia"

class NormativeStatement(StrictModel):
    statement_id: int = Field(ge=0)
    span_type: SpanType
    span_index: Optional[int] = None
    text_span: Optional[str] = None

    statement_type: StatementType
    structure: Structure
    deontic_modality: DeonticModality
    hohfeldian_position: HohfeldianPosition
    derogability: Derogability
    addressee: Addressee
    antecedent_operator: AntecedentOperator
    exception: ExceptionInfo = Field(default_factory=ExceptionInfo)
    presumption: Optional[PresumptionInfo] = None
    time_limit: TimeLimit = Field(default_factory=TimeLimit)
    generality: GeneralityProxies

    # "heuristica_local": propuesto por src/labeling/rules.py (reglas léxicas
    # deterministas, sin LLM ni servicio externo) — distinto de
    # statement_type="regla" (tipo de norma), no confundir.
    annotated_by: Literal["human", "llm", "llm+human", "heuristica_local"] = "human"
    verified: bool = False

    @model_validator(mode="after")
    def _rules(self) -> "NormativeStatement":
        allowed = COMPATIBILITY[self.statement_type]
        if self.structure not in allowed:
            raise ValueError(
                f"combinación ilegal: statement_type={self.statement_type} "
                f"con structure={self.structure}. Permitidas: {sorted(allowed)}"
            )
        if self.structure == "supuesto_consecuencia_con_excepcion" and not self.exception.present:
            raise ValueError("structure con excepción exige exception.present=True.")
        if self.statement_type == "presuncion" and self.presumption is None:
            raise ValueError("statement_type='presuncion' exige el bloque presumption.")
        if self.statement_type != "presuncion" and self.presumption is not None:
            raise ValueError("presumption solo se admite en statement_type='presuncion'.")
        if self.presumption is not None and self.presumption.rebuttable is False                 and self.derogability != "inderogable":
            raise ValueError(
                "Una presunción de derecho no admite prueba en contrario: "
                "derogability debe ser 'inderogable'."
            )
        if self.span_type == "articulo_completo" and self.span_index is not None:
            raise ValueError("span_type=articulo_completo no admite span_index.")
        if self.span_type != "articulo_completo" and self.span_index is None:
            raise ValueError(f"span_type={self.span_type} exige span_index.")
        return self

    @computed_field
    @property
    def generality_level(self) -> GeneralityLevel:
        return self.generality.derive_generality()

    @computed_field
    @property
    def derogability_marker_detected(self) -> bool:
        return bool(self.text_span and DEROGABILITY_MARKER_RE.search(self.text_span))

class Referral(StrictModel):
    target_uid: Optional[str] = None
    raw_reference: str
    resolution: Literal["numeric", "anaphoric", "unresolved", "external"] = "numeric"
    function: ReferralFunction = "indeterminada"
    function_marker: Optional[str] = None
    in_function_sample: bool = False
    annotated_by: Literal["human", "llm", "llm+human", "none"] = "none"
    verified: bool = False

    @model_validator(mode="after")
    def _rules(self) -> "Referral":
        if self.function != "indeterminada" and not self.in_function_sample:
            raise ValueError(
                "Solo las aristas de la muestra pueden llevar function != 'indeterminada'."
            )
        if self.resolution in {"numeric", "anaphoric"} and self.target_uid is None:
            raise ValueError(f"resolution={self.resolution} exige target_uid.")
        if self.resolution == "unresolved" and self.target_uid is not None:
            raise ValueError("resolution='unresolved' no admite target_uid.")
        return self

class Referrals(StrictModel):
    outbound: list[Referral] = Field(default_factory=list)
    extraction_method: Literal["regex", "regex+manual_review", "manual"] = "regex"
    recall_sample_member: bool = False

    @computed_field
    @property
    def n_resolved(self) -> int:
        return sum(1 for r in self.outbound if r.target_uid is not None)

    @computed_field
    @property
    def n_in_function_sample(self) -> int:
        return sum(1 for r in self.outbound if r.in_function_sample)

    @computed_field
    @property
    def function_profile(self) -> dict[str, int]:
        return dict(Counter(
            r.function for r in self.outbound
            if r.in_function_sample and r.verified and r.function != "indeterminada"
        ))

class Validity(StrictModel):
    status: ValidityStatus
    source_original_text: Optional[bool] = None
    amended_by: list[str] = Field(default_factory=list)
    last_amendment_date: Optional[date] = None
    constitutional_ruling: Optional[str] = None

class ArticleRecord(StrictModel):
    uid: str
    jurisdiction: str
    code_id: str
    schema_version: str = SCHEMA_VERSION
    manifest_id: str
    source_version_date: date
    source_url: str
    source_retrieved_at: date
    source_hash: str

    n1_architecture: Architecture
    n2_institution: Institution
    n3_statements: list[NormativeStatement] = Field(min_length=1)
    n4_referrals: Referrals = Field(default_factory=Referrals)
    n5_validity: Validity

    text_raw: str
    text_normalized: str
    editorial_notes: list[str] = Field(default_factory=list)
    qa_flags: list[str] = Field(default_factory=list)

    @computed_field
    @property
    def n_statements(self) -> int:
        return len(self.n3_statements)

    @computed_field
    @property
    def statement_type_profile(self) -> dict[str, int]:
        return dict(Counter(s.statement_type for s in self.n3_statements))

    @computed_field
    @property
    def dominant_statement_type(self) -> StatementType:
        counts = Counter(s.statement_type for s in self.n3_statements)
        top = max(counts.values())
        for s in self.n3_statements:
            if counts[s.statement_type] == top:
                return s.statement_type
        raise RuntimeError("inalcanzable")

    @computed_field
    @property
    def is_heterogeneous(self) -> bool:
        return len({s.statement_type for s in self.n3_statements}) > 1

    @computed_field
    @property
    def has_exception(self) -> bool:
        return any(s.exception.present for s in self.n3_statements)

    @computed_field
    @property
    def is_definition(self) -> bool:
        return any(s.statement_type == "definicion" for s in self.n3_statements)

    @computed_field
    @property
    def is_referral(self) -> bool:
        return all(s.statement_type == "remision" for s in self.n3_statements)

    @computed_field
    @property
    def has_time_limit(self) -> bool:
        return any(s.time_limit.has for s in self.n3_statements)

    @computed_field
    @property
    def has_irrebuttable_presumption(self) -> bool:
        return any(
            s.presumption is not None and s.presumption.rebuttable is False
            for s in self.n3_statements
        )

    @computed_field
    @property
    def generality_level(self) -> GeneralityLevel:
        dom = self.dominant_statement_type
        for s in self.n3_statements:
            if s.statement_type == dom:
                return s.generality_level
        raise RuntimeError("inalcanzable")

    @computed_field
    @property
    def score_eligible(self) -> bool:
        return self.n2_institution.verified and all(s.verified for s in self.n3_statements)

    @field_validator("source_hash")
    @classmethod
    def _hash_format(cls, v: str) -> str:
        if not v.startswith("sha256:") or len(v) != 71:
            raise ValueError("source_hash debe ser sha256: + 64 hexadecimales.")
        return v

    @field_validator("uid")
    @classmethod
    def _uid_format(cls, v: str) -> str:
        parts = v.split("-")
        if len(parts) < 5 or parts[3] != "ART":
            raise ValueError("uid esperado: {JUR}-{CODE}-{YEAR}-ART-{NUM}[-{SUFIJO}]")
        return v

    @model_validator(mode="after")
    def _consistency(self) -> "ArticleRecord":
        ids = [s.statement_id for s in self.n3_statements]
        if len(ids) != len(set(ids)):
            raise ValueError("statement_id duplicado dentro del artículo.")
        if len(self.n3_statements) == 1 and self.n3_statements[0].span_type != "articulo_completo":
            raise ValueError("Artículo con un solo enunciado debe usar span_type=articulo_completo.")
        for r in self.n4_referrals.outbound:
            if r.target_uid == self.uid:
                raise ValueError(f"remisión reflexiva detectada en {self.uid}.")
        return self
