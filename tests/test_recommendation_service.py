"""Tests for the RecommendationService and build_request_profile helper (T096)."""
from __future__ import annotations

from typing import Optional

from src.recommendation.service import (
    RecommendationService,
    build_request_profile,
)
from src.recommendation.synthetic_profiles import SYNTHETIC_PROFILES
from src.recommendation.user_profile import UserProfile


def test_build_request_profile_returns_none_when_no_signal() -> None:
    assert build_request_profile(None, [], []) is None


def test_build_request_profile_uses_synthetic_persona() -> None:
    profile = build_request_profile("synthetic:mochilero", [], [])
    assert profile is not None
    assert profile.id == "synthetic:mochilero"
    assert "aventura" in profile.interests


def test_build_request_profile_resolves_persona_without_prefix() -> None:
    profile = build_request_profile("mochilero", [], [])
    assert profile is not None
    assert profile.id == "synthetic:mochilero"


def test_build_request_profile_merges_extra_interests_and_history() -> None:
    profile = build_request_profile(
        "mochilero",
        interests=["surf", "aventura"],  # "aventura" already in mochilero
        history=["cusco-pe"],
    )
    assert profile is not None
    # extra tag appended without duplicating
    assert profile.interests.count("aventura") == 1
    assert "surf" in profile.interests
    assert profile.history == ["cusco-pe"]


def test_build_request_profile_handles_anonymous_user() -> None:
    profile = build_request_profile(None, interests=["playa"], history=[])
    assert profile is not None
    assert profile.id == "anonymous"
    assert profile.interests == ["playa"]


def test_build_request_profile_strips_blank_entries() -> None:
    profile = build_request_profile(None, interests=["  ", "playa", ""], history=[" "])
    assert profile is not None
    assert profile.interests == ["playa"]
    assert profile.history == []


class _FakeEmbedder:
    def __init__(self, vocab: dict[str, list[float]], default_dim: int = 6):
        self._vocab = vocab
        self._default_dim = default_dim

    def embed(self, text: str) -> list[float]:
        if text in self._vocab:
            return list(self._vocab[text])
        return [0.0] * self._default_dim


class _FakeStore:
    def __init__(self, hits: list[tuple[object, float, dict[str, object]]]):
        self.hits = hits

    def search(
        self,
        collection: str,
        query_vector: list[float],
        *,
        top_k: int = 10,
        score_threshold: Optional[float] = None,
    ) -> list[tuple[object, float, dict[str, object]]]:
        return list(self.hits[:top_k])


def _unique_vocab() -> dict[str, list[float]]:
    """Map every persona tag to one of six orthogonal directions."""
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


def test_service_returns_empty_for_missing_profile() -> None:
    embedder = _FakeEmbedder({})
    store = _FakeStore([])
    service = RecommendationService(embedder, store)
    outcome = service.recommend(None, top_k=5, mode="hybrid", alpha=0.5)
    assert outcome.empty is True
    assert outcome.hits == []
    assert outcome.persona is None


def test_service_dispatches_content_mode_and_returns_persona_label() -> None:
    vocab = _unique_vocab()
    vocab["surf"] = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # aligned with mochilero
    embedder = _FakeEmbedder(vocab)
    hits = [("uuid-1", 0.9, {"slug": "tofino-ca"})]
    store = _FakeStore(hits)
    service = RecommendationService(embedder, store)
    profile = UserProfile(id="u1", interests=["surf"])

    outcome = service.recommend(profile, top_k=1, mode="content", alpha=0.5)
    assert outcome.persona == "synthetic:mochilero"
    assert len(outcome.hits) == 1
    assert outcome.hits[0][0] == "tofino-ca"
    assert outcome.empty is False


def test_service_dispatches_collaborative_mode() -> None:
    vocab = _unique_vocab()
    vocab["surf"] = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    embedder = _FakeEmbedder(vocab)
    hits = [("uuid-1", 0.85, {"slug": "queenstown-nz"})]
    store = _FakeStore(hits)
    service = RecommendationService(embedder, store)
    profile = UserProfile(id="u1", interests=["surf"])

    outcome = service.recommend(profile, top_k=1, mode="collaborative", alpha=0.5)
    assert outcome.persona == "synthetic:mochilero"
    assert outcome.hits and outcome.hits[0][0] == "queenstown-nz"


def test_service_dispatches_hybrid_mode_by_default() -> None:
    vocab = _unique_vocab()
    vocab["surf"] = [1.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    embedder = _FakeEmbedder(vocab)
    hits = [("uuid-1", 1.0, {"slug": "byron-au"})]
    store = _FakeStore(hits)
    service = RecommendationService(embedder, store)
    profile = UserProfile(id="u1", interests=["surf"])

    outcome = service.recommend(profile, top_k=1, mode="hybrid", alpha=0.5)
    assert outcome.hits and outcome.hits[0][0] == "byron-au"
    # alpha 0.5 with both branches scoring 1.0 gives fused = 1.0
    assert outcome.hits[0][1] == 1.0
