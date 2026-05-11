"""T120 - Rocchio relevance-feedback applied to the dense query vector.

Rocchio's formula (Rocchio, 1971; Manning et al. 2008 ch. 9) shifts the
query vector toward the centroid of the documents the user marked as
relevant and away from the centroid of those marked as irrelevant::

    q_modified = alpha * q_original
               + beta  * (1/|D_rel|)    * sum(d for d in D_rel)
               - gamma * (1/|D_nonrel|) * sum(d for d in D_nonrel)

We apply it on top of the dense query embedding the semantic
retriever already builds. Relevance is sourced from
:func:`src.ingestion.feedback.aggregate_feedback` (T118) so the user's
thumbs up / thumbs down history shapes the next request automatically.

Sensible defaults follow the literature: ``alpha=1.0``, ``beta=0.75``,
``gamma=0.15``. Negative feedback is weighted half of positive feedback
to avoid over-correcting on a single thumbs-down.
"""
from __future__ import annotations

import math
from typing import Mapping, Optional

__all__ = [
    "DEFAULT_ALPHA",
    "DEFAULT_BETA",
    "DEFAULT_GAMMA",
    "RocchioWeights",
    "rocchio_update",
]


DEFAULT_ALPHA = 1.0
DEFAULT_BETA = 0.75
DEFAULT_GAMMA = 0.15


class RocchioWeights:
    """Holder for the three Rocchio coefficients.

    Keeping them in one struct makes call sites short and avoids the
    "swap beta with gamma" footgun.
    """

    __slots__ = ("alpha", "beta", "gamma")

    def __init__(
        self,
        alpha: float = DEFAULT_ALPHA,
        beta: float = DEFAULT_BETA,
        gamma: float = DEFAULT_GAMMA,
    ) -> None:
        if alpha < 0:
            raise ValueError(f"alpha must be >= 0; got {alpha}")
        if beta < 0:
            raise ValueError(f"beta must be >= 0; got {beta}")
        if gamma < 0:
            raise ValueError(f"gamma must be >= 0; got {gamma}")
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma


def _centroid(vectors: list[list[float]]) -> Optional[list[float]]:
    if not vectors:
        return None
    dim = len(vectors[0])
    accum = [0.0] * dim
    for vec in vectors:
        if len(vec) != dim:
            raise ValueError(
                f"Dimension mismatch in centroid: expected {dim}, got {len(vec)}"
            )
        for i, value in enumerate(vec):
            accum[i] += value
    n = len(vectors)
    return [v / n for v in accum]


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0.0:
        return list(vector)
    return [v / norm for v in vector]


def rocchio_update(
    query_vector: list[float],
    feedback: Mapping[str, int],
    document_embeddings: Mapping[str, list[float]],
    *,
    weights: Optional[RocchioWeights] = None,
    normalize: bool = True,
) -> list[float]:
    """Shift ``query_vector`` toward relevant docs and away from irrelevant.

    Parameters:
        query_vector: original dense embedding of the user's query.
        feedback: map ``destination_id -> vote`` (+1 or -1). The
            aggregator in :mod:`src.ingestion.feedback` already
            collapses multiple votes per triple into the latest one.
        document_embeddings: map ``destination_id -> vector``. Missing
            ids are skipped silently — they cannot contribute to the
            centroid, but they should not crash the request either.
        weights: Rocchio coefficients. Defaults to (1.0, 0.75, 0.15).
        normalize: whether to L2-normalize the result. Defaults to
            True because the semantic retriever uses cosine similarity
            against L2-normalized embeddings.

    Returns the modified query vector. When ``feedback`` is empty (no
    votes for the query yet) the function returns a copy of the input
    unchanged — Rocchio has no signal to act on.
    """
    w = weights or RocchioWeights()
    if not feedback or not document_embeddings:
        return _normalize(query_vector) if normalize else list(query_vector)

    positive_vectors: list[list[float]] = []
    negative_vectors: list[list[float]] = []
    for dest_id, vote in feedback.items():
        vec = document_embeddings.get(dest_id)
        if vec is None:
            continue
        if vote > 0:
            positive_vectors.append(vec)
        elif vote < 0:
            negative_vectors.append(vec)

    dim = len(query_vector)
    accum = [w.alpha * v for v in query_vector]
    if positive_vectors:
        centroid = _centroid(positive_vectors)
        if centroid is not None:
            if len(centroid) != dim:
                raise ValueError(
                    f"Positive centroid dim {len(centroid)} != query dim {dim}"
                )
            for i in range(dim):
                accum[i] += w.beta * centroid[i]
    if negative_vectors:
        centroid = _centroid(negative_vectors)
        if centroid is not None:
            if len(centroid) != dim:
                raise ValueError(
                    f"Negative centroid dim {len(centroid)} != query dim {dim}"
                )
            for i in range(dim):
                accum[i] -= w.gamma * centroid[i]

    return _normalize(accum) if normalize else accum
