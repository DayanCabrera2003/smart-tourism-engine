"""T040 — Tests del endpoint POST /search.

Verifica que la API exponga `/search` con body ``{query, top_k}`` y
devuelva una lista de destinos rankeados por el recuperador p-norm.

Los tests inyectan un índice en memoria mediante ``dependency_overrides``
para no depender del pickle real del proyecto.
"""
from fastapi.testclient import TestClient

from src.api.main import app, get_destinations, get_index, get_retriever_factory
from src.indexing.inverted_index import InvertedIndex
from src.retrieval.extended_boolean import ExtendedBoolean


def _build_test_index() -> InvertedIndex:
    idx = InvertedIndex()
    idx.add_document("doc-beach", ["beach", "sun", "sea"])
    idx.add_document("doc-mountain", ["mountain", "snow", "hike"])
    idx.add_document("doc-city", ["city", "museum", "art"])
    idx.compute_tf_idf()
    return idx


def _client(
    destinations: dict | None = None,
    captured_p: list[float] | None = None,
) -> TestClient:
    idx = _build_test_index()
    app.dependency_overrides[get_index] = lambda: idx

    def _factory() -> "callable":
        def _make(p: float) -> ExtendedBoolean:
            if captured_p is not None:
                captured_p.append(p)
            return ExtendedBoolean(p=p)
        return _make

    app.dependency_overrides[get_retriever_factory] = _factory
    app.dependency_overrides[get_destinations] = lambda: destinations or {}
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


def test_search_enriches_results_with_metadata():
    """T044 — La API adjunta name/country/description cuando hay metadatos."""
    destinations = {
        "doc-beach": {
            "name": "Playa del Carmen",
            "country": "México",
            "description": "Balneario caribeño con arrecife y vida nocturna.",
            "image_urls": [],
        }
    }
    client = _client(destinations=destinations)
    response = client.post("/search", json={"query": "beach", "top_k": 1})
    assert response.status_code == 200
    top = response.json()["results"][0]
    assert top["id"] == "doc-beach"
    assert top["name"] == "Playa del Carmen"
    assert top["country"] == "México"
    assert "arrecife" in top["description"]


def test_search_accepts_custom_p():
    """T047 — El body acepta ``p`` y el endpoint lo usa al construir el recuperador."""
    captured: list[float] = []
    client = _client(captured_p=captured)
    response = client.post("/search", json={"query": "beach", "top_k": 3, "p": 4.5})
    assert response.status_code == 200
    assert captured == [4.5]


def test_search_default_p_is_two():
    """T047 — Sin ``p`` explícito se usa p=2.0 (valor por defecto del schema)."""
    captured: list[float] = []
    client = _client(captured_p=captured)
    response = client.post("/search", json={"query": "beach"})
    assert response.status_code == 200
    assert captured == [2.0]


def test_search_rejects_p_out_of_range():
    """T047 — ``p`` fuera de [1, 10] debe devolver 422."""
    client = _client()
    too_small = client.post("/search", json={"query": "beach", "p": 0.5})
    too_big = client.post("/search", json={"query": "beach", "p": 20})
    assert too_small.status_code == 422
    assert too_big.status_code == 422


def test_search_returns_null_metadata_when_absent():
    """T044 — Si no hay metadatos, los campos nuevos viajan como null."""
    client = _client(destinations={})
    response = client.post("/search", json={"query": "beach", "top_k": 1})
    top = response.json()["results"][0]
    assert top["name"] is None
    assert top["country"] is None
    assert top["description"] is None
