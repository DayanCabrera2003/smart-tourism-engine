"""Tests for T118 — relevance feedback storage and /feedback endpoint."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.ingestion.feedback import (
    NEGATIVE,
    POSITIVE,
    aggregate_feedback,
    list_feedback,
    record_feedback,
    relevance_feedback,
)
from src.ingestion.store import engine


@pytest.fixture(autouse=True)
def _clean_table():
    with engine.begin() as conn:
        conn.execute(relevance_feedback.delete())
    yield
    with engine.begin() as conn:
        conn.execute(relevance_feedback.delete())


# ─── Module-level API ─────────────────────────────────────────────────


def test_record_feedback_inserts_row() -> None:
    new_id = record_feedback("u1", "madrid", "dest-a", POSITIVE)
    assert new_id > 0


def test_record_feedback_rejects_invalid_vote() -> None:
    with pytest.raises(ValueError):
        record_feedback("u1", "madrid", "dest-a", 0)
    with pytest.raises(ValueError):
        record_feedback("u1", "madrid", "dest-a", 2)


def test_record_feedback_rejects_empty_fields() -> None:
    with pytest.raises(ValueError):
        record_feedback("", "q", "d", POSITIVE)
    with pytest.raises(ValueError):
        record_feedback("u", "", "d", POSITIVE)
    with pytest.raises(ValueError):
        record_feedback("u", "q", "", POSITIVE)


def test_list_feedback_filters_by_user() -> None:
    record_feedback("u1", "q", "d-a", POSITIVE)
    record_feedback("u2", "q", "d-b", NEGATIVE)
    rows = list_feedback("u1")
    assert len(rows) == 1
    assert rows[0]["destination_id"] == "d-a"


def test_list_feedback_filters_by_query() -> None:
    record_feedback("u1", "madrid", "d-a", POSITIVE)
    record_feedback("u1", "paris", "d-b", POSITIVE)
    rows = list_feedback("u1", "madrid")
    assert [r["destination_id"] for r in rows] == ["d-a"]


def test_aggregate_feedback_returns_latest_vote_per_destination() -> None:
    base = datetime(2026, 6, 1, tzinfo=timezone.utc)
    # User votes +1, then changes mind and votes -1 for the same triple.
    record_feedback("u1", "madrid", "d-a", POSITIVE, created_at=base)
    record_feedback(
        "u1", "madrid", "d-a", NEGATIVE, created_at=base + timedelta(minutes=5)
    )
    record_feedback("u1", "madrid", "d-b", POSITIVE, created_at=base)

    agg = aggregate_feedback("u1", "madrid")
    assert agg == {"d-a": NEGATIVE, "d-b": POSITIVE}


def test_aggregate_feedback_isolates_users_and_queries() -> None:
    record_feedback("u1", "madrid", "d-a", POSITIVE)
    record_feedback("u1", "paris", "d-a", NEGATIVE)
    record_feedback("u2", "madrid", "d-a", NEGATIVE)
    assert aggregate_feedback("u1", "madrid") == {"d-a": POSITIVE}
    assert aggregate_feedback("u1", "paris") == {"d-a": NEGATIVE}


# ─── Endpoint ─────────────────────────────────────────────────────────


def _client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_endpoint_accepts_thumbs_up() -> None:
    client = _client()
    r = client.post(
        "/feedback",
        json={
            "user_id": "u1",
            "query": "madrid",
            "destination_id": "dest-a",
            "vote": POSITIVE,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert "id" in body
    assert body["id"] > 0


def test_endpoint_accepts_thumbs_down() -> None:
    client = _client()
    r = client.post(
        "/feedback",
        json={
            "user_id": "u1",
            "query": "madrid",
            "destination_id": "dest-a",
            "vote": NEGATIVE,
        },
    )
    assert r.status_code == 200


def test_endpoint_rejects_invalid_vote() -> None:
    client = _client()
    r = client.post(
        "/feedback",
        json={
            "user_id": "u1",
            "query": "madrid",
            "destination_id": "dest-a",
            "vote": 0,
        },
    )
    assert r.status_code == 422


def test_endpoint_rejects_empty_fields() -> None:
    client = _client()
    r = client.post(
        "/feedback",
        json={
            "user_id": "",
            "query": "madrid",
            "destination_id": "dest-a",
            "vote": POSITIVE,
        },
    )
    assert r.status_code == 422
