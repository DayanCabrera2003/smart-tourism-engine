"""Tests for T106 and T107 — evaluation metrics."""
from __future__ import annotations

import math

import pytest

from src.evaluation.metrics import (
    average_precision,
    dcg_at_k,
    f1_at_k,
    mean_average_precision,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)

# ─── Precision@k ────────────────────────────────────────────────────────────


def test_precision_at_k_perfect() -> None:
    assert precision_at_k(["a", "b", "c"], {"a", "b", "c"}, k=3) == 1.0


def test_precision_at_k_partial() -> None:
    assert precision_at_k(["a", "b", "x"], {"a", "b"}, k=3) == pytest.approx(2 / 3)


def test_precision_at_k_uses_top_k_only() -> None:
    # Document at rank 5 is relevant but k=3 must not count it.
    retrieved = ["x", "y", "z", "w", "a"]
    assert precision_at_k(retrieved, {"a"}, k=3) == 0.0


def test_precision_at_k_with_short_retrieved_list() -> None:
    # The retriever only returned 2 docs but the user asked for 5;
    # the denominator stays at k=5 to penalize the under-delivery.
    assert precision_at_k(["a", "b"], {"a", "b"}, k=5) == pytest.approx(2 / 5)


def test_precision_at_k_empty_relevant_returns_zero() -> None:
    assert precision_at_k(["a", "b"], set(), k=2) == 0.0


def test_precision_at_k_invalid_k_raises() -> None:
    with pytest.raises(ValueError):
        precision_at_k(["a"], {"a"}, k=0)
    with pytest.raises(ValueError):
        precision_at_k(["a"], {"a"}, k=-1)
    with pytest.raises(TypeError):
        precision_at_k(["a"], {"a"}, k=1.5)  # type: ignore[arg-type]


# ─── Recall@k ───────────────────────────────────────────────────────────────


def test_recall_at_k_perfect() -> None:
    assert recall_at_k(["a", "b", "c"], {"a", "b", "c"}, k=3) == 1.0


def test_recall_at_k_partial() -> None:
    assert recall_at_k(["a", "x"], {"a", "b"}, k=2) == 0.5


def test_recall_at_k_caps_at_one() -> None:
    # k larger than the relevant set still cannot exceed 1.0.
    assert recall_at_k(["a", "b"], {"a", "b"}, k=10) == 1.0


def test_recall_at_k_empty_relevant_returns_zero() -> None:
    assert recall_at_k(["a"], set(), k=1) == 0.0


# ─── F1@k ───────────────────────────────────────────────────────────────────


def test_f1_at_k_zero_when_no_hits() -> None:
    assert f1_at_k(["x"], {"a"}, k=1) == 0.0


def test_f1_at_k_matches_harmonic_mean() -> None:
    retrieved = ["a", "x", "b", "y"]
    relevant = {"a", "b", "c"}
    p = precision_at_k(retrieved, relevant, k=4)
    r = recall_at_k(retrieved, relevant, k=4)
    expected = 2 * p * r / (p + r)
    assert f1_at_k(retrieved, relevant, k=4) == pytest.approx(expected)


# ─── Average Precision / MAP ────────────────────────────────────────────────


def test_average_precision_classic_example() -> None:
    # Manning et al. AP example: retrieved = [R, N, R, N, N, R] over
    # relevant = 3, k effectively = 6. AP = (1/3) * (1/1 + 2/3 + 3/6).
    retrieved = ["a", "x", "b", "y", "z", "c"]
    relevant = {"a", "b", "c"}
    expected = (1.0 / 3) * (1 / 1 + 2 / 3 + 3 / 6)
    assert average_precision(retrieved, relevant) == pytest.approx(expected)


def test_average_precision_perfect() -> None:
    assert average_precision(["a", "b"], {"a", "b"}) == 1.0


def test_average_precision_no_relevant_retrieved() -> None:
    assert average_precision(["x", "y"], {"a"}) == 0.0


def test_average_precision_penalizes_missing_relevant() -> None:
    # If only 1 of 2 relevant documents is retrieved, AP is bounded by
    # 0.5 even if that single hit is at rank 1.
    assert average_precision(["a", "x", "y"], {"a", "b"}) == 0.5


