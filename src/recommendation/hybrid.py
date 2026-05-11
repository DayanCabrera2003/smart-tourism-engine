"""T095 - Hybrid recommender that fuses content-based and collaborative scores.

The hybrid recommender resolves the cold-start trade-off between the
two strategies:

- The **content-based** branch (T093) follows the user's own embedding
  closely. It is precise when the user has declared strong interests,
  but it can amplify whatever single tag dominates the profile.
- The **pseudo-collaborative** branch (T094) snaps the user to a
  synthetic persona and rides on its broader taste. It surfaces
  destinations the user might not have asked for but would enjoy.

Combining both branches with a weighted average gives a ranking that is
personal yet diverse. The weight ``alpha`` controls the emphasis: 1.0
falls back to content-based, 0.0 to collaborative.
"""
from __future__ import annotations

from typing import Optional

from src.recommendation.collaborative import CollaborativeRecommender
from src.recommendation.content_based import ContentBasedRecommender, RecommendationHit
from src.recommendation.user_profile import UserProfile

__all__ = ["HybridRecommender"]


class HybridRecommender:
    """Weighted fusion of content-based and pseudo-collaborative scores.

    Parameters:
        content_based: instance of :class:`ContentBasedRecommender`.
        collaborative: instance of :class:`CollaborativeRecommender`.
        alpha: weight of the content-based branch in ``[0, 1]``. Defaults
            to 0.6 because the content-based branch reacts immediately to
            an explicit user profile, while the collaborative branch
            contributes diversity through the matched persona.
    """

    def __init__(
        self,
        content_based: ContentBasedRecommender,
        collaborative: CollaborativeRecommender,
        *,
        alpha: float = 0.6,
    ) -> None:
        if not 0.0 <= alpha <= 1.0:
            raise ValueError(f"alpha must be in [0, 1]; got {alpha}")
        self._content_based = content_based
        self._collaborative = collaborative
        self._alpha = alpha

    @property
    def alpha(self) -> float:
        return self._alpha

    def recommend(
        self,
        profile: UserProfile,
        *,
        top_k: int = 10,
    ) -> list[RecommendationHit]:
        """Return the fused ranking.

        Strategy:
        1. Ask each branch for ``2*top_k`` candidates so the union has
           enough material to rank after fusion.
        2. Build a map ``destination_id → fused_score`` where
           ``fused = alpha * content_score + (1 - alpha) * collab_score``.
           Branches that do not return a destination contribute 0 for
           that document.
        3. Sort by fused score (descending) and keep the top ``top_k``.
        4. The payload returned is the one observed in either branch
           (content-based wins to keep parity with the standalone modes).
        """
        candidates_pool = max(top_k * 2, top_k)
        content_hits = self._content_based.recommend(profile, top_k=candidates_pool)
        collab_hits = self._collaborative.recommend(profile, top_k=candidates_pool)

        if not content_hits and not collab_hits:
            return []

        fused: dict[str, _Entry] = {}
        for doc_id, score, payload in content_hits:
            fused[doc_id] = _Entry(content=score, payload=payload)
        for doc_id, score, payload in collab_hits:
            entry = fused.get(doc_id)
            if entry is None:
                fused[doc_id] = _Entry(collaborative=score, payload=payload)
            else:
                entry.collaborative = score
                # Prefer the content-based payload when both branches
                # returned the destination; payload from collab arrives
                # second so it is the natural fallback when content
                # left payload empty.
                if not entry.payload:
                    entry.payload = payload

        ranked: list[RecommendationHit] = []
        for doc_id, entry in fused.items():
            score = self._alpha * entry.content + (1.0 - self._alpha) * entry.collaborative
            ranked.append((doc_id, score, dict(entry.payload)))

        ranked.sort(key=lambda hit: hit[1], reverse=True)
        return ranked[:top_k]


class _Entry:
    """Mutable accumulator for the per-destination fused score."""

    __slots__ = ("content", "collaborative", "payload")

    def __init__(
        self,
        *,
        content: float = 0.0,
        collaborative: float = 0.0,
        payload: Optional[dict[str, object]] = None,
    ) -> None:
        self.content = content
        self.collaborative = collaborative
        self.payload: dict[str, object] = dict(payload or {})
