from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

from src.reasoning.models import Party, FactEntry, FactBase, ProofResult
from src.reasoning.engine import prove
from src.reasoning.rulesets import RULEBASES

app = FastAPI(title='DataLex Lab · LATIO API', version='1.0.0', docs_url='/docs')

# Orígenes explícitos permitidos. `allow_origins=['*']` junto con
# `allow_credentials=True` es una combinación inválida/insegura según la
# especificación CORS (ver A-2, reports/debate_revision_2026-09-10.md).
# TODO(despliegue): 'https://datalexlab.com' es el dominio conocido del
# proyecto (README); ajustar esta lista a los orígenes reales de
# producción/staging/preview antes de un despliegue definitivo.
ALLOWED_ORIGINS = ['https://datalexlab.com']

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

@app.get('/')
def root():
    return {'lab': 'DataLex Lab', 'website': 'https://www.datalexlab.com', 'project': 'LATIO API', 'version': '1.0.0', 'docs': '/docs'}


# --------------------------------------------------------------------------
# /v1/reasoning — motor de razonamiento jurídico derrotable (PROLEG)
# --------------------------------------------------------------------------

class RulebaseInfo(BaseModel):
    id: str
    description: str


class ProveRequest(BaseModel):
    rulebase_id: str
    goal: str
    party: Party
    facts: List[FactEntry]


@app.get('/v1/reasoning/rulebases', response_model=List[RulebaseInfo])
def list_rulebases():
    return [
        RulebaseInfo(id=rulebase_id, description=getattr(rulebase, 'description', ''))
        for rulebase_id, rulebase in RULEBASES.items()
    ]


@app.post('/v1/reasoning/prove', response_model=ProofResult)
def reasoning_prove(req: ProveRequest):
    rulebase = RULEBASES.get(req.rulebase_id)
    if rulebase is None:
        raise HTTPException(status_code=404, detail=f"rulebase_id '{req.rulebase_id}' no encontrado")

    factbase = FactBase(entries=req.facts)
    return prove(req.goal, req.party, rulebase, factbase)
