"""T101 - Combined re-ranker for top-k hits.

The retriever (Boolean Extended, semantic or hybrid) decides which
destinations are relevant to the query. The re-ranker then mixes that
relevance with three orthogonal signals:

- **Popularity** (T099): destinations more discussed in the corpus.
- **Freshness** (T100): how recently the data was fetched.
- **Personalization**: cosine similarity between the user profile
  embedding (T091) and the destination embedding, when both are
  available. Falls back to 0 for anonymous users or unknown
  destinations.

The final score is a convex combination with caller-tunable weights::

    final = w_rel * relevance
          + w_pop * popularity
          + w_fresh * freshness
          + w_pers * personalization

Weights are renormalized internally so they always sum to 1.0 and the
output stays in ``[0, 1]``. The re-ranker is a pure function over
already-fetched hits + side metadata; it does not query Qdrant or the
LLM, so it is cheap to call per request and easy to test.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Optional

__all__ = [
    "RerankWeights",
    "Reranker",
    "RerankHit",
    "cosine_similarity",
]

RerankHit = tuple[str, float]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Plain cosine similarity for two non-empty vectors.

    Returns 0.0 when either vector has zero norm so the re-ranker never
    propagates NaNs to the final score.
    """
    if len(a) != len(b):
        raise ValueError(f"Dimension mismatch: {len(a)} vs {len(b)}")
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


@dataclass(frozen=True)
class RerankWeights:
    """Weights for the four signals combined by :class:`Reranker`.

    The defaults emphasise relevance (the user's stated need) while
    keeping popularity and freshness as visible nudges. Personalization
    is small by default because it can be aggressive when a user has
    a strong profile.
    """

    relevance: float = 0.55
    popularity: float = 0.20
    freshness: float = 0.10
    personalization: float = 0.15

    def __post_init__(self) -> None:
        for name in ("relevance", "popularity", "freshness", "personalization"):
            value = getattr(self, name)
            if value < 0:
                raise ValueError(f"weight {name} must be >= 0; got {value}")
        if self.total() == 0:
            raise ValueError("at least one weight must be > 0")

    def total(self) -> float:
        return (
            self.relevance + self.popularity + self.freshness + self.personalization
        )

    def normalized(self) -> "RerankWeights":
        total = self.total()
        return RerankWeights(
            relevance=self.relevance / total,
            popularity=self.popularity / total,
            freshness=self.freshness / total,
            personalization=self.personalization / total,
        )


class Reranker:
    """Re-rank ``top_k`` hits using popularity, freshness and personalization.

    Parameters:
        weights: configurable :class:`RerankWeights`. Pass a custom
            instance to tune the strategy for a given UI section
            (popularity-heavy for "Populares", personalization-heavy
            for "Recomendado para ti").
        popularity: optional ``destination_id -> [0, 1]`` map. Missing
            ids contribute zero.
        freshness: optional ``destination_id -> [0, 1]`` map. Missing
            ids contribute zero.
        destination_embeddings: optional ``destination_id -> vector``
            map used for the personalization component.
        user_embedding: optional vector representing the active user
            profile (T091). When ``None`` the personalization
            contribution is dropped from the convex combination and
            the remaining weights are renormalized so the final score
            still lives in ``[0, 1]``.
    """

    def __init__(
        self,
        *,
        weights: Optional[RerankWeights] = None,
        popularity: Optional[Mapping[str, float]] = None,
        freshness: Optional[Mapping[str, float]] = None,
        destination_embeddings: Optional[Mapping[str, list[float]]] = None,
        user_embedding: Optional[list[float]] = None,
    ) -> None:
        self._weights = (weights or RerankWeights()).normalized()
        self._popularity = dict(popularity or {})
        self._freshness = dict(freshness or {})
        self._destination_embeddings = dict(destination_embeddings or {})
        self._user_embedding = list(user_embedding) if user_embedding else None

    @property
    def weights(self) -> RerankWeights:
        return self._weights

    def _personalization(self, destination_id: str) -> float:
        if self._user_embedding is None:
            return 0.0
        vector = self._destination_embeddings.get(destination_id)
        if not vector:
            return 0.0
        sim = cosine_similarity(self._user_embedding, vector)
        # Cosine can be negative; clamp to [0, 1] so it never subtracts
        # from the final score (we never want to push a result down for
        # being "anti-similar"; we just stop boosting it).
        return max(0.0, min(1.0, sim))

    def rerank(self, hits: list[RerankHit]) -> list[RerankHit]:
        """Return ``hits`` re-ordered by the convex combination.

        Input hits are tuples ``(destination_id, relevance_score)``
        with relevance already in ``[0, 1]``. Output preserves the same
        shape with the recomputed score and is sorted by score
        descending. The input list is not mutated.
        """
        if not hits:
            return []

        weights = self._weights
        # If the user has no embedding, redistribute the personalization
        # weight proportionally so the convex combination still sums
        # to 1.0 and the score stays in [0, 1].
        if self._user_embedding is None:
            redistributed = RerankWeights(
                relevance=weights.relevance,
                popularity=weights.popularity,
                freshness=weights.freshness,
                personalization=0.0,
            ).normalized()
        else:
            redistributed = weights

        ranked: list[RerankHit] = []
        for destination_id, relevance in hits:
            pop = self._popularity.get(destination_id, 0.0)
            fresh = self._freshness.get(destination_id, 0.0)
            pers = self._personalization(destination_id)
            final = (
                redistributed.relevance * float(relevance)
                + redistributed.popularity * float(pop)
                + redistributed.freshness * float(fresh)
                + redistributed.personalization * pers
            )
            ranked.append((destination_id, final))

        ranked.sort(key=lambda hit: hit[1], reverse=True)
        return ranked
