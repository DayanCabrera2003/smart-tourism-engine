"""Tests for T093 - content-based recommender."""
from __future__ import annotations

from typing import Optional

from src.recommendation.content_based import ContentBasedRecommender
from src.recommendation.user_profile import UserProfile


class _FakeEmbedder:
    def __init__(self, vocab: dict[str, list[float]]):
        self._vocab = vocab

    def embed(self, text: str) -> list[float]:
        return list(self._vocab[text])


class _FakeStore:
    """Minimal stand-in for VectorStore that returns canned hits.

    The fake mirrors the contract of ``VectorStore.search`` so the
    recommender can be wired without a running Qdrant.
    """

    def __init__(self, hits: list[tuple[object, float, dict[str, object]]]):
        self.hits = hits
        self.last_query: list[float] | None = None
        self.last_top_k: int | None = None
        self.last_collection: str | None = None

    def search(
        self,
        collection: str,
        query_vector: list[float],
        *,
        top_k: int = 10,
        score_threshold: Optional[float] = None,
    ) -> list[tuple[object, float, dict[str, object]]]:
        self.last_collection = collection
        self.last_query = list(query_vector)
        self.last_top_k = top_k
        return list(self.hits[:top_k])


def test_recommend_returns_top_k_hits_with_slug_id() -> None:
    embedder = _FakeEmbedder({"playa": [1.0, 0.0]})
    hits = [
        ("uuid-1", 0.95, {"slug": "playa-cancun", "name": "Cancún"}),
        ("uuid-2", 0.80, {"slug": "playa-tulum", "name": "Tulum"}),
        ("uuid-3", 0.60, {"slug": "playa-mazatlan", "name": "Mazatlán"}),
    ]
    store = _FakeStore(hits)
    recommender = ContentBasedRecommender(embedder, store, collection="destinations_text")
    profile = UserProfile(id="u1", interests=["playa"])

    out = recommender.recommend(profile, top_k=2)

    assert [doc_id for doc_id, _, _ in out] == ["playa-cancun", "playa-tulum"]
    assert all(0.0 <= score <= 1.0 for _, score, _ in out)
    assert store.last_collection == "destinations_text"


def test_recommend_skips_history_destinations() -> None:
    embedder = _FakeEmbedder({"playa": [1.0, 0.0]})
    hits = [
        ("uuid-1", 0.95, {"slug": "playa-cancun"}),
        ("uuid-2", 0.80, {"slug": "playa-tulum"}),
        ("uuid-3", 0.60, {"slug": "playa-mazatlan"}),
    ]
    store = _FakeStore(hits)
    recommender = ContentBasedRecommender(embedder, store)
    profile = UserProfile(id="u1", interests=["playa"], history=["playa-cancun"])

    out = recommender.recommend(profile, top_k=2)

    ids = [doc_id for doc_id, _, _ in out]
    assert "playa-cancun" not in ids
    assert ids == ["playa-tulum", "playa-mazatlan"]


def test_recommend_respects_extra_exclude() -> None:
    embedder = _FakeEmbedder({"playa": [1.0, 0.0]})
    hits = [
        ("uuid-1", 0.95, {"slug": "playa-cancun"}),
        ("uuid-2", 0.80, {"slug": "playa-tulum"}),
    ]
    store = _FakeStore(hits)
    recommender = ContentBasedRecommender(embedder, store)
    profile = UserProfile(id="u1", interests=["playa"])

    out = recommender.recommend(profile, top_k=2, exclude={"playa-tulum"})

    assert [doc_id for doc_id, _, _ in out] == ["playa-cancun"]


def test_recommend_returns_empty_when_no_signal() -> None:
    embedder = _FakeEmbedder({})
    store = _FakeStore([("uuid-1", 0.5, {"slug": "any"})])
    recommender = ContentBasedRecommender(embedder, store)
    profile = UserProfile(id="u1")  # no interests, no history

    assert recommender.recommend(profile, top_k=5) == []
    # Store must not be queried when there is no signal to embed.
    assert store.last_query is None


def test_recommend_falls_back_to_point_id_when_slug_missing() -> None:
    embedder = _FakeEmbedder({"montaña": [0.0, 1.0]})
    hits = [("a1b2", 0.7, {"name": "Andes"})]
    store = _FakeStore(hits)
    recommender = ContentBasedRecommender(embedder, store)
    profile = UserProfile(id="u1", interests=["montaña"])

    out = recommender.recommend(profile, top_k=1)
    assert out and out[0][0] == "a1b2"
