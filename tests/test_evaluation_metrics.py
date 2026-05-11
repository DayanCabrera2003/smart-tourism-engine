"""Tests for T106 — Precision@k, Recall@k and F1@k."""
from __future__ import annotations

import pytest

from src.evaluation.metrics import (
    f1_at_k,
    precision_at_k,
    recall_at_k,
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
