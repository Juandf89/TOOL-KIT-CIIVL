"""test_api_corpora.py — tests de integración de /v1/corpora/* contra el
contenido REAL de los 8 corpus legales ya extraídos por el pipeline
(data/processed/<corpus_id>_articles.json + reports/manifest.json).

A diferencia de /v1/statements/* y /v1/behavior/* (mockeados en
toolkit-api/index.html, "Modo demostración"), estos endpoints sirven datos
genuinos, así que estos tests corren contra los artefactos reales del
repositorio, no contra fixtures sintéticas. Se usa CO-CC (sugerido por la
consigna) para mantener la suite rápida.
"""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from src.api import app

client = TestClient(app)

ROOT = Path(__file__).resolve().parent.parent
CORPUS_ID = "CO-CC"

with open(ROOT / "reports" / "manifest.json", "r", encoding="utf-8") as f:
    _MANIFEST = json.load(f)
_MANIFEST_ENTRY = next(c for c in _MANIFEST["corpora"] if c["corpus_id"] == CORPUS_ID)

with open(ROOT / "data" / "processed" / f"{CORPUS_ID}_articles.json", "r", encoding="utf-8") as f:
    _REAL_ARTICLES = json.load(f)


def test_list_corpora_returns_the_8_real_corpora():
    response = client.get("/v1/corpora")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 8

    ids = {c["corpus_id"] for c in body}
    assert ids == {
        "CL-CC", "CO-CC", "AR-CC", "AR-CCYC", "BR-CC", "MX-CCF", "MX-CDMX", "PE-CC",
    }

    entry = next(c for c in body if c["corpus_id"] == CORPUS_ID)
    assert entry["display_name"] == "Código Civil de Colombia (Ley 84 de 1873, vía Ley 57 de 1887)"
    assert entry["jurisdiction"] == "CO"
    assert entry["articles_parsed"] == _MANIFEST_ENTRY["articles_parsed"]
    assert entry["expected_article_count"] == _MANIFEST_ENTRY["expected_article_count"]
    assert entry["recall"] == _MANIFEST_ENTRY["recall"]
    # No debe filtrar el fixture de prueba interno del pipeline.
    assert "TEST-FIXTURE" not in ids


def test_get_corpus_detail_includes_the_6_gates():
    response = client.get(f"/v1/corpora/{CORPUS_ID}")
    assert response.status_code == 200
    body = response.json()
    assert body["corpus_id"] == CORPUS_ID
    gates = body["gates"]
    for key in (
        "completitud", "unicidad", "consistencia_N4",
        "integridad_grafo", "cuerpo_no_vacio", "trazabilidad",
    ):
        assert key in gates
        assert gates[key] == _MANIFEST_ENTRY["gates"][key]


def test_get_corpus_detail_unknown_corpus_returns_404():
    response = client.get("/v1/corpora/ZZ-DOES-NOT-EXIST")
    assert response.status_code == 404
    assert "ZZ-DOES-NOT-EXIST" in response.json()["detail"]


def test_list_corpus_articles_returns_real_paginated_content():
    response = client.get(f"/v1/corpora/{CORPUS_ID}/articles", params={"limit": 5, "offset": 0})
    assert response.status_code == 200
    body = response.json()

    assert body["corpus_id"] == CORPUS_ID
    assert body["total"] == len(_REAL_ARTICLES)
    assert body["limit"] == 5
    assert body["offset"] == 0
    assert len(body["articles"]) == 5

    first = body["articles"][0]
    real_first = _REAL_ARTICLES[0]
    assert first["uid"] == real_first["uid"]
    assert first["text_raw"] == real_first["text_raw"][:300]
    assert first["truncated"] == (len(real_first["text_raw"]) > 300)
    assert "path" in first


def test_list_corpus_articles_respects_limit_upper_bound():
    response = client.get(f"/v1/corpora/{CORPUS_ID}/articles", params={"limit": 500})
    assert response.status_code == 422  # limit<=200 impuesto por Query(..., le=200)


def test_list_corpus_articles_unknown_corpus_returns_404():
    response = client.get("/v1/corpora/ZZ-DOES-NOT-EXIST/articles")
    assert response.status_code == 404


def test_get_single_article_by_uid_returns_full_untruncated_text():
    # Buscamos un artículo real con texto más largo que el recorte de listado
    # (300 caracteres) para probar que el detalle no lo trunca.
    long_article = max(_REAL_ARTICLES, key=lambda a: len(a["text_raw"]))
    assert len(long_article["text_raw"]) > 300

    response = client.get(f"/v1/corpora/{CORPUS_ID}/articles/{long_article['uid']}")
    assert response.status_code == 200
    body = response.json()
    assert body["uid"] == long_article["uid"]
    assert body["text_raw"] == long_article["text_raw"]
    assert "truncated" not in body


def test_get_single_article_unknown_uid_returns_404():
    response = client.get(f"/v1/corpora/{CORPUS_ID}/articles/NOT-A-REAL-UID")
    assert response.status_code == 404
    assert "NOT-A-REAL-UID" in response.json()["detail"]


def test_get_single_article_unknown_corpus_returns_404():
    response = client.get("/v1/corpora/ZZ-DOES-NOT-EXIST/articles/whatever")
    assert response.status_code == 404
