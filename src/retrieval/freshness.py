"""T100 - Freshness score with exponential decay.

Tourist content goes stale: opening hours change, businesses close,
political situations evolve. A destination scraped six months ago is
less trustworthy than one scraped last week. We capture that with a
freshness score in ``[0, 1]`` derived from ``Destination.fetched_at``
and an exponential decay with a configurable half-life.

The score is computed on demand from the timestamp; we deliberately do
not persist it because:

1. It changes every minute (a persisted value would always be stale).
2. ``fetched_at`` is already persisted, so recomputation is free.

The decay constant is parameterized so the recuperador can tune how
aggressively old content is penalized. The default half-life of 180
days fits the cadence at which a manual review of tourism content tends
to be needed.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Optional, Union

__all__ = [
    "DEFAULT_HALF_LIFE_DAYS",
    "freshness_score",
]

DEFAULT_HALF_LIFE_DAYS = 180.0


def _parse_timestamp(value: Union[datetime, str]) -> datetime:
    """Coerce ``value`` to a timezone-aware ``datetime``.

    Accepts both ``datetime`` instances and ISO 8601 strings (the JSONL
    on disk stores timestamps as strings). Naive datetimes are assumed
    to be UTC, which matches how ``Destination`` builds them in
    :mod:`src.ingestion.models`.
    """
    if isinstance(value, str):
        # ``fromisoformat`` accepts "2026-04-14T02:18:51.459209Z" only
        # from Python 3.11 onward; we normalize the trailing Z for
        # safety.
        normalized = value.replace("Z", "+00:00")
        value = datetime.fromisoformat(normalized)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def freshness_score(
    fetched_at: Optional[Union[datetime, str]],
    *,
    now: Optional[datetime] = None,
    half_life_days: float = DEFAULT_HALF_LIFE_DAYS,
) -> float:
    """Return an exponential-decay freshness score in ``[0, 1]``.

    Formula::

        age_days = max(0, (now - fetched_at).total_seconds() / 86400)
        score = 2 ** (-age_days / half_life_days)

    A destination fetched at ``now`` scores 1.0. After one half-life
    the score drops to 0.5, after two half-lives to 0.25, and so on.
    Future timestamps (clock skew, manual data tampering) are clamped
    to ``now`` so the score stays bounded above by 1.0.

    Returns ``0.0`` when ``fetched_at`` is ``None`` (legacy rows with no
    timestamp signal): we cannot trust them, so they get the lowest
    score available.
    """
    if half_life_days <= 0:
        raise ValueError(f"half_life_days must be > 0; got {half_life_days}")
    if fetched_at is None:
        return 0.0
    fetched = _parse_timestamp(fetched_at)
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None:
        reference = reference.replace(tzinfo=timezone.utc)
    delta_seconds = (reference - fetched).total_seconds()
    age_days = max(0.0, delta_seconds / 86400.0)
    return math.pow(2.0, -age_days / half_life_days)
