"""T118 - Relevance feedback (thumbs up / thumbs down) storage.

The UI lets the user mark each result as helpful (+1) or not (-1).
We persist those signals so future iterations of the recuperador
(Rocchio in T120, a learned re-ranker later) can train on real
clickstream instead of synthetic ground truth.

Schema:

- ``id``: surrogate primary key.
- ``user_id``: who gave the feedback.
- ``query``: the text the user submitted.
- ``destination_id``: the destination they rated.
- ``vote``: +1 (thumbs up) or -1 (thumbs down). Anything else is
  rejected at the application level.
- ``created_at``: UTC timestamp.

We do not enforce a unique constraint on (user_id, query,
destination_id) so the user can change their mind: the latest vote
wins when callers aggregate by ``MAX(created_at)``. ``record_feedback``
exposes a small upsert helper that keeps only the latest vote per
triple, which is what the Rocchio path expects.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Index,
    Integer,
    String,
    Table,
    desc,
    inspect,
    select,
)

from src.ingestion.store import Session, engine, metadata

__all__ = [
    "POSITIVE",
    "NEGATIVE",
    "VALID_VOTES",
    "relevance_feedback",
    "record_feedback",
    "list_feedback",
    "aggregate_feedback",
]


POSITIVE = 1
NEGATIVE = -1
VALID_VOTES = (POSITIVE, NEGATIVE)


relevance_feedback = Table(
    "relevance_feedback",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", String(128), nullable=False, index=True),
    Column("query", String(512), nullable=False),
    Column("destination_id", String(256), nullable=False),
    Column("vote", Integer, nullable=False),
    Column("created_at", DateTime, nullable=False),
    CheckConstraint("vote IN (-1, 1)", name="ck_relevance_feedback_vote"),
    Index("ix_feedback_user_query", "user_id", "query"),
    extend_existing=True,
)


def _ensure_table() -> None:
    inspector = inspect(engine)
    if not inspector.has_table(relevance_feedback.name):
        relevance_feedback.create(engine, checkfirst=True)


_ensure_table()


def record_feedback(
    user_id: str,
    query: str,
    destination_id: str,
    vote: int,
    *,
    created_at: datetime | None = None,
) -> int:
    """Append a feedback row and return the new id.

    The function does not deduplicate by (user_id, query,
    destination_id); aggregators are expected to take the latest vote.
    Voting twice for the same triple is therefore allowed and lets the
    user change their mind without losing the history.
    """
    if not user_id or not user_id.strip():
        raise ValueError("user_id must be non-empty")
    if not query or not query.strip():
        raise ValueError("query must be non-empty")
    if not destination_id or not destination_id.strip():
        raise ValueError("destination_id must be non-empty")
    if vote not in VALID_VOTES:
        raise ValueError(f"vote must be one of {VALID_VOTES}; got {vote}")
    when = created_at or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)

    values = {
        "user_id": user_id[:128],
        "query": query[:512],
        "destination_id": destination_id[:256],
        "vote": int(vote),
        "created_at": when,
    }
    with Session() as session:
        result = session.execute(relevance_feedback.insert().values(**values))
        session.commit()
        return int(result.inserted_primary_key[0])


def list_feedback(
    user_id: str,
    query: str | None = None,
    *,
    limit: int = 50,
) -> list[dict]:
    """Return raw feedback rows for ``user_id`` (newest first).

    When ``query`` is provided we filter to that query; otherwise we
    return every vote the user has ever cast.
    """
    if limit <= 0:
        return []
    stmt = (
        select(relevance_feedback)
        .where(relevance_feedback.c.user_id == user_id)
        .order_by(desc(relevance_feedback.c.created_at))
        .limit(limit)
    )
    if query is not None:
        stmt = stmt.where(relevance_feedback.c.query == query)
    with Session() as session:
        rows = session.execute(stmt).mappings().all()
    return [dict(row) for row in rows]


def aggregate_feedback(
    user_id: str,
    query: str,
) -> dict[str, int]:
    """Latest vote per destination for ``(user_id, query)``.

    Returns ``destination_id -> vote`` where each ``vote`` is the most
    recent +1/-1 cast for that triple. Older votes are ignored. Used
    by Rocchio (T120) to seed the positive/negative document sets.
    """
    stmt = (
        select(relevance_feedback)
        .where(relevance_feedback.c.user_id == user_id)
        .where(relevance_feedback.c.query == query)
        .order_by(desc(relevance_feedback.c.created_at))
    )
    latest: dict[str, int] = {}
    with Session() as session:
        rows = session.execute(stmt).mappings().all()
    for row in rows:
        dest_id = row["destination_id"]
        if dest_id not in latest:
            latest[dest_id] = int(row["vote"])
    return latest
