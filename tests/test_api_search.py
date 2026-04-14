"""T040 — Tests del endpoint POST /search.

Verifica que la API exponga `/search` con body ``{query, top_k}`` y
devuelva una lista de destinos rankeados por el recuperador p-norm.

Los tests inyectan un índice en memoria mediante ``dependency_overrides``
para no depender del pickle real del proyecto.
"""
from fastapi.testclient import TestClient

from src.api.main import app, get_index, get_retriever
from src.indexing.inverted_index import InvertedIndex
from src.retrieval.extended_boolean import ExtendedBoolean


def _build_test_index() -> InvertedIndex:
    idx = InvertedIndex()
    idx.add_document("doc-beach", ["beach", "sun", "sea"])
    idx.add_document("doc-mountain", ["mountain", "snow", "hike"])
    idx.add_document("doc-city", ["city", "museum", "art"])
    idx.compute_tf_idf()
    return idx


def _client() -> TestClient:
    idx = _build_test_index()
    app.dependency_overrides[get_index] = lambda: idx
    app.dependency_overrides[get_retriever] = lambda: ExtendedBoolean(p=2.0)
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_search_returns_ranked_results():
    client = _client()
    response = client.post("/search", json={"query": "beach", "top_k": 3})
    assert response.status_code == 200
    body = response.json()
    assert "results" in body
    assert len(body["results"]) >= 1
    top = body["results"][0]
    assert top["id"] == "doc-beach"
    assert top["score"] > 0.0


def test_search_respects_top_k():
    client = _client()
    response = client.post(
        "/search", json={"query": "beach OR mountain OR city", "top_k": 2}
    )
    assert response.status_code == 200
    assert len(response.json()["results"]) == 2


def test_search_results_ordered_by_score():
    client = _client()
    response = client.post(
        "/search", json={"query": "beach OR mountain OR city", "top_k": 5}
    )
    scores = [r["score"] for r in response.json()["results"]]
    assert scores == sorted(scores, reverse=True)


def test_search_default_top_k_is_ten():
    client = _client()
    response = client.post("/search", json={"query": "beach"})
    assert response.status_code == 200
    # Sólo 3 docs en el índice; con top_k=10 devuelve los disponibles
    assert len(response.json()["results"]) <= 10


def test_search_requires_query():
    client = _client()
    response = client.post("/search", json={"top_k": 3})
    assert response.status_code == 422
