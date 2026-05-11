"""Tests for T117 — per-user search history."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.ingestion.search_history import (
    MAX_QUERY_LENGTH,
    MAX_USER_ID_LENGTH,
    clear_user_history,
    list_recent_searches,
    record_search,
    search_history,
)
from src.ingestion.store import engine


@pytest.fixture(autouse=True)
def _clean_table():
    # Wipe the table before and after each test so they do not see each
    # other's writes.
    with engine.begin() as conn:
        conn.execute(search_history.delete())
    yield
    with engine.begin() as conn:
        conn.execute(search_history.delete())


def test_record_search_inserts_row_and_returns_id() -> None:
    new_id = record_search("user-1", "madrid", mode="boolean", top_k=10)
    assert isinstance(new_id, int)
    assert new_id > 0


def test_record_search_validates_user_id() -> None:
    with pytest.raises(ValueError):
        record_search("", "madrid")
    with pytest.raises(ValueError):
        record_search("   ", "madrid")


def test_record_search_validates_query() -> None:
    with pytest.raises(ValueError):
        record_search("user-1", "")


def test_record_search_validates_top_k() -> None:
    with pytest.raises(ValueError):
        record_search("user-1", "madrid", top_k=0)
    with pytest.raises(ValueError):
        record_search("user-1", "madrid", top_k=-1)


def test_record_search_truncates_long_inputs() -> None:
    long_user = "u" * (MAX_USER_ID_LENGTH + 50)
    long_query = "q" * (MAX_QUERY_LENGTH + 50)
    new_id = record_search(long_user, long_query)
    rows = list_recent_searches(long_user[:MAX_USER_ID_LENGTH], limit=1)
    assert len(rows) == 1
    assert rows[0]["id"] == new_id
    assert len(rows[0]["user_id"]) <= MAX_USER_ID_LENGTH
    assert len(rows[0]["query"]) <= MAX_QUERY_LENGTH


def test_list_recent_searches_returns_newest_first() -> None:
    base = datetime(2026, 6, 1, tzinfo=timezone.utc)
    record_search("user-1", "old", created_at=base)
    record_search("user-1", "newer", created_at=base + timedelta(hours=1))
    record_search("user-1", "newest", created_at=base + timedelta(hours=2))

    rows = list_recent_searches("user-1", limit=10)
    assert [r["query"] for r in rows] == ["newest", "newer", "old"]


def test_list_recent_searches_respects_limit() -> None:
    for i in range(5):
        record_search(
            "user-1",
            f"q{i}",
            created_at=datetime(2026, 6, 1, 12, i, tzinfo=timezone.utc),
        )
    rows = list_recent_searches("user-1", limit=3)
    assert len(rows) == 3


def test_list_recent_searches_isolates_users() -> None:
    record_search("user-1", "q-a")
    record_search("user-2", "q-b")
    rows_1 = list_recent_searches("user-1")
    rows_2 = list_recent_searches("user-2")
    assert [r["query"] for r in rows_1] == ["q-a"]
    assert [r["query"] for r in rows_2] == ["q-b"]


def test_list_recent_searches_zero_limit_returns_empty() -> None:
    record_search("user-1", "q")
    assert list_recent_searches("user-1", limit=0) == []


def test_clear_user_history_deletes_only_target_user() -> None:
    record_search("user-1", "q-a")
    record_search("user-1", "q-b")
    record_search("user-2", "q-c")
    removed = clear_user_history("user-1")
    assert removed == 2
    assert list_recent_searches("user-1") == []
    remaining = list_recent_searches("user-2")
    assert [r["query"] for r in remaining] == ["q-c"]


def test_clear_user_history_returns_zero_when_no_rows() -> None:
    assert clear_user_history("ghost") == 0
