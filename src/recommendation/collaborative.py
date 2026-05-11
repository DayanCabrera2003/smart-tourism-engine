"""T094 - Pseudo-collaborative recommender for cold-start scenarios.

Real collaborative filtering needs many users interacting with many
items. We do not have that yet, so this module fakes the signal:

1. Snap the user to the closest synthetic persona (T092). Closeness is
   defined as cosine similarity between the user profile embedding and
   each persona embedding, both projected in the destinations text
   space.
2. Recommend "what users in that persona would like" by reusing the
   content-based recommender (T093) on the persona's profile.

Because the personas are fixed and few, we can precompute their
embeddings once per process and cache them on the instance. This keeps
the recommendation latency dominated by a single Qdrant search even when
the per-request profile has a deep history.
"""
from __future__ import annotations

import math
from typing import Mapping, Optional, Protocol

from src.recommendation.content_based import ContentBasedRecommender, RecommendationHit
from src.recommendation.synthetic_profiles import (
    SYNTHETIC_PROFILES,
    list_synthetic_profile_ids,
)
from src.recommendation.user_profile import UserProfile, build_profile_embedding

__all__ = ["CollaborativeRecommender"]


class _Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


class _Store(Protocol):
    def search(
        self,
        collection: str,
        query_vector: list[float],
        *,
        top_k: int = 10,
        score_threshold: Optional[float] = None,
    ) -> list[tuple[object, float, dict[str, object]]]: ...


def _cosine(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two non-empty vectors."""
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


class CollaborativeRecommender:
    """Recommend by snapping the user to the closest synthetic persona.

    The recommender is "pseudo"-collaborative because the personas are
    handcrafted instead of inferred from real interactions; the algorithm
    still mimics the collaborative shape: find users similar to me, then
    recommend what they like.

    Parameters:
        embedder: text embedder used to materialize the user and the
            persona embeddings. Must produce vectors in the same space as
            the destinations collection.
        store: vector store (or compatible protocol) used to query the
            destinations collection.
        collection: name of the destinations collection in Qdrant.
        content_based: optional pre-built ``ContentBasedRecommender`` to
            reuse when generating recommendations for the matched
            persona. Injecting it avoids constructing two recommenders
            with subtly different settings.
        history_embeddings: optional map ``destination_id → vector`` used
            when materializing the user embedding to include their
            history.
    """

    def __init__(
        self,
        embedder: _Embedder,
        store: _Store,
        *,
        collection: str = "destinations_text",
        content_based: Optional[ContentBasedRecommender] = None,
        history_embeddings: Optional[Mapping[str, list[float]]] = None,
    ) -> None:
        self._embedder = embedder
        self._store = store
        self._collection = collection
        self._history_embeddings = dict(history_embeddings or {})
        self._content_based = content_based or ContentBasedRecommender(
            embedder,
            store,
            collection=collection,
            history_embeddings=history_embeddings,
        )
        self._persona_embeddings: dict[str, list[float]] = {}

    def _embed_personas(self) -> dict[str, list[float]]:
        """Cache the embedding of each synthetic persona."""
        if self._persona_embeddings:
            return self._persona_embeddings
        cache: dict[str, list[float]] = {}
        for persona_id in list_synthetic_profile_ids():
            persona = SYNTHETIC_PROFILES[persona_id]
            embedding = build_profile_embedding(persona, self._embedder)
            if embedding is not None:
                cache[persona_id] = embedding
        self._persona_embeddings = cache
        return cache

    def closest_persona(self, profile: UserProfile) -> Optional[str]:
        """Return the persona id whose embedding is closest to the profile.

        Returns ``None`` when the user profile has no embeddable signal
        or when no persona could be embedded (defensive guard for empty
        catalogs).
        """
        user_vec = build_profile_embedding(
            profile,
            self._embedder,
            history_embeddings=self._history_embeddings,
        )
        if user_vec is None:
            return None

        personas = self._embed_personas()
        if not personas:
            return None

        best_id: Optional[str] = None
        best_score = -1.0
        for persona_id, vec in personas.items():
            score = _cosine(user_vec, vec)
            if score > best_score:
                best_score = score
                best_id = persona_id
        return best_id

    def recommend(
        self,
        profile: UserProfile,
        *,
        top_k: int = 10,
    ) -> list[RecommendationHit]:
        """Recommend destinations using the closest synthetic persona.

        If no persona matches (e.g. profile has no signal), returns an
        empty list. The history of the input profile is propagated to
        the persona so already-seen destinations are still excluded.
        """
        persona_id = self.closest_persona(profile)
        if persona_id is None:
            return []
        persona = SYNTHETIC_PROFILES[persona_id].model_copy(deep=True)
        # Inherit the user's history so already-seen destinations are
        # excluded as if the persona had visited them.
        persona.history = list({*persona.history, *profile.history})
        return self._content_based.recommend(persona, top_k=top_k)
