"""Integracion: /search/hybrid y /search/semantic disparan fallback web
cuando el cross-encoder reporta baja relevancia."""
from __future__ import annotations

import math

from fastapi.testclient import TestClient

from src.api.main import (
    app,
    get_cross_encoder,
    get_destinations,
    get_embedder,
    get_index,
    get_retriever_factory,
    get_semantic_collection,
    get_vector_store,
    get_web_client,
)
from src.indexing.embed_destinations import slug_to_uuid
from src.indexing.inverted_index import InvertedIndex
from src.indexing.vector_store import VectorStore
from src.retrieval.extended_boolean import ExtendedBoolean
from src.web_search.tavily import WebResult

COLLECTION = "fallback_test"
DIM = 4


class _StubEmbedder:
    def embed(self, text, mode="query"):
        del mode
        raw = [float((ord(c) % 7) + 1) for c in (text.strip().lower() or "x")[:DIM]]
        raw.extend([0.0] * (DIM - len(raw)))
        norm = math.sqrt(sum(v * v for v in raw)) or 1.0
        return [v / norm for v in raw]


class _FakeCrossEncoder:
    def __init__(self, score):
        self._score = score
        self.calls = 0

    def rerank(self, query, candidates):
        self.calls += 1
        return [(doc_id, self._score) for doc_id, _text in candidates]


class _FakeWebClient:
    def __init__(self):
        self.calls = 0

    def search(self, query, *, max_results=5):
        self.calls += 1
        return [WebResult(title="Alaska Hotels", snippet="Lodges near Denali.", url="http://x/1")]


def _build_index():
    idx = InvertedIndex()
    idx.add_document("doc-bangkok", ["khaosan", "bangkok", "hotel"])
    idx.compute_tf_idf()
    return idx


def _build_store():
    store = VectorStore(url=":memory:")
    store.create_collection(COLLECTION, vector_size=DIM)
    emb = _StubEmbedder()
    store.upsert(
        COLLECTION,
        [(slug_to_uuid("doc-bangkok"), emb.embed("khaosan"),
          {"slug": "doc-bangkok", "name": "Calle Khaosan", "country": "Thailand"})],
    )
    return store


def _client(*, ce_score, web_client):
    destinations = {
        "doc-bangkok": {"name": "Calle Khaosan", "country": "Thailand",
                        "description": "Calle en Bangkok."}
    }
    app.dependency_overrides[get_vector_store] = lambda: _build_store()
    app.dependency_overrides[get_embedder] = lambda: _StubEmbedder()
    app.dependency_overrides[get_semantic_collection] = lambda: COLLECTION
    app.dependency_overrides[get_index] = lambda: _build_index()
    app.dependency_overrides[get_retriever_factory] = lambda: lambda p: ExtendedBoolean(p=p)
    app.dependency_overrides[get_destinations] = lambda: destinations
    cross_encoder = _FakeCrossEncoder(ce_score)
    app.dependency_overrides[get_cross_encoder] = lambda: cross_encoder
    app.dependency_overrides[get_web_client] = lambda: web_client
    client = TestClient(app)
    client.cross_encoder = cross_encoder
    return client


def teardown_function():
    app.dependency_overrides.clear()


def test_hybrid_triggers_web_fallback_on_low_relevance():
    web = _FakeWebClient()
    client = _client(ce_score=0.02, web_client=web)
    resp = client.post("/search/hybrid", json={"query": "hoteles en alaska", "top_k": 5})
    assert resp.status_code == 200
    assert web.calls == 1
    results = resp.json()["results"]
    # Solo web: el local irrelevante (doc-bangkok) se descarta.
    assert results and all(r["from_web"] for r in results)
    assert not any(r["id"] == "doc-bangkok" for r in results)


def test_boolean_triggers_web_fallback_on_low_relevance():
    web = _FakeWebClient()
    client = _client(ce_score=0.02, web_client=web)
    resp = client.post("/search", json={"query": "hoteles en alaska", "top_k": 5})
    assert resp.status_code == 200
    assert web.calls == 1
    results = resp.json()["results"]
    assert results and all(r["from_web"] for r in results)


def test_hybrid_no_fallback_when_relevant():
    web = _FakeWebClient()
    client = _client(ce_score=0.90, web_client=web)
    resp = client.post("/search/hybrid", json={"query": "khaosan", "top_k": 5})
    assert resp.status_code == 200
    assert web.calls == 0
    assert not any(r["from_web"] for r in resp.json()["results"])


def test_semantic_triggers_web_fallback_on_low_relevance():
    web = _FakeWebClient()
    client = _client(ce_score=0.02, web_client=web)
    resp = client.post("/search/semantic", json={"query": "hoteles en alaska", "top_k": 5})
    assert resp.status_code == 200
    assert web.calls == 1
    results = resp.json()["results"]
    assert results and all(r["from_web"] for r in results)


def test_search_no_fallback_when_web_client_absent():
    client = _client(ce_score=0.02, web_client=None)
    resp = client.post("/search/hybrid", json={"query": "hoteles en alaska", "top_k": 5})
    assert resp.status_code == 200
    assert not any(r["from_web"] for r in resp.json()["results"])
    # Sin web client el gate se salta entero: no se gasta el cross-encoder.
    assert client.cross_encoder.calls == 0
