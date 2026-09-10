"""test_reasoning_co_256.py — pruebas del ruleset co-civil-256-visitas.

Primer ruleset del motor derivado de un artículo LATAM real (Art. 256 del
Código Civil colombiano, ver src/reasoning/rulesets/co_civil_256_visitas.py
para el texto fuente citado y la justificación de cada Rule).

Los tres escenarios son HIPOTÉTICOS (no son un caso real fallado): sirven
para ejercitar las dos ramas del ruleset — el derecho por defecto del
progenitor (concedido y derrotado por la excepción absoluta) y el régimen
judicial del ascendiente en segundo grado.
"""

from __future__ import annotations

from src.reasoning.engine import prove
from src.reasoning.models import FactAction, FactBase, FactEntry, Party
from src.reasoning.rulesets import RULEBASES

RULEBASE = RULEBASES["co-civil-256-visitas"]


def _entry(action: FactAction, fact: str, party: Party | None = None) -> FactEntry:
    return FactEntry(action=action, fact=fact, party=party)


def test_derecho_de_visitas_progenitor_se_concede_sin_condena():
    """Escenario A: el progenitor sin custodia pide visitas; la contraparte
    admite que no tiene el cuidado personal de los hijos y no alega ninguna
    condena -> no hay excepción que probar -> el derecho por defecto se
    prueba."""
    factbase = FactBase(entries=[
        _entry(FactAction.ADMISSION, "no_tiene_cuidado_personal_hijos", Party.DEFENDANT),
    ])
    result = prove("derecho_de_visitas_progenitor", Party.PLAINTIFF, RULEBASE, factbase)
    assert result.proved is True


def test_derecho_de_visitas_progenitor_se_derrota_por_victimario_absoluto():
    """Escenario B: mismo punto de partida, pero la contraparte (defendant,
    la parte con custodia) alega y prueba que el solicitante fue condenado
    por sentencia ejecutoriada por violencia intrafamiliar contra ese mismo
    hijo -> se activa la excepción absoluta del parágrafo -> el derecho por
    defecto queda derrotado, aunque la condición base (no tener custodia)
    siga cumplida."""
    factbase = FactBase(entries=[
        _entry(FactAction.ADMISSION, "no_tiene_cuidado_personal_hijos", Party.DEFENDANT),
        _entry(FactAction.ALLEGE, "condena_ejecutoriada_violencia_intrafamiliar", Party.DEFENDANT),
        _entry(FactAction.PROVIDE_EVIDENCE, "condena_ejecutoriada_violencia_intrafamiliar", Party.DEFENDANT),
        _entry(FactAction.PLAUSIBLE, "condena_ejecutoriada_violencia_intrafamiliar"),
        _entry(FactAction.ALLEGE, "es_victima_o_hermano_del_solicitante", Party.DEFENDANT),
        _entry(FactAction.PROVIDE_EVIDENCE, "es_victima_o_hermano_del_solicitante", Party.DEFENDANT),
        _entry(FactAction.PLAUSIBLE, "es_victima_o_hermano_del_solicitante"),
    ])
    result = prove("derecho_de_visitas_progenitor", Party.PLAINTIFF, RULEBASE, factbase)
    assert result.proved is False

    kinds_and_subjects = [(s.kind, s.subject) for s in result.trace]
    assert ("alleges_defense", "es_victimario_absoluto") in kinds_and_subjects
    assert ("defense_succeeded", "es_victimario_absoluto") in kinds_and_subjects


def test_regimen_visitas_abuelos_se_concede_cuando_progenitores_niegan_relacion():
    """Escenario C: la abuela (segundo grado de consanguinidad) no tiene el
    cuidado personal de los nietos, y los progenitores le niegan la
    relación -> justifica_regulacion se prueba por la rama de negación del
    vínculo (inciso 2) -> el régimen de visitas se concede, sin que se
    alegue ninguna condena."""
    factbase = FactBase(entries=[
        _entry(FactAction.ADMISSION, "es_ascendiente_segundo_grado", Party.DEFENDANT),
        _entry(FactAction.ADMISSION, "no_tiene_cuidado_personal_nietos", Party.DEFENDANT),
        _entry(FactAction.ALLEGE, "progenitores_niegan_relacion", Party.PLAINTIFF),
        _entry(FactAction.PROVIDE_EVIDENCE, "progenitores_niegan_relacion", Party.PLAINTIFF),
        _entry(FactAction.PLAUSIBLE, "progenitores_niegan_relacion"),
    ])
    result = prove("regimen_visitas_abuelos", Party.PLAINTIFF, RULEBASE, factbase)
    assert result.proved is True
