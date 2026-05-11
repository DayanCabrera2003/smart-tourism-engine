"""T096 - Application-level service that resolves the request profile and dispatches.

Lives between the API layer (FastAPI handler in ``src/api/main.py``) and the
recommender implementations. The goal is to keep ``main.py`` thin and the
recommenders pure: the service knows how to translate a request payload into
a :class:`UserProfile`, picks the strategy and assembles the response with
destination metadata.
"""
from __future__ import annotations

from typing import Iterable, Optional, Protocol

from src.recommendation.collaborative import CollaborativeRecommender
from src.recommendation.content_based import ContentBasedRecommender, RecommendationHit
from src.recommendation.hybrid import HybridRecommender
from src.recommendation.synthetic_profiles import (
    SYNTHETIC_PROFILES,
    get_synthetic_profile,
)
from src.recommendation.user_profile import UserProfile

__all__ = [
    "RecommendationService",
    "RecommendationOutcome",
    "build_request_profile",
]


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


SYNTHETIC_PREFIX = "synthetic:"


def build_request_profile(
    user_id: Optional[str],
    interests: Iterable[str],
    history: Iterable[str],
) -> Optional[UserProfile]:
    """Resolve a :class:`UserProfile` from a recommendation request.

    Resolution order:

    1. If ``user_id`` matches a known synthetic profile (with or without
       the ``synthetic:`` prefix) we start from a deep copy of that
       profile so its interests/history are preserved as a base.
    2. Otherwise we start from an empty profile with the given user id
       (or ``"anonymous"`` as a fallback).
    3. ``interests`` and ``history`` are appended without removing what
       the synthetic profile already declared so users with both a
       persona and extra signal get the union.

    Returns ``None`` only when nothing was provided at all.
    """
    cleaned_interests = [tag.strip() for tag in interests if tag and tag.strip()]
    cleaned_history = [dest_id.strip() for dest_id in history if dest_id and dest_id.strip()]

    persona_id = _resolve_persona_id(user_id)
    if persona_id is not None:
        profile = get_synthetic_profile(persona_id)
        profile.interests = _dedup(profile.interests + cleaned_interests)
        profile.history = _dedup(profile.history + cleaned_history)
        return profile

    if not cleaned_interests and not cleaned_history and not user_id:
        return None

    return UserProfile(
        id=user_id or "anonymous",
        interests=_dedup(cleaned_interests),
        history=_dedup(cleaned_history),
    )


def _resolve_persona_id(user_id: Optional[str]) -> Optional[str]:
    if not user_id:
        return None
    bare = user_id[len(SYNTHETIC_PREFIX):] if user_id.startswith(SYNTHETIC_PREFIX) else user_id
    if bare in SYNTHETIC_PROFILES:
        return bare
    return None


def _dedup(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in items:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


class RecommendationOutcome:
    """Container with the hits and the persona that drove the ranking."""

    __slots__ = ("hits", "persona", "empty")

    def __init__(
        self,
        hits: list[RecommendationHit],
        *,
        persona: Optional[str] = None,
        empty: bool = False,
    ) -> None:
        self.hits = hits
        self.persona = persona
        self.empty = empty


class RecommendationService:
    """Coordinates the three strategies and adds the matched persona info.

    The service owns the recommenders so the FastAPI handler builds it
    once via dependency injection and reuses it across requests. The
    underlying recommenders share the same store/embedder, but each is
    parameterised so callers can mutate ``alpha`` per request without
    rebuilding the object.
    """

    def __init__(
        self,
        embedder: _Embedder,
        store: _Store,
        *,
        collection: str = "destinations_text",
    ) -> None:
        self._content_based = ContentBasedRecommender(
            embedder, store, collection=collection
        )
        self._collaborative = CollaborativeRecommender(
            embedder,
            store,
            collection=collection,
            content_based=self._content_based,
        )

    def recommend(
        self,
        profile: Optional[UserProfile],
        *,
        top_k: int,
        mode: str,
        alpha: float,
    ) -> RecommendationOutcome:
        if profile is None:
            return RecommendationOutcome([], empty=True)

        persona = self._collaborative.closest_persona(profile)
        persona_label = f"{SYNTHETIC_PREFIX}{persona}" if persona else None

        if mode == "content":
            hits = self._content_based.recommend(profile, top_k=top_k)
        elif mode == "collaborative":
            hits = self._collaborative.recommend(profile, top_k=top_k)
        else:
            hybrid = HybridRecommender(
                self._content_based, self._collaborative, alpha=alpha
            )
            hits = hybrid.recommend(profile, top_k=top_k)

        return RecommendationOutcome(
            hits, persona=persona_label, empty=not hits
        )
