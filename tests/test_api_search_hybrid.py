"""T055 — Tests del endpoint POST /search/hybrid.

Verifica que la API exponga ``/search/hybrid`` con body
``{query, top_k, alpha, p}``, combine las ramas léxica y semántica y
devuelva destinos rankeados por score fusionado.

Los tests inyectan stubs deterministas para el índice, el embedder y el
VectorStore, de modo que no dependen de Qdrant ni de sentence-transformers
durante CI.
"""
from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from src.api.main import (
    app,
    get_destinations,
    get_embedder,
    get_index,
    get_retriever_factory,
    get_semantic_collection,
    get_vector_store,
)
from src.indexing.embed_destinations import slug_to_uuid
from src.indexing.inverted_index import InvertedIndex
from src.indexing.vector_store import VectorStore
from src.retrieval.extended_boolean import ExtendedBoolean

COLLECTION = "hybrid_test"
DIM = 4


class _StubEmbedder:
    VECTORS: dict[str, list[float]] = {
        "beach": [1.0, 0.0, 0.0, 0.0],
        "mountain": [0.0, 1.0, 0.0, 0.0],
    }

    def embed(self, text: str) -> list[float]:
        key = text.strip().lower()
        if key in self.VECTORS:
            return list(self.VECTORS[key])
        raw = [float((ord(c) % 7) + 1) for c in (key or "x")[:DIM]]
        raw.extend([0.0] * (DIM - len(raw)))
        norm = math.sqrt(sum(v * v for v in raw)) or 1.0
        return [v / norm for v in raw]


def _build_index() -> InvertedIndex:
    idx = InvertedIndex()
    idx.add_document("doc-beach", ["beach", "sand", "sea"])
    idx.add_document("doc-mountain", ["mountain", "snow", "hike"])
    idx.compute_tf_idf()
    return idx


def _build_store() -> VectorStore:
    store = VectorStore(url=":memory:")
    store.create_collection(COLLECTION, vector_size=DIM)
    embedder = _StubEmbedder()
    points = [
        (
            slug_to_uuid("doc-beach"),
            embedder.embed("beach"),
            {"slug": "doc-beach", "name": "Playa", "country": "ES"},
        ),
        (
            slug_to_uuid("doc-mountain"),
            embedder.embed("mountain"),
            {"slug": "doc-mountain", "name": "Montana", "country": "AR"},
        ),
    ]
    store.upsert(COLLECTION, points)
    return store


def _client(destinations: dict | None = None) -> TestClient:
    store = _build_store()
    embedder = _StubEmbedder()
    index = _build_index()
    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_embedder] = lambda: embedder
    app.dependency_overrides[get_semantic_collection] = lambda: COLLECTION
    app.dependency_overrides[get_index] = lambda: index
    app.dependency_overrides[get_retriever_factory] = lambda: lambda p: ExtendedBoolean(p=p)
    app.dependency_overrides[get_destinations] = lambda: destinations or {}
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_hybrid_search_returns_results():
    client = _client()
    response = client.post("/search/hybrid", json={"query": "beach", "top_k": 2})
    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) >= 1


def test_hybrid_search_top_result_is_beach():
    client = _client()
    response = client.post("/search/hybrid", json={"query": "beach", "top_k": 2, "alpha": 0.5})
    assert response.status_code == 200
    top = response.json()["results"][0]
    assert top["id"] == "doc-beach"


def test_hybrid_search_respects_top_k():
    client = _client()
    response = client.post("/search/hybrid", json={"query": "beach", "top_k": 1})
    assert response.status_code == 200
    assert len(response.json()["results"]) == 1


def test_hybrid_search_results_ordered_by_score():
    client = _client()
    response = client.post("/search/hybrid", json={"query": "beach", "top_k": 2})
    scores = [r["score"] for r in response.json()["results"]]
    assert scores == sorted(scores, reverse=True)


def test_hybrid_alpha_zero_uses_semantic_only():
    """alpha=0.0 delega completamente en la rama semántica."""
    client = _client()
    response = client.post(
        "/search/hybrid", json={"query": "mountain", "top_k": 2, "alpha": 0.0}
    )
    assert response.status_code == 200
    top = response.json()["results"][0]
    assert top["id"] == "doc-mountain"


def test_hybrid_alpha_one_uses_lexical_only():
    """alpha=1.0 delega completamente en la rama léxica."""
    client = _client()
    response = client.post(
        "/search/hybrid", json={"query": "beach", "top_k": 2, "alpha": 1.0}
    )
    assert response.status_code == 200
    assert response.json()["results"][0]["id"] == "doc-beach"


def test_hybrid_enriches_metadata_from_destinations():
    destinations = {
        "doc-beach": {
            "name": "Playa Dorada",
            "country": "ES",
            "description": "Arena dorada y aguas tranquilas.",
            "image_urls": ["img.jpg"],
        }
    }
    client = _client(destinations=destinations)
    response = client.post("/search/hybrid", json={"query": "beach", "top_k": 1})
    top = response.json()["results"][0]
    assert top["name"] == "Playa Dorada"
    assert top["description"] == "Arena dorada y aguas tranquilas."
    assert top["image_urls"] == ["img.jpg"]


def test_hybrid_scores_in_unit_interval():
    client = _client()
    response = client.post("/search/hybrid", json={"query": "beach", "top_k": 5})
    for r in response.json()["results"]:
        assert 0.0 <= r["score"] <= 1.0


def test_hybrid_requires_query():
    client = _client()
    response = client.post("/search/hybrid", json={"top_k": 3})
    assert response.status_code == 422


def test_hybrid_rejects_alpha_out_of_range():
    client = _client()
    too_high = client.post("/search/hybrid", json={"query": "beach", "alpha": 1.5})
    too_low = client.post("/search/hybrid", json={"query": "beach", "alpha": -0.1})
    assert too_high.status_code == 422
    assert too_low.status_code == 422


@pytest.mark.parametrize("alpha", [0.0, 0.5, 1.0])
def test_hybrid_accepts_valid_alpha_values(alpha: float):
    client = _client()
    response = client.post("/search/hybrid", json={"query": "beach", "alpha": alpha})
    assert response.status_code == 200
