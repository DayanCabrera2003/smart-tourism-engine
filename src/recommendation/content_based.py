"""T093 - Content-based recommender.

Given a ``UserProfile`` the recommender:

1. Materializes the profile embedding via ``build_profile_embedding``.
2. Queries the destinations vector store (Qdrant collection
   ``destinations_text`` built in T051/T052) using the profile embedding
   as the query vector.
3. Filters out destinations the user already engaged with so we do not
   re-recommend something the user just visited, and returns the
   ``top_k`` most similar destinations.

The recommender relies on the same `VectorStore` wrapper used by the
semantic and hybrid retrievers, so the cosine similarity returned by
Qdrant maps directly to the relevance score the API surfaces.
"""
from __future__ import annotations

from typing import Iterable, Mapping, Optional, Protocol

from src.recommendation.user_profile import UserProfile, build_profile_embedding

__all__ = ["ContentBasedRecommender", "RecommendationHit"]


RecommendationHit = tuple[str, float, dict[str, object]]


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


class ContentBasedRecommender:
    """Recommender that scores destinations by similarity to the user profile.

    Parameters:
        embedder: Text embedder used to materialize the profile embedding.
            Must produce vectors in the same space as the destinations
            collection (defaults match ``TextEmbedder`` + ``destinations_text``).
        store: ``VectorStore`` (or compatible protocol) used to query the
            destinations collection.
        collection: Name of the destinations collection in Qdrant.
        history_embeddings: Optional map ``destination_id → vector`` used by
            ``build_profile_embedding`` to fold the user's history into the
            profile embedding. Resolving this from Qdrant is the caller's
            responsibility (one round-trip per recommendation request is
            cheap; pulling all destinations is not).
    """

    def __init__(
        self,
        embedder: _Embedder,
        store: _Store,
        *,
        collection: str = "destinations_text",
        history_embeddings: Optional[Mapping[str, list[float]]] = None,
    ) -> None:
        self._embedder = embedder
        self._store = store
        self._collection = collection
        self._history_embeddings = dict(history_embeddings or {})

    def recommend(
        self,
        profile: UserProfile,
        *,
        top_k: int = 10,
        exclude: Optional[Iterable[str]] = None,
    ) -> list[RecommendationHit]:
        """Return up to ``top_k`` destinations ranked by cosine similarity.

        ``exclude`` is unioned with the profile history so callers can
        veto extra destinations (for example, items already shown on the
        page). When the profile produces no embedding the method returns
        an empty list - the caller is responsible for falling back to a
        generic ranking instead of inventing arbitrary content.
        """
        query_vector = build_profile_embedding(
            profile,
            self._embedder,
            history_embeddings=self._history_embeddings,
        )
        if query_vector is None:
            return []

        excluded_ids: set[str] = set(profile.history)
        if exclude:
            excluded_ids.update(exclude)

        # Over-fetch so that filtering out excluded ids still leaves
        # top_k candidates. The factor of 2 is a pragmatic trade-off
        # between latency and the risk of returning fewer than top_k
        # when the user has a long history.
        fetch_k = max(top_k * 2, top_k + len(excluded_ids))
        raw_hits = self._store.search(
            self._collection,
            query_vector,
            top_k=fetch_k,
        )

        hits: list[RecommendationHit] = []
        for point_id, score, payload in raw_hits:
            destination_id = str(payload.get("slug") or point_id)
            if destination_id in excluded_ids:
                continue
            hits.append((destination_id, float(score), dict(payload)))
            if len(hits) >= top_k:
                break
        return hits
