"""Tests for T102 - MMR diversification."""
from __future__ import annotations

import pytest

from src.retrieval.diversify import apply_mmr


def test_empty_hits_returns_empty() -> None:
    assert apply_mmr([], {}) == []


def test_invalid_lambda_raises() -> None:
    with pytest.raises(ValueError):
        apply_mmr([("a", 0.5)], {"a": [1.0, 0.0]}, lambda_=1.5)
    with pytest.raises(ValueError):
        apply_mmr([("a", 0.5)], {"a": [1.0, 0.0]}, lambda_=-0.1)


def test_lambda_one_preserves_relevance_order() -> None:
    hits = [("a", 0.9), ("b", 0.5), ("c", 0.1)]
    emb = {
        "a": [1.0, 0.0],
        "b": [0.99, 0.01],  # near-duplicate of a
        "c": [0.0, 1.0],
    }
    out = apply_mmr(hits, emb, lambda_=1.0)
    assert [d for d, _ in out] == ["a", "b", "c"]


def test_lambda_zero_maximizes_diversity() -> None:
    # All three hits have similar relevance; embeddings are arranged so
    # that picking by diversity yields the orthogonal corners first.
    hits = [("near", 0.6), ("far", 0.55), ("similar", 0.5)]
    emb = {
        "near": [1.0, 0.0, 0.0],
        "similar": [0.99, 0.01, 0.0],
        "far": [0.0, 1.0, 0.0],
    }
    out = apply_mmr(hits, emb, lambda_=0.0)
    ids = [d for d, _ in out]
    # First pick is the highest relevance ("near"). Second should be
    # the most diverse ("far"), not the near-duplicate ("similar").
    assert ids[0] == "near"
    assert ids[1] == "far"


def test_default_lambda_balances_relevance_and_diversity() -> None:
    hits = [("a", 0.9), ("a_dup", 0.85), ("b", 0.5)]
    emb = {
        "a": [1.0, 0.0],
        "a_dup": [0.99, 0.01],
        "b": [0.0, 1.0],
    }
    out = apply_mmr(hits, emb)
    ids = [d for d, _ in out]
    # The duplicate should not sit right next to the original at the
    # default lambda (0.7); the diverse pick comes second.
    assert ids[:2] == ["a", "b"]


def test_top_k_caps_output() -> None:
    hits = [("a", 0.9), ("b", 0.5), ("c", 0.1)]
    emb = {"a": [1.0, 0.0], "b": [0.0, 1.0], "c": [1.0, 1.0]}
    out = apply_mmr(hits, emb, top_k=2)
    assert len(out) == 2


def test_destinations_without_embedding_are_appended() -> None:
    hits = [("a", 0.9), ("b", 0.5), ("opaque", 0.1)]
    emb = {"a": [1.0, 0.0], "b": [0.0, 1.0]}
    out = apply_mmr(hits, emb)
    ids = [d for d, _ in out]
    # Opaque destinations get appended at the end.
    assert ids[-1] == "opaque"
    assert set(ids[:-1]) == {"a", "b"}


def test_opaque_destinations_respect_top_k() -> None:
    hits = [("a", 0.9), ("opaque", 0.1)]
    emb = {"a": [1.0, 0.0]}
    out = apply_mmr(hits, emb, top_k=1)
    # Only one slot, occupied by the embedded hit.
    assert [d for d, _ in out] == ["a"]


def test_relevance_scores_preserved() -> None:
    hits = [("a", 0.9), ("b", 0.5)]
    emb = {"a": [1.0, 0.0], "b": [0.0, 1.0]}
    out = apply_mmr(hits, emb)
    scores = {d: s for d, s in out}
    assert scores["a"] == 0.9
    assert scores["b"] == 0.5
