from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

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
