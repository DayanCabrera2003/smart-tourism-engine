"""Tests for T095 - hybrid recommender (content-based + pseudo-collaborative)."""
from __future__ import annotations

import math

import pytest

from src.recommendation.content_based import RecommendationHit
from src.recommendation.hybrid import HybridRecommender
from src.recommendation.user_profile import UserProfile


class _FakeBranch:
    """In-memory recommender used to drive the hybrid layer in tests."""

    def __init__(self, hits: list[RecommendationHit]):
        self.hits = hits
        self.last_top_k: int | None = None
        self.last_profile: UserProfile | None = None

    def recommend(self, profile: UserProfile, *, top_k: int = 10) -> list[RecommendationHit]:
        self.last_profile = profile
        self.last_top_k = top_k
        return list(self.hits[:top_k])


def _profile() -> UserProfile:
    return UserProfile(id="u1", interests=["playa"])


def test_alpha_outside_unit_interval_raises() -> None:
    content = _FakeBranch([])
    collab = _FakeBranch([])
    with pytest.raises(ValueError):
        HybridRecommender(content, collab, alpha=1.5)  # type: ignore[arg-type]


def test_alpha_zero_returns_collaborative_ranking() -> None:
    content = _FakeBranch([])
    collab = _FakeBranch(
        [
            ("playa-cancun", 0.9, {"slug": "playa-cancun"}),
            ("playa-tulum", 0.7, {"slug": "playa-tulum"}),
        ]
    )
    hybrid = HybridRecommender(content, collab, alpha=0.0)  # type: ignore[arg-type]
    out = hybrid.recommend(_profile(), top_k=2)
    assert [doc_id for doc_id, _, _ in out] == ["playa-cancun", "playa-tulum"]
    # With alpha=0 the fused score equals the collaborative score.
    assert math.isclose(out[0][1], 0.9)


def test_alpha_one_returns_content_ranking() -> None:
    content = _FakeBranch(
        [
            ("venice-it", 0.9, {"slug": "venice-it"}),
        ]
    )
    collab = _FakeBranch(
        [
            ("santorini-gr", 0.8, {"slug": "santorini-gr"}),
        ]
    )
    hybrid = HybridRecommender(content, collab, alpha=1.0)  # type: ignore[arg-type]
    out = hybrid.recommend(_profile(), top_k=1)
    assert [doc_id for doc_id, _, _ in out] == ["venice-it"]
    assert math.isclose(out[0][1], 0.9)


def test_fusion_combines_overlapping_documents() -> None:
    content = _FakeBranch([("dest-a", 1.0, {"slug": "dest-a"})])
    collab = _FakeBranch([("dest-a", 0.5, {"slug": "dest-a"})])
    hybrid = HybridRecommender(content, collab, alpha=0.5)  # type: ignore[arg-type]
    out = hybrid.recommend(_profile(), top_k=1)
    assert len(out) == 1
    # 0.5 * 1.0 + 0.5 * 0.5 = 0.75
    assert math.isclose(out[0][1], 0.75)


def test_fusion_handles_disjoint_documents() -> None:
    content = _FakeBranch([("dest-a", 1.0, {"slug": "dest-a"})])
    collab = _FakeBranch([("dest-b", 1.0, {"slug": "dest-b"})])
    hybrid = HybridRecommender(content, collab, alpha=0.5)  # type: ignore[arg-type]
    out = hybrid.recommend(_profile(), top_k=2)
    ids = {doc_id for doc_id, _, _ in out}
    assert ids == {"dest-a", "dest-b"}
    # Each document is scored against a missing branch (contributes 0):
    # alpha * 1.0 + (1 - alpha) * 0.0 = 0.5
    for _, score, _ in out:
        assert math.isclose(score, 0.5)


def test_recommend_returns_empty_when_both_branches_empty() -> None:
    content = _FakeBranch([])
    collab = _FakeBranch([])
    hybrid = HybridRecommender(content, collab, alpha=0.4)  # type: ignore[arg-type]
    assert hybrid.recommend(_profile(), top_k=3) == []


def test_recommend_overfetches_candidates() -> None:
    content = _FakeBranch([])
    collab = _FakeBranch([])
    hybrid = HybridRecommender(content, collab, alpha=0.5)  # type: ignore[arg-type]
    hybrid.recommend(_profile(), top_k=5)
    # Each branch should be asked for >= top_k candidates.
    assert content.last_top_k is not None and content.last_top_k >= 5
    assert collab.last_top_k is not None and collab.last_top_k >= 5
