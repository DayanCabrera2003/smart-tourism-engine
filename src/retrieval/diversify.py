"""T102 - Maximal Marginal Relevance (MMR) diversification.

Pure ranking by relevance often returns ten almost identical results:
ten beach destinations on the same coast, ten European capitals, etc.
MMR (Carbonell & Goldstein, 1998) trades off relevance against
similarity to already-selected items so the top-k stays varied.

Greedy formulation::

    MMR(d) = lambda * sim_rel(d) - (1 - lambda) * max_{d' in S} sim_doc(d, d')

where ``S`` is the set of already-selected destinations. ``lambda=1``
keeps the original ranking; ``lambda=0`` maximizes diversity at the
expense of relevance. We default to 0.7 because in tourism the user
already filtered by query, so relevance should dominate but a handful
of diverse picks is welcome.

The implementation expects embeddings in the destinations vector space
(384-dim from ``TextEmbedder`` in our codebase). Destinations without
an embedding are kept in their original order at the bottom of the
result so MMR never silently drops content from a partial corpus.
"""
from __future__ import annotations

from typing import Mapping, Optional

from src.retrieval.reranker import RerankHit, cosine_similarity

__all__ = ["DEFAULT_LAMBDA", "apply_mmr"]

DEFAULT_LAMBDA = 0.7


def apply_mmr(
    hits: list[RerankHit],
    embeddings: Mapping[str, list[float]],
    *,
    top_k: Optional[int] = None,
    lambda_: float = DEFAULT_LAMBDA,
) -> list[RerankHit]:
    """Greedy MMR over already-ranked hits.

    Parameters:
        hits: list of ``(destination_id, relevance)`` ordered by the
            base retriever. Relevance must already be in ``[0, 1]``
            for the trade-off to behave linearly.
        embeddings: map ``destination_id -> vector``. Destinations
            without an entry are treated as opaque: they keep their
            relative order at the end of the output.
        top_k: cap the output length. ``None`` means "as many as
            available".
        lambda_: weight of relevance against diversity in ``[0, 1]``.
            0.0 = maximum diversity; 1.0 = original ranking.

    Returns the selected hits with their original relevance scores
    preserved (we do not rewrite them; the caller can chain a re-ranker
    on top if it wants different numbers).
    """
    if not 0.0 <= lambda_ <= 1.0:
        raise ValueError(f"lambda_ must be in [0, 1]; got {lambda_}")
    if not hits:
        return []

    embedded: list[RerankHit] = [h for h in hits if h[0] in embeddings]
    opaque: list[RerankHit] = [h for h in hits if h[0] not in embeddings]

    selected: list[RerankHit] = []
    pool = list(embedded)

    while pool and (top_k is None or len(selected) < top_k):
        best_index = 0
        best_score = -float("inf")
        for i, (doc_id, relevance) in enumerate(pool):
            if not selected:
                # First pick: pure relevance.
                score = float(relevance)
            else:
                doc_vec = embeddings[doc_id]
                max_sim = max(
                    cosine_similarity(doc_vec, embeddings[chosen_id])
                    for chosen_id, _ in selected
                )
                score = lambda_ * float(relevance) - (1 - lambda_) * max_sim
            if score > best_score:
                best_score = score
                best_index = i
        selected.append(pool.pop(best_index))

    if top_k is None or len(selected) < top_k:
        remaining = (top_k - len(selected)) if top_k is not None else None
        if remaining is None:
            selected.extend(opaque)
        else:
            selected.extend(opaque[:remaining])

    return selected
