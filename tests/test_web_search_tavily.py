"""T073 + T079 — Tests del cliente Tavily y rate limiter."""
from __future__ import annotations

import pytest

from src.web_search.tavily import RateLimiter, TavilyClient, WebResult

# ── RateLimiter ───────────────────────────────────────────────────────────────

def test_rate_limiter_allows_within_quota():
    limiter = RateLimiter(max_calls=3, period_seconds=60.0)
    assert limiter.is_allowed() is True
    assert limiter.is_allowed() is True
    assert limiter.is_allowed() is True


def test_rate_limiter_blocks_when_quota_exceeded():
    limiter = RateLimiter(max_calls=2, period_seconds=60.0)
    limiter.is_allowed()
    limiter.is_allowed()
    assert limiter.is_allowed() is False


def test_rate_limiter_resets_after_period(monkeypatch):
    import time

    start = time.monotonic()
    calls: list[int] = []

    def fake_monotonic() -> float:
        return start + (len(calls) * 31.0)

    monkeypatch.setattr(time, "monotonic", fake_monotonic)

    limiter = RateLimiter(max_calls=1, period_seconds=60.0)
    calls.append(1)
    limiter.is_allowed()  # consume quota
    calls.append(2)
    assert limiter.is_allowed() is False  # still in window
    calls.append(3)  # now > 60s later
    assert limiter.is_allowed() is True  # window reset


# ── WebResult ─────────────────────────────────────────────────────────────────

def test_web_result_fields():
    r = WebResult(title="Paris", snippet="Ciudad de la luz.", url="https://example.com")
    assert r.title == "Paris"
    assert r.snippet == "Ciudad de la luz."
    assert r.url == "https://example.com"


# ── TavilyClient ──────────────────────────────────────────────────────────────

def test_tavily_client_raises_when_rate_limited():
    """Si el rate limiter dice que no, debe lanzar RuntimeError."""
    client = TavilyClient(api_key="fake")
    client._rate_limiter = RateLimiter(max_calls=0, period_seconds=60.0)
    with pytest.raises(RuntimeError, match="rate limit"):
        client.search("playa")


def test_tavily_client_search_parses_response(monkeypatch):
    """search() convierte correctamente la respuesta JSON en WebResult."""
    import httpx

    fake_json = {
        "results": [
            {"title": "Ibiza", "content": "Isla balear.", "url": "https://ibiza.com"},
            {"title": "Mallorca", "content": "Otra isla.", "url": "https://mallorca.com"},
        ]
    }

    def fake_post(url, *, json, timeout):
        class FakeResponse:
            def raise_for_status(self) -> None:
                pass

            def json(self) -> dict:
                return fake_json

        return FakeResponse()

    monkeypatch.setattr(httpx, "post", fake_post)

    client = TavilyClient(api_key="fake-key")
    results = client.search("islas baleares", max_results=2)

    assert len(results) == 2
    assert results[0].title == "Ibiza"
    assert results[0].url == "https://ibiza.com"
    assert "balear" in results[0].snippet


def test_tavily_client_returns_empty_on_http_error(monkeypatch):
    """Un error HTTP devuelve lista vacía, no excepción."""
    import httpx

    def fake_post(url, *, json, timeout):
        raise httpx.HTTPStatusError("err", request=None, response=None)

    monkeypatch.setattr(httpx, "post", fake_post)

    client = TavilyClient(api_key="fake-key")
    results = client.search("query")
    assert results == []
