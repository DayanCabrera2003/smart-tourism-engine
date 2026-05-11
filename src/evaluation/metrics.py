"""T106 and T107 - Evaluation metrics for ranked retrieval.

All metrics operate on the same input shape so they can be composed
freely from a CLI:

- ``retrieved``: ordered list of destination ids returned by the
  recuperador for a query.
- ``relevant``: set of destination ids judged relevant for that query
  (the ground truth from :file:`data/eval/queries.json`).
- ``k`` (where applicable): cut-off rank.

The functions are pure and dependency-free (only the standard library)
so they can be reused outside the evaluation script — for example, by
unit tests, ad-hoc notebooks or a future API endpoint that surfaces
metrics on demand.

The implementations follow the standard definitions used by Manning et
al., *Introduction to Information Retrieval* (2008), chapters 8 and
13, and Croft et al., *Search Engines: Information Retrieval in
Practice* (2009), chapter 8.
"""
from __future__ import annotations

import math
from typing import Iterable

__all__ = [
    "precision_at_k",
    "recall_at_k",
    "f1_at_k",
    "average_precision",
    "mean_average_precision",
    "reciprocal_rank",
    "mean_reciprocal_rank",
    "dcg_at_k",
    "ndcg_at_k",
]


# ─── T106: Precision / Recall / F1 ─────────────────────────────────────────


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


# ─── T107: Average Precision / MAP / MRR / nDCG ─────────────────────────────


def average_precision(retrieved: list[str], relevant: Iterable[str]) -> float:
    """Average Precision over all relevant documents.

    AP = (1 / |relevant|) * sum_{rank where retrieved[rank] is relevant}
                                  Precision@(rank + 1)

    Indexes are 1-based when reporting precision (Precision@1 if the
    first hit is relevant, etc.). Documents in the ground truth that
    are *never* retrieved still count against the average, which is
    why AP is a stricter signal than Precision@k for any fixed k.
    """
    relevant_set = _as_set(relevant)
    if not relevant_set:
        return 0.0
    total = 0.0
    hits = 0
    for rank, doc_id in enumerate(retrieved, start=1):
        if doc_id in relevant_set:
            hits += 1
            total += hits / rank
    return total / len(relevant_set)


def mean_average_precision(
    retrieved_per_query: list[list[str]],
    relevant_per_query: list[Iterable[str]],
) -> float:
    """MAP = mean of Average Precision across queries.

    The two input lists must have the same length and be aligned by
    index. Queries with empty ground truth contribute 0.0 so they are
    visible in the mean — a system that returns nothing useful for an
    impossible query is still penalised.
    """
    if len(retrieved_per_query) != len(relevant_per_query):
        raise ValueError(
            f"retrieved_per_query and relevant_per_query must have the same length; "
            f"got {len(retrieved_per_query)} and {len(relevant_per_query)}"
        )
    if not retrieved_per_query:
        return 0.0
    return sum(
        average_precision(retrieved, relevant)
        for retrieved, relevant in zip(retrieved_per_query, relevant_per_query, strict=True)
    ) / len(retrieved_per_query)


def reciprocal_rank(retrieved: list[str], relevant: Iterable[str]) -> float:
    """Reciprocal Rank = 1 / rank of the first relevant document.

    Returns 0.0 when no relevant document appears in ``retrieved``.
    """
    relevant_set = _as_set(relevant)
    if not relevant_set:
        return 0.0
    for rank, doc_id in enumerate(retrieved, start=1):
        if doc_id in relevant_set:
            return 1.0 / rank
    return 0.0


def mean_reciprocal_rank(
    retrieved_per_query: list[list[str]],
    relevant_per_query: list[Iterable[str]],
) -> float:
    """MRR = mean of reciprocal rank across queries."""
    if len(retrieved_per_query) != len(relevant_per_query):
        raise ValueError(
            "retrieved_per_query and relevant_per_query must have the same length"
        )
    if not retrieved_per_query:
        return 0.0
    return sum(
        reciprocal_rank(retrieved, relevant)
        for retrieved, relevant in zip(retrieved_per_query, relevant_per_query, strict=True)
    ) / len(retrieved_per_query)


def dcg_at_k(
    retrieved: list[str],
    relevant: Iterable[str],
    k: int,
    *,
    binary: bool = True,
) -> float:
    """Discounted Cumulative Gain at rank k.

    For binary judgments (default) the gain of position ``i`` is::

        gain(i) = 1 if retrieved[i-1] in relevant else 0
        DCG@k   = sum_{i=1..k} gain(i) / log2(i + 1)

    When ``binary=False`` we expect ``relevant`` to be a mapping
    ``doc_id -> graded_relevance`` and the gain is the graded value;
    we keep this branch available for future use but the current
    pipeline only emits binary judgments.
    """
    _validate_k(k)
    is_graded = not binary and isinstance(relevant, dict)
    relevant_set = set(relevant) if not is_graded else None
    score = 0.0
    for i, doc_id in enumerate(retrieved[:k], start=1):
        if is_graded:
            gain = float(relevant.get(doc_id, 0.0))
        else:
            gain = 1.0 if doc_id in relevant_set else 0.0
        if gain:
            score += gain / math.log2(i + 1)
    return score


def ndcg_at_k(
    retrieved: list[str],
    relevant: Iterable[str],
    k: int,
    *,
    binary: bool = True,
) -> float:
    """Normalized DCG at rank k = DCG@k / ideal DCG@k.

    Returns 0.0 when ``relevant`` is empty (the ideal DCG is 0 and we
    avoid the division). For binary judgments the ideal ranking places
    as many relevant documents as possible in the top positions, so
    iDCG@k uses ``min(k, |relevant|)`` gains of 1.0.
    """
    _validate_k(k)
    is_graded = not binary and isinstance(relevant, dict)
    if is_graded:
        gains = sorted(relevant.values(), reverse=True)[:k]
    else:
        relevant_count = len(_as_set(relevant))
        if relevant_count == 0:
            return 0.0
        gains = [1.0] * min(k, relevant_count)
    ideal = sum(gain / math.log2(i + 1) for i, gain in enumerate(gains, start=1))
    if ideal == 0:
        return 0.0
    return dcg_at_k(retrieved, relevant, k, binary=binary) / ideal
