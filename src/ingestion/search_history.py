"""T117 - Per-user search history persistence.

The Streamlit UI does not own a real user database (T097 stores the
synthetic profile id in ``st.session_state``), so the "user" of the
history table is just whatever identifier the caller passes. In the
current UI that maps to the synthetic profile id; once T118-T120 build
a real user model the same table will store its history without
schema changes.

Schema:

- ``id``: surrogate primary key, autoincremented.
- ``user_id``: free text (max 128). Indexed for the "recent searches
  by user" lookup.
- ``query``: the text the user typed.
- ``mode``: which retriever was used (boolean, semantic, hybrid).
- ``top_k``: the top_k value the user picked.
- ``created_at``: UTC timestamp.

The module exposes three operations: insert, list_recent and clear.
None of them require Qdrant or the LLM, so the search history works
even in fully offline demos.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
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
    "MAX_USER_ID_LENGTH",
    "MAX_QUERY_LENGTH",
    "search_history",
    "record_search",
    "list_recent_searches",
    "clear_user_history",
]


MAX_USER_ID_LENGTH = 128
MAX_QUERY_LENGTH = 512


search_history = Table(
    "search_history",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("user_id", String(MAX_USER_ID_LENGTH), nullable=False, index=True),
    Column("query", String(MAX_QUERY_LENGTH), nullable=False),
    Column("mode", String(32), nullable=False),
    Column("top_k", Integer, nullable=False),
    Column("created_at", DateTime, nullable=False),
    Index("ix_search_history_user_created", "user_id", "created_at"),
    extend_existing=True,
)


def _ensure_table() -> None:
    """Idempotent migration so legacy databases pick up the new table.

    ``metadata.create_all`` only creates missing tables; for an empty
    database it just works, and for a database that already has every
    other table it adds ``search_history`` without touching the rest.
    """
    inspector = inspect(engine)
    if not inspector.has_table(search_history.name):
        search_history.create(engine, checkfirst=True)


_ensure_table()


def record_search(
    user_id: str,
    query: str,
    *,
    mode: str = "boolean",
    top_k: int = 10,
    created_at: datetime | None = None,
) -> int:
    """Insert one history row and return the autoincremented id.

    Both ``user_id`` and ``query`` are truncated to their column limits
    so a misbehaving caller cannot trip an integrity error.
    """
    if not user_id or not user_id.strip():
        raise ValueError("user_id must be non-empty")
    if not query or not query.strip():
        raise ValueError("query must be non-empty")
    if top_k <= 0:
        raise ValueError(f"top_k must be > 0; got {top_k}")
    when = created_at or datetime.now(timezone.utc)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)

    values = {
        "user_id": user_id[:MAX_USER_ID_LENGTH],
        "query": query[:MAX_QUERY_LENGTH],
        "mode": mode,
        "top_k": int(top_k),
        "created_at": when,
    }
    with Session() as session:
        result = session.execute(search_history.insert().values(**values))
        session.commit()
        return int(result.inserted_primary_key[0])


def list_recent_searches(user_id: str, *, limit: int = 10) -> list[dict]:
    """Return up to ``limit`` recent searches for ``user_id``.

    The newest entry is first. Entries are returned as plain dicts to
    keep the caller decoupled from SQLAlchemy rows.
    """
    if limit <= 0:
        return []
    stmt = (
        select(search_history)
        .where(search_history.c.user_id == user_id)
        .order_by(desc(search_history.c.created_at))
        .limit(limit)
    )
    with Session() as session:
        rows = session.execute(stmt).mappings().all()
    return [dict(row) for row in rows]


def clear_user_history(user_id: str) -> int:
    """Delete every history row for ``user_id``. Returns the row count."""
    stmt = search_history.delete().where(search_history.c.user_id == user_id)
    with Session() as session:
        result = session.execute(stmt)
        session.commit()
        return int(result.rowcount or 0)
