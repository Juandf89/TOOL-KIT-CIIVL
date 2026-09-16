"""passenger_wsgi.py — punto de entrada para Hostinger (hPanel > Avanzado >
Setup Python App, sobre Phusion Passenger).

Passenger, en el modelo clásico de hosting compartido, espera un callable
WSGI llamado `application` en este archivo exacto. `src/api.py` expone una
app ASGI (FastAPI) — `a2wsgi.ASGIMiddleware` la envuelve como WSGI sin tocar
`src/api.py` ni perder ninguna de sus rutas (incluye /v1/reasoning/* y
/v1/corpora/*, agregados en paralelo por otro proceso).

Si el plan de Hostinger específico soporta ASGI nativo en su versión de
Passenger, este wrapper igual funciona (corre en modo síncrono, sin
aprovechar async nativo) — es la opción más compatible entre planes, no la
más rápida. Ver DEPLOYMENT.md. Esta ruta requiere un plan que ejecute Python:
la API de producción es el puerto Node de latio-node/ (ver
latio-node/DEPLOYMENT-NODE.md).

Nota sobre la IP del cliente (importa para el límite de tasa): a2wsgi solo
puebla `scope["client"]` si el entorno WSGI trae REMOTE_ADDR **y**
REMOTE_PORT, y REMOTE_PORT no es parte de PEP 3333. Por eso
`src/ratelimit.py` lee REMOTE_ADDR de `scope["wsgi_environ"]`, que a2wsgi sí
conserva siempre. No cambiar eso sin leer el comentario de `_client_ip`.
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