def test_average_precision_empty_relevant_returns_zero() -> None:
    assert average_precision(["a"], set()) == 0.0


def test_mean_average_precision_averages_per_query() -> None:
    retrieved_per_query = [["a", "x"], ["x", "b"]]
    relevant_per_query = [{"a"}, {"b"}]
    # AP for first query = 1.0, AP for second = 0.5.
    assert mean_average_precision(retrieved_per_query, relevant_per_query) == pytest.approx(0.75)


def test_mean_average_precision_mismatched_lengths_raise() -> None:
    with pytest.raises(ValueError):
        mean_average_precision([["a"]], [{"a"}, {"b"}])


def test_mean_average_precision_empty_inputs_returns_zero() -> None:
    assert mean_average_precision([], []) == 0.0


# ─── Reciprocal Rank / MRR ──────────────────────────────────────────────────


def test_reciprocal_rank_first_hit_at_rank_one() -> None:
    assert reciprocal_rank(["a", "x"], {"a"}) == 1.0


def test_reciprocal_rank_first_hit_at_rank_three() -> None:
    assert reciprocal_rank(["x", "y", "a"], {"a", "z"}) == pytest.approx(1 / 3)


def test_reciprocal_rank_no_relevant_in_list() -> None:
    assert reciprocal_rank(["x", "y"], {"a"}) == 0.0


def test_mean_reciprocal_rank() -> None:
    rrs = [["a", "x"], ["x", "y", "b"]]
    relevants = [{"a"}, {"b"}]
    # 1.0 + 1/3 = 1.333... over 2 = 0.6666...
    assert mean_reciprocal_rank(rrs, relevants) == pytest.approx((1.0 + 1 / 3) / 2)


def test_mean_reciprocal_rank_mismatched_lengths_raise() -> None:
    with pytest.raises(ValueError):
        mean_reciprocal_rank([["a"]], [{"a"}, {"b"}])


# ─── DCG / nDCG ─────────────────────────────────────────────────────────────


def test_dcg_at_k_canonical_three_hits() -> None:
    # Three relevant docs at ranks 1, 2, 3.
    retrieved = ["a", "b", "c"]
    relevant = {"a", "b", "c"}
    expected = 1 / math.log2(2) + 1 / math.log2(3) + 1 / math.log2(4)
    assert dcg_at_k(retrieved, relevant, k=3) == pytest.approx(expected)


def test_dcg_at_k_only_top_k_counts() -> None:
    retrieved = ["x", "x", "x", "a"]
    relevant = {"a"}
    assert dcg_at_k(retrieved, relevant, k=3) == 0.0


def test_ndcg_at_k_perfect_ranking() -> None:
    assert ndcg_at_k(["a", "b", "c"], {"a", "b", "c"}, k=3) == 1.0


def test_ndcg_at_k_reverse_ranking_below_one() -> None:
    # Relevant doc at the last rank instead of first.
    retrieved = ["x", "x", "x", "a"]
    relevant = {"a", "b", "c"}
    # k=4: ideal places 3 hits at ranks 1, 2, 3; actual gets one hit
    # at rank 4. Score must be strictly between 0 and 1.
    score = ndcg_at_k(retrieved, relevant, k=4)
    assert 0.0 < score < 1.0


def test_ndcg_at_k_empty_relevant_returns_zero() -> None:
    assert ndcg_at_k(["a"], set(), k=1) == 0.0


def test_ndcg_at_k_graded_judgments() -> None:
    # Graded mode: doc "a" worth 3, "b" worth 2, "c" worth 1.
    retrieved = ["a", "c", "b"]
    relevance = {"a": 3.0, "b": 2.0, "c": 1.0}
    actual = (3 / math.log2(2)) + (1 / math.log2(3)) + (2 / math.log2(4))
    ideal = (3 / math.log2(2)) + (2 / math.log2(3)) + (1 / math.log2(4))
    assert ndcg_at_k(retrieved, relevance, k=3, binary=False) == pytest.approx(actual / ideal)
