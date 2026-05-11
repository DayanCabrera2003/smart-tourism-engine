"""Tests for T094 - pseudo-collaborative recommender."""
from __future__ import annotations

from typing import Optional

from src.recommendation.collaborative import CollaborativeRecommender
from src.recommendation.synthetic_profiles import SYNTHETIC_PROFILES
from src.recommendation.user_profile import UserProfile


class _FakeEmbedder:
    """Deterministic embedder driven by a token → vector dictionary.

    Unknown tokens fall back to a zero vector of the dimension declared
    by ``default_dim`` so the embedder never produces mismatched
    dimensions across the synthetic personas catalog.
    """

    def __init__(self, vocab: dict[str, list[float]], default_dim: int = 2):
        self._vocab = vocab
        self._default_dim = default_dim

    def embed(self, text: str) -> list[float]:
        if text in self._vocab:
            return list(self._vocab[text])
        return [0.0] * self._default_dim


class _FakeStore:
    def __init__(self, hits: list[tuple[object, float, dict[str, object]]]):
        self.hits = hits
        self.calls = 0

    def search(
        self,
        collection: str,
        query_vector: list[float],
        *,
        top_k: int = 10,
        score_threshold: Optional[float] = None,
    ) -> list[tuple[object, float, dict[str, object]]]:
        self.calls += 1
        return list(self.hits[:top_k])


def _make_recommender(store: _FakeStore, embedder: _FakeEmbedder) -> CollaborativeRecommender:
    return CollaborativeRecommender(embedder, store, collection="destinations_text")


def _build_unique_vocab() -> dict[str, list[float]]:
    """Assign every persona-tag to one of six orthogonal directions.

    Each persona gets its own direction so cosine similarity is exactly
    1.0 for the matched persona and lower for the rest. Tags that appear
    in more than one persona end up belonging to the persona we list
    last; that is fine because we feed the user a tag that is exclusive
    to the persona we want to match.
    """
    persona_axes = {
        "mochilero": [1.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        "familia": [0.0, 1.0, 0.0, 0.0, 0.0, 0.0],
        "luna_de_miel": [0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
        "aventurero": [0.0, 0.0, 0.0, 1.0, 0.0, 0.0],
        "cultural": [0.0, 0.0, 0.0, 0.0, 1.0, 0.0],
        "lujo": [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
    }
    vocab: dict[str, list[float]] = {}
    for persona_id, axis in persona_axes.items():
        for tag in SYNTHETIC_PROFILES[persona_id].interests:
            vocab[tag] = axis
    return vocab


def test_closest_persona_matches_user_interest() -> None:
    vocab = _build_unique_vocab()
    # "hoteles 5 estrellas" is exclusive to the lujo persona.
    vocab["hoteles 5 estrellas"] = [0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
    embedder = _FakeEmbedder(vocab, default_dim=6)
    store = _FakeStore([])
    recommender = _make_recommender(store, embedder)
    profile = UserProfile(id="u1", interests=["hoteles 5 estrellas"])

    assert recommender.closest_persona(profile) == "lujo"


def test_closest_persona_returns_none_without_signal() -> None:
    embedder = _FakeEmbedder({})
    store = _FakeStore([])
    recommender = _make_recommender(store, embedder)
    assert recommender.closest_persona(UserProfile(id="u1")) is None


def test_recommend_delegates_to_content_based_via_persona() -> None:
    vocab = _build_unique_vocab()
    vocab["hoteles 5 estrellas"] = [0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
    embedder = _FakeEmbedder(vocab, default_dim=6)
    hits = [
        ("uuid-1", 0.95, {"slug": "venice-it", "name": "Venecia"}),
        ("uuid-2", 0.80, {"slug": "santorini-gr"}),
    ]
    store = _FakeStore(hits)
    recommender = _make_recommender(store, embedder)
    profile = UserProfile(id="u1", interests=["hoteles 5 estrellas"])

    out = recommender.recommend(profile, top_k=2)

    assert [doc_id for doc_id, _, _ in out] == ["venice-it", "santorini-gr"]
    assert store.calls == 1


def test_recommend_returns_empty_without_signal() -> None:
    embedder = _FakeEmbedder({})
    store = _FakeStore([("uuid-1", 0.5, {"slug": "any"})])
    recommender = _make_recommender(store, embedder)
    assert recommender.recommend(UserProfile(id="u1"), top_k=5) == []
    assert store.calls == 0


def test_recommend_propagates_user_history_as_exclusion() -> None:
    vocab = _build_unique_vocab()
    vocab["hoteles 5 estrellas"] = [0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
    embedder = _FakeEmbedder(vocab, default_dim=6)
    hits = [
        ("uuid-1", 0.95, {"slug": "venice-it"}),
        ("uuid-2", 0.80, {"slug": "santorini-gr"}),
    ]
    store = _FakeStore(hits)
    recommender = _make_recommender(store, embedder)
    profile = UserProfile(
        id="u1", interests=["hoteles 5 estrellas"], history=["venice-it"]
    )

    out = recommender.recommend(profile, top_k=2)

    assert [doc_id for doc_id, _, _ in out] == ["santorini-gr"]
