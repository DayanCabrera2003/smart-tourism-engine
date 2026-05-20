"""T17 - Tests for the Wikipedia MediaWiki client.

Uses httpx.MockTransport so the suite stays offline. Verifies the
extract parsing, the boilerplate stripping, the disk cache and the
fallback when the page is missing.
"""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest

from src.ingestion.wikipedia import WikipediaClient


def _payload_with_extract(extract: str, title: str = "Madrid") -> dict:
    return {
        "query": {
            "pages": [
                {
                    "pageid": 1,
                    "ns": 0,
                    "title": title,
                    "extract": extract,
                }
            ]
        }
    }


def _build_client(handler, tmp_path: Path) -> WikipediaClient:
    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport)
    return WikipediaClient(client=http, cache_dir=tmp_path, rate_limit_seconds=0.0)


def test_fetch_extract_returns_text(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_payload_with_extract("Madrid es la capital de España."))

    with _build_client(handler, tmp_path) as client:
        text = client.fetch_extract("Madrid")

    assert text == "Madrid es la capital de España."


def test_fetch_extract_returns_none_for_missing_page(tmp_path: Path) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"query": {"pages": [{"missing": True, "title": "Foo"}]}},
        )

    with _build_client(handler, tmp_path) as client:
        assert client.fetch_extract("Foo") is None


def test_fetch_extract_strips_see_also_section(tmp_path: Path) -> None:
    text = (
        "Madrid es la capital de España. Tiene museos importantes.\n\n"
        "== Véase también ==\n* Lista de cosas\n* Otra lista"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_payload_with_extract(text))

    with _build_client(handler, tmp_path) as client:
        cleaned = client.fetch_extract("Madrid")

    assert cleaned is not None
    assert "Véase también" not in cleaned
    assert cleaned.endswith("museos importantes.")


def test_fetch_extract_strips_references_in_english(tmp_path: Path) -> None:
    text = (
        "Madrid is the capital of Spain. It has many museums.\n"
        "== References ==\n* [1] Source"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_payload_with_extract(text))

    with _build_client(handler, tmp_path) as client:
        cleaned = client.fetch_extract("Madrid", language="en")

    assert cleaned is not None
    assert "References" not in cleaned


def test_cache_round_trip_avoids_second_http_call(tmp_path: Path) -> None:
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json=_payload_with_extract("cached text"))

    with _build_client(handler, tmp_path) as client:
        first = client.fetch_extract("Madrid")
        second = client.fetch_extract("Madrid")

    assert first == "cached text"
    assert second == "cached text"
    assert calls["count"] == 1


def test_force_refresh_bypasses_cache(tmp_path: Path) -> None:
    payloads = iter([
        _payload_with_extract("original"),
        _payload_with_extract("refreshed"),
    ])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=next(payloads))

    with _build_client(handler, tmp_path) as client:
        first = client.fetch_extract("Madrid")
        second = client.fetch_extract("Madrid", force_refresh=True)

    assert first == "original"
    assert second == "refreshed"


def test_unsupported_language_raises(tmp_path: Path) -> None:
    with _build_client(lambda r: httpx.Response(200, json={}), tmp_path) as client:
        with pytest.raises(ValueError):
            client.fetch_extract("Madrid", language="fr")
