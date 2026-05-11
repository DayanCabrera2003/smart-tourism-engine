"""T099 - Popularity score per destination.

The plan asks for a popularity score based on "number of sources that
mention the destination or reviews count". Our corpus is single-source
(Wikivoyage) and lacks review counts, so we approximate popularity from
two intrinsic signals:

1. **Description length** (primary). Wikivoyage editors invest more
   prose into destinations that are more visited and more discussed.
   The text length is the most reliable proxy we have without paid
   APIs.
2. **Cross-mentions** (secondary). How many other destinations in the
   corpus mention this destination by name in their description. A city
   that appears in the prose of many other entries is, by construction,
   notable in the regional travel discourse.

Both signals are normalized to ``[0, 1]`` and combined with a default
weight of 0.7 for description length and 0.3 for cross-mentions. The
final score lives in ``Destination.popularity`` and is computed once at
ingestion time (or via the recompute helper) so the recuperador can
read it without recomputing on every query.
"""
from __future__ import annotations

import re
from typing import Iterable, Optional

__all__ = [
    "DEFAULT_DESCRIPTION_WEIGHT",
    "DEFAULT_MENTION_WEIGHT",
    "compute_popularity_scores",
    "normalize_min_max",
]

DEFAULT_DESCRIPTION_WEIGHT = 0.7
DEFAULT_MENTION_WEIGHT = 0.3


def normalize_min_max(values: list[float]) -> list[float]:
    """Min-max scale a list of non-negative values into ``[0, 1]``.

    Empty input returns an empty list. When all values are equal we
    return zeros: there is no signal to differentiate destinations.
    """
    if not values:
        return []
    lo = min(values)
    hi = max(values)
    if hi == lo:
        return [0.0] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


def _name_pattern(name: str) -> Optional[re.Pattern[str]]:
    """Compile a word-boundary regex for ``name`` (case-insensitive).

    Returns ``None`` for names that are too short to be matched
    reliably (a single letter would match too aggressively).
    """
    cleaned = name.strip()
    if len(cleaned) < 3:
        return None
    return re.compile(rf"\b{re.escape(cleaned)}\b", re.IGNORECASE)


def _count_cross_mentions(
    target_name: str,
    target_id: str,
    corpus: Iterable[tuple[str, str]],
) -> int:
    """Count how many destinations mention ``target_name`` in their text.

    ``corpus`` is an iterable of ``(destination_id, description)``. The
    destination matching ``target_id`` is skipped so a destination does
    not count itself.
    """
    pattern = _name_pattern(target_name)
    if pattern is None:
        return 0
    count = 0
    for dest_id, description in corpus:
        if dest_id == target_id:
            continue
        if pattern.search(description or ""):
            count += 1
    return count


def compute_popularity_scores(
    destinations: list[dict],
    *,
    description_weight: float = DEFAULT_DESCRIPTION_WEIGHT,
    mention_weight: float = DEFAULT_MENTION_WEIGHT,
) -> dict[str, float]:
    """Compute popularity scores for a list of destination dicts.

    Each input dict must have ``id``, ``name`` and ``description``
    fields. Returns a dict ``id -> popularity`` with values in ``[0, 1]``.

    The two component scores (description length, cross-mentions) are
    min-max normalized independently across the corpus and combined
    with the provided weights. Weights are renormalized so they always
    sum to 1.0 even if the caller passes off-spec values.
    """
    if not destinations:
        return {}
    total_weight = description_weight + mention_weight
    if total_weight <= 0:
        raise ValueError("description_weight + mention_weight must be > 0")
    desc_w = description_weight / total_weight
    ment_w = mention_weight / total_weight

    descriptions = [(d["id"], d.get("description") or "") for d in destinations]
    lengths = [float(len(text)) for _, text in descriptions]
    mentions = [
        float(_count_cross_mentions(d["name"], d["id"], descriptions))
        for d in destinations
    ]
    norm_lengths = normalize_min_max(lengths)
    norm_mentions = normalize_min_max(mentions)

    return {
        d["id"]: desc_w * norm_lengths[i] + ment_w * norm_mentions[i]
        for i, d in enumerate(destinations)
    }
