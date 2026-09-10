"""src/reasoning/rulesets — bases de reglas registradas del motor.

`RULEBASES` es el registro público: `RULEBASES[id] -> RuleBase`. Cada módulo
del paquete define un `RuleBase` de contenido jurídico verificado y se
registra aquí bajo su `RuleBase.id`.
"""

from src.reasoning.models import RuleBase
from src.reasoning.rulesets.jp_civil_612_sublease import RULEBASE as JP_CIVIL_612_SUBLEASE

RULEBASES: dict[str, RuleBase] = {
    JP_CIVIL_612_SUBLEASE.id: JP_CIVIL_612_SUBLEASE,
}

__all__ = ["RULEBASES"]
