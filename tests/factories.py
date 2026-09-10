"""factories.py — constructores mínimos válidos de NormativeStatement /
ArticleRecord para tests. No son fixtures de negocio: son solo el esqueleto
más chico que pasa los model_validator de src/models.py, para que cada test
solo tenga que sobreescribir el campo que le interesa probar."""

from __future__ import annotations

from datetime import date

from src.models import (
    Architecture,
    ArticleRecord,
    ExceptionInfo,
    GeneralityProxies,
    Institution,
    NormativeStatement,
    Referral,
    Referrals,
    TimeLimit,
    Validity,
)


def make_statement(**overrides) -> NormativeStatement:
    defaults = dict(
        statement_id=0,
        span_type="articulo_completo",
        span_index=None,
        text_span=None,
        statement_type="regla",
        structure="supuesto_consecuencia",
        deontic_modality="obligacion",
        hohfeldian_position="deber",
        derogability="derogable_por_pacto",
        addressee="partes",
        antecedent_operator="si",
        exception=ExceptionInfo(),
        presumption=None,
        time_limit=TimeLimit(),
        generality=GeneralityProxies(n_conditions=1, has_enumeration=False),
        annotated_by="human",
        verified=False,
    )
    defaults.update(overrides)
    return NormativeStatement(**defaults)


def make_article(**overrides) -> ArticleRecord:
    statements = overrides.pop("n3_statements", None) or [make_statement()]
    defaults = dict(
        uid="XX-TEST-2026-ART-1",
        jurisdiction="XX",
        code_id="TEST",
        manifest_id="test-manifest",
        source_version_date=date(2026, 1, 1),
        source_url="http://example.com/fixture",
        source_retrieved_at=date(2026, 1, 1),
        source_hash="sha256:" + "a" * 64,
        n1_architecture=Architecture(path=[], position_index=0),
        n2_institution=Institution(primary="obligaciones"),
        n3_statements=statements,
        n4_referrals=Referrals(),
        n5_validity=Validity(status="vigente"),
        text_raw="texto de prueba",
        text_normalized="texto de prueba",
    )
    defaults.update(overrides)
    return ArticleRecord(**defaults)
