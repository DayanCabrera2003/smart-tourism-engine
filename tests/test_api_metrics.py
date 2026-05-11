"""Tests for T121 — Prometheus instrumentation."""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.main import app
from src.api.metrics import CACHE_EVENTS, REQUEST_COUNTER, record_cache_event


def _client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_metrics_endpoint_returns_text_format() -> None:
    client = _client()
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    body = r.text
    # Standard Prometheus output starts each metric with a HELP line.
    assert "# HELP smart_tourism_requests_total" in body


def test_request_counter_increments_after_a_call() -> None:
    client = _client()
    before = _get_counter_value(
        REQUEST_COUNTER, {"method": "GET", "path": "/health", "status_code": "200"}
    )
    client.get("/health")
    after = _get_counter_value(
        REQUEST_COUNTER, {"method": "GET", "path": "/health", "status_code": "200"}
    )
    assert after == before + 1


def test_metrics_endpoint_exposes_request_duration() -> None:
    client = _client()
    client.get("/health")
    r = client.get("/metrics")
    body = r.text
    assert "smart_tourism_request_duration_seconds" in body


def test_record_cache_event_increments_counter() -> None:
    before_hit = _get_counter_value(CACHE_EVENTS, {"cache": "rag", "event": "hit"})
    record_cache_event("rag", "hit")
    after_hit = _get_counter_value(CACHE_EVENTS, {"cache": "rag", "event": "hit"})
    assert after_hit == before_hit + 1


def test_failed_request_still_increments_counter() -> None:
    client = _client()
    # 422 path: POST /search with empty query
    before = _get_counter_value(
        REQUEST_COUNTER,
        {"method": "POST", "path": "/search", "status_code": "422"},
    )
    r = client.post("/search", json={"query": "", "top_k": 5})
    assert r.status_code == 422
    after = _get_counter_value(
        REQUEST_COUNTER,
        {"method": "POST", "path": "/search", "status_code": "422"},
    )
    assert after == before + 1


def _get_counter_value(counter, labels: dict[str, str]) -> float:
    """Helper that reads a Prometheus counter by label set."""
    # prometheus_client exposes the value via the internal _value attr.
    metric = counter.labels(**labels)
    return float(metric._value.get())
