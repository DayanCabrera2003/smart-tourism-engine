"""Unit del helper compartido de fallback web (run_web_fallback)."""
from __future__ import annotations

from src.web_search.fallback import run_web_fallback
from src.web_search.tavily import WebResult


class _FakeWebClient:
    def __init__(self, results):
        self._results = results
        self.calls = 0

    def search(self, query, *, max_results=5):
        self.calls += 1
        return self._results


class _FakeEmbedder:
    def embed(self, text, mode="passage"):
        return [0.1, 0.2, 0.3, 0.4]


class _FakeStore:
    def __init__(self):
        self.upserts = []

    def upsert(self, collection, points):
        self.upserts.append((collection, points))


def test_run_web_fallback_appends_web_hits_and_registers_destinations():
    web = _FakeWebClient(
        [WebResult(title="Hotels in Alaska", snippet="Best lodges near Denali.", url="http://x/a")]
    )
    destinations: dict[str, dict] = {}
    existing = [("doc-local", 0.42)]

    out = run_web_fallback(
        "hoteles en alaska",
        existing,
        web_client=web,
        embedder=_FakeEmbedder(),
        store=_FakeStore(),
        collection="destinations_text",
        destinations=destinations,
    )

    assert web.calls == 1
    # Los hits locales se preservan y los web se agregan al final.
    assert out[0] == ("doc-local", 0.42)
    assert len(out) == 2
    web_id = out[1][0]
    assert destinations[web_id]["from_web"] is True
    assert destinations[web_id]["name"] == "Hotels in Alaska"


def test_run_web_fallback_returns_existing_when_rate_limited():
    class _RateLimited:
        def search(self, query, *, max_results=5):
            raise RuntimeError("rate limit")

    existing = [("doc-local", 0.42)]
    out = run_web_fallback(
        "q",
        existing,
        web_client=_RateLimited(),
        embedder=_FakeEmbedder(),
        store=_FakeStore(),
        collection="c",
        destinations={},
    )
    assert out == existing
