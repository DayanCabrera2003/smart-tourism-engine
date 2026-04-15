"""T053 — Tests del endpoint POST /search/semantic.

Verifica que la API exponga ``/search/semantic`` con body ``{query, top_k}``,
embeba la consulta y consulte Qdrant para devolver los destinos rankeados.

Los tests inyectan un ``VectorStore`` en memoria y un embedder determinista
mediante ``dependency_overrides`` para no depender de Qdrant ni de
``sentence-transformers`` durante la ejecución de CI.
"""
from __future__ import annotations

import math

from fastapi.testclient import TestClient

from src.api.main import (
    app,
    get_destinations,
    get_embedder,
    get_semantic_collection,
    get_vector_store,
)
from src.indexing.embed_destinations import slug_to_uuid
from src.indexing.vector_store import VectorStore

COLLECTION = "destinations_text_test"
DIM = 4


class _StubEmbedder:
    """Embedder determinista: vector unitario por slug conocido."""

    VECTORS: dict[str, list[float]] = {
        "beach": [1.0, 0.0, 0.0, 0.0],
        "mountain": [0.0, 1.0, 0.0, 0.0],
        "city": [0.0, 0.0, 1.0, 0.0],
    }

    def embed(self, text: str) -> list[float]:
        key = text.strip().lower()
        if key in self.VECTORS:
            return list(self.VECTORS[key])
        raw = [float((ord(c) % 7) + 1) for c in (key or "x")[:DIM]]
        raw.extend([0.0] * (DIM - len(raw)))
        norm = math.sqrt(sum(v * v for v in raw)) or 1.0
        return [v / norm for v in raw]


def _seed_store() -> VectorStore:
    store = VectorStore(url=":memory:")
    store.create_collection(COLLECTION, vector_size=DIM)
    embedder = _StubEmbedder()
    points = [
        (
            slug_to_uuid("doc-beach"),
            embedder.embed("beach"),
            {"slug": "doc-beach", "name": "Playa", "country": "ES", "image_urls": ["a.jpg"]},
        ),
        (
            slug_to_uuid("doc-mountain"),
            embedder.embed("mountain"),
            {"slug": "doc-mountain", "name": "Montaña", "country": "AR", "image_urls": []},
        ),
        (
            slug_to_uuid("doc-city"),
            embedder.embed("city"),
            {"slug": "doc-city", "name": "Ciudad", "country": "FR", "image_urls": []},
        ),
    ]
    store.upsert(COLLECTION, points)
    return store


def _client(destinations: dict | None = None) -> TestClient:
    store = _seed_store()
    embedder = _StubEmbedder()
    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_embedder] = lambda: embedder
    app.dependency_overrides[get_semantic_collection] = lambda: COLLECTION
    app.dependency_overrides[get_destinations] = lambda: destinations or {}
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_semantic_search_returns_top_match():
    client = _client()
    response = client.post("/search/semantic", json={"query": "beach", "top_k": 3})
    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) >= 1
    top = body["results"][0]
    assert top["id"] == "doc-beach"
    assert top["score"] > 0.99


def test_semantic_search_respects_top_k():
    client = _client()
    response = client.post("/search/semantic", json={"query": "beach", "top_k": 2})
    assert response.status_code == 200
    assert len(response.json()["results"]) == 2


def test_semantic_search_results_ordered_by_score():
    client = _client()
    response = client.post("/search/semantic", json={"query": "beach", "top_k": 3})
    scores = [r["score"] for r in response.json()["results"]]
    assert scores == sorted(scores, reverse=True)


def test_semantic_search_payload_populates_metadata():
    client = _client()
    response = client.post("/search/semantic", json={"query": "beach", "top_k": 1})
    top = response.json()["results"][0]
    assert top["name"] == "Playa"
    assert top["country"] == "ES"
    assert top["image_urls"] == ["a.jpg"]


def test_semantic_search_enriches_description_from_destinations():
    destinations = {
        "doc-beach": {
            "name": "Playa",
            "country": "ES",
            "description": "Arena fina y aguas cristalinas.",
            "image_urls": [],
        }
    }
    client = _client(destinations=destinations)
    response = client.post("/search/semantic", json={"query": "beach", "top_k": 1})
    top = response.json()["results"][0]
    assert top["description"] == "Arena fina y aguas cristalinas."


def test_semantic_search_default_top_k_is_ten():
    client = _client()
    response = client.post("/search/semantic", json={"query": "beach"})
    assert response.status_code == 200
    assert len(response.json()["results"]) <= 10


def test_semantic_search_requires_query():
    client = _client()
    response = client.post("/search/semantic", json={"top_k": 3})
    assert response.status_code == 422


def test_semantic_search_rejects_empty_query():
    client = _client()
    response = client.post("/search/semantic", json={"query": "", "top_k": 3})
    assert response.status_code == 422


def test_semantic_search_rejects_top_k_out_of_range():
    client = _client()
    too_big = client.post("/search/semantic", json={"query": "beach", "top_k": 500})
    too_small = client.post("/search/semantic", json={"query": "beach", "top_k": 0})
    assert too_big.status_code == 422
    assert too_small.status_code == 422
