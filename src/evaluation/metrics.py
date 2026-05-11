"""T106 - Precision@k, Recall@k and F1@k for ranked retrieval.

All metrics operate on the same input shape so they can be composed
freely from a CLI:

- ``retrieved``: ordered list of destination ids returned by the
  recuperador for a query.
- ``relevant``: set of destination ids judged relevant for that query
  (the ground truth from :file:`data/eval/queries.json`).
- ``k``: cut-off rank.

The functions are pure and dependency-free (only the standard library)
so they can be reused outside the evaluation script — for example, by
unit tests, ad-hoc notebooks or a future API endpoint that surfaces
metrics on demand.

The implementations follow the standard definitions used by Manning et
al., *Introduction to Information Retrieval* (2008), chapter 8.
"""
from __future__ import annotations

from typing import Iterable

__all__ = [
    "precision_at_k",
    "recall_at_k",
    "f1_at_k",
]


def _validate_k(k: int) -> int:
    if not isinstance(k, int):
        raise TypeError(f"k must be an int; got {type(k).__name__}")
    if k <= 0:
        raise ValueError(f"k must be > 0; got {k}")
    return k


def _as_set(relevant: Iterable[str]) -> set[str]:
    return relevant if isinstance(relevant, set) else set(relevant)


def precision_at_k(retrieved: list[str], relevant: Iterable[str], k: int) -> float:
    """Precision@k = (#relevant retrieved in top-k) / k.

    ``k`` is fixed even when ``retrieved`` is shorter — that mirrors a
    real evaluation where the system promised ``k`` results but only
    delivered some.
    """
    _validate_k(k)
    relevant_set = _as_set(relevant)
    if not relevant_set:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for doc_id in top_k if doc_id in relevant_set)
    return hits / k


def recall_at_k(retrieved: list[str], relevant: Iterable[str], k: int) -> float:
    """Recall@k = (#relevant retrieved in top-k) / |relevant|.

    Returns 0.0 when there are no relevant documents (no recall can be
    measured against an empty ground truth).
    """
    _validate_k(k)
    relevant_set = _as_set(relevant)
    if not relevant_set:
        return 0.0
    top_k = retrieved[:k]
    hits = sum(1 for doc_id in top_k if doc_id in relevant_set)
    return hits / len(relevant_set)


def f1_at_k(retrieved: list[str], relevant: Iterable[str], k: int) -> float:
    """F1@k = harmonic mean of Precision@k and Recall@k.

    Returns 0.0 when both precision and recall are 0 (avoids division
    by zero in the harmonic mean).
    """
    p = precision_at_k(retrieved, relevant, k)
    r = recall_at_k(retrieved, relevant, k)
    if p + r == 0:
        return 0.0
    return 2 * p * r / (p + r)
