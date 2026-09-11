"""passenger_wsgi.py — punto de entrada para Hostinger (hPanel > Avanzado >
Setup Python App, sobre Phusion Passenger).

Passenger, en el modelo clásico de hosting compartido, espera un callable
WSGI llamado `application` en este archivo exacto. `src/api.py` expone una
app ASGI (FastAPI) — `a2wsgi.ASGIMiddleware` la envuelve como WSGI sin tocar
`src/api.py` ni perder ninguna de sus rutas (incluye /v1/reasoning/* y
/v1/corpora/*, agregados en paralelo por otro proceso).

Si el plan de Hostinger específico soporta ASGI nativo en su versión de
Passenger, este wrapper igual funciona (corre en modo síncrono, sin
aprovechar async nativo) — es la opción más compatible entre pl,anes, no la
más rápida. Ver DEPLOYMENT.md, sección "Hostinger (hosting compartido)".
"""

import sys
from pathlib import Path

# hPanel corre este archivo desde la carpeta de la app; asegurar que el
# repo esté en sys.path para que "import src.api" resuelva sin importar
# desde qué directorio de trabajo lo invoque Passenger.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from a2wsgi import ASGIMiddleware

from src.api import app as _asgi_app

application = ASGIMiddleware(_asgi_app)
