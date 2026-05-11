"""T103 - Build UI sections from a single top-k retrieval.

The user sees more than just one ranked list. The plan asks for four
sections that reframe the same hits through different lenses:

- **Más relevantes**: the original ranking from the retriever.
- **Populares**: re-ranked emphasising :mod:`src.retrieval.popularity`.
- **Recientes**: re-ranked emphasising :mod:`src.retrieval.freshness`.
- **Variados**: greedy diversification by country so consecutive picks
  do not all share the same flag. This is the plan's "visualmente
  similares" reinterpreted for a corpus where image embeddings are not
  yet available; once the multimodal index is populated the same slot
  can be swapped for a CLIP-driven section.

The helpers in this module are **pure functions** over already-fetched
hits + side metadata. They are cheap to call per request, easy to
test, and intentionally decoupled from the API / UI transport so a
future CLI can reuse them.
"""
from __future__ import annotations

from typing import Mapping, Optional

from src.retrieval.reranker import Reranker, RerankHit, RerankWeights

__all__ = [
    "popular_section",
    "fresh_section",
    "diverse_by_country_section",
    "build_positioning_sections",
]


def _take_top(hits: list[RerankHit], top_k: int) -> list[RerankHit]:
    return hits[:top_k] if top_k > 0 else []


def popular_section(
    hits: list[RerankHit],
    popularity: Mapping[str, float],
    *,
    top_k: int = 5,
    popularity_weight: float = 0.7,
) -> list[RerankHit]:
    """Re-rank ``hits`` putting ``popularity_weight`` on the popularity signal.

    The relevance still contributes ``1 - popularity_weight`` so the
    list is not divorced from the user's query. Default weight is 0.7
    because a "Populares" section that ignores relevance would
    degenerate to a global top-N for any query.
    """
    if not 0.0 < popularity_weight < 1.0:
        raise ValueError(
            f"popularity_weight must be in (0, 1); got {popularity_weight}"
        )
    weights = RerankWeights(
        relevance=1.0 - popularity_weight,
        popularity=popularity_weight,
        freshness=0.0,
        personalization=0.0,
    )
    reranker = Reranker(weights=weights, popularity=popularity)
    return _take_top(reranker.rerank(hits), top_k)


def fresh_section(
    hits: list[RerankHit],
    freshness: Mapping[str, float],
    *,
    top_k: int = 5,
    freshness_weight: float = 0.7,
) -> list[RerankHit]:
    """Re-rank ``hits`` putting ``freshness_weight`` on the freshness signal.

    Same convex-combination logic as :func:`popular_section` so the
    list remains tied to the query while bubbling fresh content to the
    top.
    """
    if not 0.0 < freshness_weight < 1.0:
        raise ValueError(
            f"freshness_weight must be in (0, 1); got {freshness_weight}"
        )
    weights = RerankWeights(
        relevance=1.0 - freshness_weight,
        popularity=0.0,
        freshness=freshness_weight,
        personalization=0.0,
    )
    reranker = Reranker(weights=weights, freshness=freshness)
    return _take_top(reranker.rerank(hits), top_k)


def diverse_by_country_section(
    hits: list[RerankHit],
    country_by_id: Mapping[str, Optional[str]],
    *,
    top_k: int = 5,
) -> list[RerankHit]:
    """Greedy diversification by country.

    Iterates the input in relevance order. The first hit is always
    accepted. After that we only accept a hit whose country has not
    appeared yet in the section; once we run out of "new" countries
    we keep filling from the remaining hits in their original order
    so we always return up to ``top_k`` entries even when the corpus
    is concentrated in a few countries.

    Destinations without a known country (``None``) are treated as
    distinct from every other unknown so they do not block each other.
    """
    if top_k <= 0 or not hits:
        return []

    picked: list[RerankHit] = []
    seen: set[str] = set()
    leftovers: list[RerankHit] = []

    for hit in hits:
        if len(picked) >= top_k:
            break
        country = country_by_id.get(hit[0])
        if country is None or country not in seen:
            picked.append(hit)
            if country is not None:
                seen.add(country)
        else:
            leftovers.append(hit)

    # Fill remaining slots from the leftovers preserving order.
    if len(picked) < top_k:
        picked.extend(leftovers[: top_k - len(picked)])
    return picked


def build_positioning_sections(
    hits: list[RerankHit],
    *,
    popularity: Optional[Mapping[str, float]] = None,
    freshness: Optional[Mapping[str, float]] = None,
    country_by_id: Optional[Mapping[str, Optional[str]]] = None,
    top_k: int = 5,
) -> dict[str, list[RerankHit]]:
    """Compose the four positioning sections for a single retrieval.

    Returns a dict keyed by the section labels surfaced in the UI
    (``"relevantes"``, ``"populares"``, ``"recientes"``, ``"variados"``).
    Sections whose backing signal is missing are still emitted but
    fall back to the original relevance order, so the UI never has
    to handle a missing key.
    """
    relevantes = _take_top(hits, top_k)
    populares = popular_section(hits, popularity or {}, top_k=top_k) if popularity else relevantes
    recientes = fresh_section(hits, freshness or {}, top_k=top_k) if freshness else relevantes
    variados = (
        diverse_by_country_section(hits, country_by_id, top_k=top_k)
        if country_by_id
        else relevantes
    )
    return {
        "relevantes": relevantes,
        "populares": populares,
        "recientes": recientes,
        "variados": variados,
    }
