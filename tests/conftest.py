"""conftest.py — asegura que `src` sea importable como paquete (`src.models`,
`src.pipeline`, `src.behavior`) sin importar desde dónde se invoque pytest."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
