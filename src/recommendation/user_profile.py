"""T091 - User profile model for the recommender system.

A ``UserProfile`` aggregates the signal that the recommender needs to produce
personalized rankings: declared interests (tags), interaction history
(destination ids the user has engaged with) and an aggregated embedding that
represents the user's taste in the same vector space as the destinations.

The embedding is rebuilt lazily from interests/history via
``build_profile_embedding`` so the profile stays in sync with the user's
declarations and actions without requiring a database round-trip on every
recommendation request.
"""
from __future__ import annotations

import math
from typing import Iterable, Mapping, Optional, Protocol

from pydantic import BaseModel, Field

__all__ = [
    "UserProfile",
    "build_profile_embedding",
    "_average_vectors",
    "_normalize",
]


class _Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


class UserProfile(BaseModel):
    """Profile that drives content-based and collaborative recommendations.

    Attributes:
        id: Stable identifier used to persist the profile across sessions.
        name: Optional human-readable label (e.g. "mochilero").
        interests: Free-form tags that describe what the user likes
            ("playa", "montaña", "cultura"). Used both for content-based
            similarity and to match against synthetic profiles.
        history: Destination ids the user has explicitly engaged with. Used to
            broaden the aggregated embedding with concrete examples instead of
            just declared interests.
        embedding: Aggregated vector in the destinations embedding space. Kept
            optional so a profile can exist before any destination has been
            embedded; the recommender rebuilds it on demand via
            ``build_profile_embedding``.
    """

    id: str = Field(..., description="Stable identifier for the profile.")
    name: Optional[str] = Field(
        None, description="Optional human-readable label of the profile."
    )
    interests: list[str] = Field(
        default_factory=list,
        description="Tags that describe what the user likes.",
    )
    history: list[str] = Field(
        default_factory=list,
        description="Destination ids the user has engaged with.",
    )
    embedding: Optional[list[float]] = Field(
        None,
        description="Aggregated embedding of interests+history in the destinations space.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "user-001",
                "name": "mochilero",
                "interests": ["aventura", "naturaleza", "bajo presupuesto"],
                "history": ["cusco-pe", "kathmandu-np"],
                "embedding": None,
            }
        }
    }


def _average_vectors(vectors: Iterable[list[float]]) -> Optional[list[float]]:
    """Average a list of equally-sized vectors, returning None if empty."""
    accum: list[float] | None = None
    count = 0
    for vec in vectors:
        if not vec:
            continue
        if accum is None:
            accum = [0.0] * len(vec)
        if len(vec) != len(accum):
            raise ValueError(
                f"Vector dimension mismatch: expected {len(accum)}, got {len(vec)}"
            )
        for i, value in enumerate(vec):
            accum[i] += float(value)
        count += 1
    if accum is None or count == 0:
        return None
    return [v / count for v in accum]


def _normalize(vector: list[float]) -> list[float]:
    """Return the L2-normalized copy of ``vector``.

    Profile and destination embeddings are compared with cosine similarity so
    normalization keeps the dot product equivalent to cosine, and matches the
    behaviour of ``TextEmbedder`` which already L2-normalizes its outputs.
    """
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0.0:
        return list(vector)
    return [v / norm for v in vector]


def build_profile_embedding(
    profile: UserProfile,
    embedder: _Embedder,
    *,
    history_embeddings: Optional[Mapping[str, list[float]]] = None,
) -> Optional[list[float]]:
    """Compute the aggregated embedding for a profile (T091).

    Strategy:
    1. Embed each interest tag with the text embedder and average them. This
       gives a stable taste vector even for users with no interaction history.
    2. If ``history_embeddings`` is provided, average those destination
       vectors too and combine them with the interests vector. We weight
       history equally to interests so that strong declared preferences are
       not drowned by a noisy clickstream.

    Returns ``None`` when there is no signal at all (no interests and no
    matching history embeddings); the caller can then fall back to a generic
    ranking instead of recommending arbitrary content.
    """
    interest_vec: Optional[list[float]] = None
    if profile.interests:
        interest_vecs = [embedder.embed(tag) for tag in profile.interests if tag.strip()]
        interest_vec = _average_vectors(interest_vecs)

    history_vec: Optional[list[float]] = None
    if profile.history and history_embeddings:
        present = [
            history_embeddings[dest_id]
            for dest_id in profile.history
            if dest_id in history_embeddings
        ]
        history_vec = _average_vectors(present)

    components = [v for v in (interest_vec, history_vec) if v is not None]
    if not components:
        return None

    combined = _average_vectors(components)
    if combined is None:
        return None
    return _normalize(combined)
