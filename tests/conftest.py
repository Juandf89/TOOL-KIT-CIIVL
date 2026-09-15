"""conftest.py — asegura que `src` sea importable como paquete (`src.models`,
`src.pipeline`, `src.behavior`) sin importar desde dónde se invoque pytest."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# El límite de tasa (src/ratelimit.py) se apaga durante los tests. Sin esto,
# TestClient manda todas las peticiones desde una sola IP ficticia y la suite
# consume un único presupuesto compartido: hoy queda por debajo del tope por
# casualidad, pero agregar unos pocos tests de /v1/reasoning/prove o
# /v1/statements/* haría fallar tests ajenos con un 429 desconcertante.
# Lo que se prueba acá es la lógica de la API, no el limitador — el limitador
# tiene su propia verificación, con límites explícitos, en verify_prod.py.
os.environ.setdefault("LATIO_RATE_LIMIT_ENABLED", "0")
