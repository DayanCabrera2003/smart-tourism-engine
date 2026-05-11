"""Tests for T101 - combined re-ranker."""
from __future__ import annotations

import math

import pytest

from src.retrieval.reranker import Reranker, RerankWeights, cosine_similarity


def test_cosine_unit_vectors() -> None:
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)


def test_cosine_zero_vector_returns_zero() -> None:
    assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_cosine_dimension_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        cosine_similarity([1.0, 0.0], [1.0])


def test_rerank_weights_validate_non_negative() -> None:
    with pytest.raises(ValueError):
        RerankWeights(relevance=-0.1)


def test_rerank_weights_validate_total_positive() -> None:
    with pytest.raises(ValueError):
        RerankWeights(relevance=0.0, popularity=0.0, freshness=0.0, personalization=0.0)


def test_rerank_weights_normalize_to_unit_sum() -> None:
    w = RerankWeights(relevance=1.0, popularity=1.0, freshness=1.0, personalization=1.0)
    n = w.normalized()
    assert math.isclose(n.total(), 1.0)
    assert math.isclose(n.relevance, 0.25)


def test_rerank_empty_hits_returns_empty() -> None:
    r = Reranker()
    assert r.rerank([]) == []


def test_rerank_pure_relevance_preserves_order() -> None:
    weights = RerankWeights(
        relevance=1.0, popularity=0.0, freshness=0.0, personalization=0.0
    )
    r = Reranker(weights=weights)
    hits = [("a", 0.9), ("b", 0.5), ("c", 0.1)]
    out = r.rerank(hits)
    assert [d for d, _ in out] == ["a", "b", "c"]


def test_rerank_popularity_breaks_relevance_tie() -> None:
    weights = RerankWeights(
        relevance=0.5, popularity=0.5, freshness=0.0, personalization=0.0
    )
    popularity = {"a": 0.1, "b": 0.9}
    r = Reranker(weights=weights, popularity=popularity)
    out = r.rerank([("a", 0.5), ("b", 0.5)])
    # b has higher popularity so it should beat a despite equal relevance.
    assert [d for d, _ in out] == ["b", "a"]


def test_rerank_freshness_boosts_recent_destinations() -> None:
    weights = RerankWeights(
        relevance=0.5, popularity=0.0, freshness=0.5, personalization=0.0
    )
    freshness = {"old": 0.1, "fresh": 0.9}
    r = Reranker(weights=weights, freshness=freshness)
    out = r.rerank([("old", 0.5), ("fresh", 0.5)])
    assert out[0][0] == "fresh"


def test_rerank_missing_signals_count_as_zero() -> None:
    weights = RerankWeights(
        relevance=0.5, popularity=0.5, freshness=0.0, personalization=0.0
    )
    popularity = {"a": 0.5}  # b not in the map
    r = Reranker(weights=weights, popularity=popularity)
    out = r.rerank([("a", 0.1), ("b", 0.1)])
    # a benefits from popularity, b does not.
    assert out[0][0] == "a"


def test_rerank_personalization_drops_when_no_user_embedding() -> None:
    # Personalization weight should be redistributed so the final
    # score still lives in [0, 1] when the user is anonymous.
    weights = RerankWeights(
        relevance=0.5, popularity=0.0, freshness=0.0, personalization=0.5
    )
    r = Reranker(weights=weights)
    out = r.rerank([("a", 0.8)])
    # Anonymous user: relevance becomes the only signal so score == relevance.
    assert out[0][1] == pytest.approx(0.8)


def test_rerank_personalization_boosts_aligned_destination() -> None:
    weights = RerankWeights(
        relevance=0.5, popularity=0.0, freshness=0.0, personalization=0.5
    )
    embeddings = {
        "near": [1.0, 0.0],
        "far": [0.0, 1.0],
    }
    r = Reranker(
        weights=weights,
        destination_embeddings=embeddings,
        user_embedding=[1.0, 0.0],
    )
    out = r.rerank([("near", 0.4), ("far", 0.4)])
    assert out[0][0] == "near"


def test_rerank_clamps_negative_cosine_to_zero() -> None:
    weights = RerankWeights(
        relevance=0.5, popularity=0.0, freshness=0.0, personalization=0.5
    )
    embeddings = {
        "anti": [-1.0, 0.0],
        "neutral": [0.0, 1.0],
    }
    r = Reranker(
        weights=weights,
        destination_embeddings=embeddings,
        user_embedding=[1.0, 0.0],
    )
    out = r.rerank([("anti", 0.5), ("neutral", 0.5)])
    # Cosine(anti, user) = -1.0 but is clamped to 0, so both should
    # tie on personalization. Order is then determined by sort
    # stability against equal scores.
    scores = {d: s for d, s in out}
    assert math.isclose(scores["anti"], scores["neutral"])


def test_rerank_final_score_stays_in_unit_interval() -> None:
    r = Reranker(
        popularity={"a": 1.0},
        freshness={"a": 1.0},
        destination_embeddings={"a": [1.0, 0.0]},
        user_embedding=[1.0, 0.0],
    )
    out = r.rerank([("a", 1.0)])
    assert 0.0 <= out[0][1] <= 1.0


def test_rerank_does_not_mutate_input() -> None:
    hits = [("a", 0.1), ("b", 0.9)]
    Reranker().rerank(hits)
    assert hits == [("a", 0.1), ("b", 0.9)]
