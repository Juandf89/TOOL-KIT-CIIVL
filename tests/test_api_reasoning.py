"""test_api_reasoning.py — tests de integración de /v1/reasoning/* contra el
motor de razonamiento jurídico derrotable (PROLEG) del paquete
`src/reasoning/`.

El caso de oro reproduce el Apéndice A del paper PROLEG (Satoh et al.,
JURISIN 2010): cancelación de arrendamiento por subarriendo no autorizado
bajo el Art. 612 del Código Civil japonés, con sus dos defensas del
demandado (aprobación del subarriendo; ausencia de abuso de confianza) y la
contra-excepción del demandante (abuso de confianza) que las revierte.
"""

from fastapi.testclient import TestClient

from src.api import app
from src.reasoning.models import FactAction, Party

client = TestClient(app)

RULEBASE_ID = "jp-civil-612-sublease-demo"


def _golden_facts() -> list[dict]:
    """Factbase completo del escenario del Apéndice A del paper PROLEG."""
    facts: list[dict] = []

    # El demandado admite las 6 condiciones base de
    # cancellation_due_to_sublease — le sirven de prueba al demandante.
    base_facts = [
        "agreement_of_lease_contract",
        "agreement_of_sublease_contract",
        "handover_to_lessee",
        "handover_to_sublessee",
        "using_leased_thing",
        "manifestation_cancellation",
    ]
    for fact in base_facts:
        facts.append({"action": FactAction.ADMISSION.value, "fact": fact, "party": Party.DEFENDANT.value})

    # El demandado alega y provee evidencia de la aprobación del subarriendo
    # y de que esa aprobación fue anterior a la cancelación — pero sin
    # admisión de la contraria ni determinación de plausibilidad, por lo que
    # ninguno de los dos hechos queda probado (la defensa get_approval_of_sublease
    # debe fallar).
    for fact in ("approval_of_sublease", "approval_before_cancellation"):
        facts.append({"action": FactAction.ALLEGE.value, "fact": fact, "party": Party.DEFENDANT.value})
        facts.append({"action": FactAction.PROVIDE_EVIDENCE.value, "fact": fact, "party": Party.DEFENDANT.value})

    # El demandado alega y provee evidencia de la ausencia de abuso de
    # confianza, y el juez lo determina plausible: fact_of_nonabuse_of_confidence
    # queda probado, por lo que la defensa nonabuse_of_confidence prospera...
    facts.append({"action": FactAction.ALLEGE.value, "fact": "fact_of_nonabuse_of_confidence", "party": Party.DEFENDANT.value})
    facts.append({"action": FactAction.PROVIDE_EVIDENCE.value, "fact": "fact_of_nonabuse_of_confidence", "party": Party.DEFENDANT.value})
    facts.append({"action": FactAction.PLAUSIBLE.value, "fact": "fact_of_nonabuse_of_confidence", "party": None})

    # ...pero el demandante alega y provee evidencia de abuso de confianza, y
    # el juez también lo determina plausible: fact_of_abuse_of_confidence
    # queda probado, lo que revierte la defensa nonabuse_of_confidence
    # (contra-excepción abuse_of_confidence) y deja en pie
    # cancellation_due_to_sublease.
    facts.append({"action": FactAction.ALLEGE.value, "fact": "fact_of_abuse_of_confidence", "party": Party.PLAINTIFF.value})
    facts.append({"action": FactAction.PROVIDE_EVIDENCE.value, "fact": "fact_of_abuse_of_confidence", "party": Party.PLAINTIFF.value})
    facts.append({"action": FactAction.PLAUSIBLE.value, "fact": "fact_of_abuse_of_confidence", "party": None})

    return facts


def test_list_rulebases_returns_at_least_one_entry():
    response = client.get("/v1/reasoning/rulebases")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 1
    ids = {entry["id"] for entry in body}
    assert RULEBASE_ID in ids


def test_prove_contract_end_golden_case_from_proleg_appendix_a():
    payload = {
        "rulebase_id": RULEBASE_ID,
        "goal": "contract_end",
        "party": Party.PLAINTIFF.value,
        "facts": _golden_facts(),
    }

    response = client.post("/v1/reasoning/prove", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["goal"] == "contract_end"
    assert body["party"] == Party.PLAINTIFF.value
    assert body["proved"] is True
    assert isinstance(body["trace"], list)
    assert len(body["trace"]) > 0


def test_prove_unknown_rulebase_returns_404():
    payload = {
        "rulebase_id": "no-existe",
        "goal": "contract_end",
        "party": Party.PLAINTIFF.value,
        "facts": [],
    }

    response = client.post("/v1/reasoning/prove", json=payload)

    assert response.status_code == 404
