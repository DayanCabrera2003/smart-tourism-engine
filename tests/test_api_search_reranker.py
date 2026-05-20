"""T12 - Tests for the Reranker wired into the search endpoints.

The Reranker mixes the retriever's relevance score with popularity and
freshness signals read from SQLite. With ``use_reranker=True`` (the
default), a more popular destination should win against a less popular
one even when both have the same lexical relevance.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.main import app, get_destinations, get_index, get_retriever_factory
from src.indexing.inverted_index import InvertedIndex
from src.retrieval.extended_boolean import ExtendedBoolean


def _build_index_with_tie() -> InvertedIndex:
    """Two docs with identical lexical weight for the query 'beach'."""
    idx = InvertedIndex()
    idx.add_document("doc-popular", ["beach"])
    idx.add_document("doc-niche", ["beach"])
    idx.compute_tf_idf()
    return idx


def _client(destinations: dict | None = None) -> TestClient:
    idx = _build_index_with_tie()
    app.dependency_overrides[get_index] = lambda: idx

    def _factory():
        return lambda p: ExtendedBoolean(p=p)

    app.dependency_overrides[get_retriever_factory] = _factory
    app.dependency_overrides[get_destinations] = lambda: destinations or {}
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_reranker_promotes_more_popular_tie_breaker() -> None:
    """Two docs tied on relevance: the more popular one wins when reranker on."""
    destinations = {
        "doc-popular": {
            "name": "Popular",
            "country": "ES",
            "description": "x" * 600,
            "image_urls": [],
            "popularity": 0.9,
            "fetched_at": "2026-05-01T00:00:00Z",
        },
        "doc-niche": {
            "name": "Niche",
            "country": "ES",
            "description": "x" * 600,
            "image_urls": [],
            "popularity": 0.1,
            "fetched_at": "2026-05-01T00:00:00Z",
        },
    }
    client = _client(destinations=destinations)
    # Default is False; flip on explicitly for the tie-breaker test.
    response = client.post(
        "/search",
        json={"query": "beach", "top_k": 2, "use_reranker": True},
    )
    assert response.status_code == 200
    ids = [r["id"] for r in response.json()["results"]]
    assert ids == ["doc-popular", "doc-niche"]


def test_use_reranker_false_preserves_pure_relevance() -> None:
    """When disabled, the tie remains a tie and ranking does not move."""
    destinations = {
        "doc-popular": {
            "name": "Popular",
            "country": "ES",
            "description": "x" * 600,
            "image_urls": [],
            "popularity": 0.9,
            "fetched_at": "2026-05-01T00:00:00Z",
        },
        "doc-niche": {
            "name": "Niche",
            "country": "ES",
            "description": "x" * 600,
            "image_urls": [],
            "popularity": 0.1,
            "fetched_at": "2026-05-01T00:00:00Z",
        },
    }
    client = _client(destinations=destinations)
    response = client.post(
        "/search",
        json={"query": "beach", "top_k": 2, "use_reranker": False},
    )
    assert response.status_code == 200
    # Both have identical lexical relevance; their scores must match.
    results = response.json()["results"]
    assert len(results) == 2
    assert results[0]["score"] == results[1]["score"]


def test_reranker_default_is_disabled() -> None:
    """A request without use_reranker leaves the retriever order intact.

    The reranker degraded P@10/nDCG@10 on the v2 eval set against the
    957-doc corpus, so the API default flipped to False. The two docs
    have identical lexical relevance for 'beach'; without the reranker
    the returned order matches the underlying retriever order (which
    is currently doc-niche, doc-popular for this lexically-tied pair).
    """
    destinations = {
        "doc-popular": {
            "name": "Popular",
            "country": "ES",
            "description": "x" * 600,
            "image_urls": [],
            "popularity": 0.99,
            "fetched_at": "2026-05-01T00:00:00Z",
        },
        "doc-niche": {
            "name": "Niche",
            "country": "ES",
            "description": "x" * 600,
            "image_urls": [],
            "popularity": 0.0,
            "fetched_at": "2026-05-01T00:00:00Z",
        },
    }
    client = _client(destinations=destinations)
    response = client.post("/search", json={"query": "beach", "top_k": 2})
    results = response.json()["results"]
    # Equal relevance, no reranker → both docs returned, scores equal.
    assert len(results) == 2
    assert results[0]["score"] == results[1]["score"]
