"""Tests for T126 — Wikipedia image client.

The tests use ``pytest-httpx`` (already in the dev extra) to stub the
Wikipedia REST endpoint and the actual image download. No real
network requests leave the suite.
"""
from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from pytest_httpx import HTTPXMock

from src.ingestion.wikipedia_images import (
    DEFAULT_USER_AGENT,
    ImageInfo,
    WikipediaImageClient,
    build_user_agent,
)

SUMMARY_OK = {
    "title": "Madrid",
    "pageid": 12345,
    "thumbnail": {
        "source": "https://upload.wikimedia.org/wikipedia/commons/thumb/madrid.jpg",
        "width": 320,
        "height": 213,
        "license": {"short_name": "CC BY-SA 4.0"},
    },
    "originalimage": {
        "source": "https://upload.wikimedia.org/wikipedia/commons/madrid.jpg",
        "width": 1920,
        "height": 1280,
    },
    "content_urls": {"desktop": {"page": "https://en.wikipedia.org/wiki/Madrid"}},
}


def _client(httpx_client: httpx.Client | None = None) -> WikipediaImageClient:
    return WikipediaImageClient(
        delay_seconds=0.0,  # tests should not wait
        client=httpx_client,
    )


def test_build_user_agent_returns_default_without_contact() -> None:
    assert build_user_agent() == DEFAULT_USER_AGENT


def test_build_user_agent_embeds_contact() -> None:
    ua = build_user_agent("foo@bar.com")
    assert "foo@bar.com" in ua


def test_fetch_summary_returns_image_info(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://en.wikipedia.org/api/rest_v1/page/summary/Madrid",
        json=SUMMARY_OK,
    )
    with _client() as client:
        info = client.fetch_summary("Madrid")
    assert isinstance(info, ImageInfo)
    assert info.title == "Madrid"
    assert info.page_id == 12345
    assert info.thumbnail_url and info.thumbnail_url.endswith("madrid.jpg")
    assert info.original_url and info.original_url.endswith("madrid.jpg")
    assert info.width == 320
    assert info.license_short_name == "CC BY-SA 4.0"
    assert info.page_url == "https://en.wikipedia.org/wiki/Madrid"


def test_fetch_summary_returns_none_for_404(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://en.wikipedia.org/api/rest_v1/page/summary/UnknownCity",
        status_code=404,
        text="not found",
    )
    with _client() as client:
        assert client.fetch_summary("UnknownCity") is None


def test_fetch_summary_returns_none_on_non_200(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://en.wikipedia.org/api/rest_v1/page/summary/Throttled",
        status_code=429,
        text="too many requests",
    )
    with _client() as client:
        assert client.fetch_summary("Throttled") is None


def test_fetch_summary_returns_none_on_transport_error(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_exception(httpx.ConnectError("boom"))
    with _client() as client:
        assert client.fetch_summary("AnyCity") is None


def test_fetch_summary_encodes_title_with_spaces(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://en.wikipedia.org/api/rest_v1/page/summary/Ho_Chi_Minh_City",
        json=SUMMARY_OK,
    )
    with _client() as client:
        assert client.fetch_summary("Ho Chi Minh City") is not None


def test_best_url_prefers_original_when_requested() -> None:
    info = ImageInfo(
        title="x",
        page_id=1,
        thumbnail_url="https://example.com/thumb.jpg",
        original_url="https://example.com/full.jpg",
        width=None,
        height=None,
        license_short_name=None,
        page_url=None,
    )
    assert info.best_url(prefer_original=True) == "https://example.com/full.jpg"
    assert info.best_url(prefer_original=False) == "https://example.com/thumb.jpg"


def test_best_url_falls_back_to_thumbnail_when_original_missing() -> None:
    info = ImageInfo(
        title="x",
        page_id=1,
        thumbnail_url="https://example.com/thumb.jpg",
        original_url=None,
        width=None,
        height=None,
        license_short_name=None,
        page_url=None,
    )
    assert info.best_url(prefer_original=True) == "https://example.com/thumb.jpg"


def test_download_writes_file(httpx_mock: HTTPXMock, tmp_path: Path) -> None:
    httpx_mock.add_response(
        url="https://upload.wikimedia.org/wikipedia/commons/madrid.jpg",
        content=b"\xff\xd8\xff fake jpeg bytes",
    )
    target = tmp_path / "madrid" / "wikipedia.jpg"
    with _client() as client:
        ok = client.download(
            "https://upload.wikimedia.org/wikipedia/commons/madrid.jpg", target
        )
    assert ok is True
    assert target.exists()
    assert target.stat().st_size > 0


def test_download_returns_false_on_http_error(
    httpx_mock: HTTPXMock, tmp_path: Path
) -> None:
    httpx_mock.add_response(
        url="https://upload.wikimedia.org/x.jpg", status_code=403
    )
    target = tmp_path / "x.jpg"
    with _client() as client:
        ok = client.download("https://upload.wikimedia.org/x.jpg", target)
    assert ok is False
    assert not target.exists()


def test_client_sends_user_agent(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(
        url="https://en.wikipedia.org/api/rest_v1/page/summary/Madrid",
        json=SUMMARY_OK,
    )
    custom_ua = "smart-tourism-engine-tests/0.1"
    custom_client = httpx.Client(
        headers={"User-Agent": custom_ua, "Accept": "application/json"}
    )
    try:
        with WikipediaImageClient(delay_seconds=0.0, client=custom_client) as c:
            c.fetch_summary("Madrid")
    finally:
        custom_client.close()
    requests = httpx_mock.get_requests()
    assert requests and requests[0].headers["User-Agent"] == custom_ua


@pytest.fixture
def httpx_mock(httpx_mock):
    # ``pytest-httpx`` ships with a fixture by the same name; this
    # indirection lets us pass non-matched URLs through.
    httpx_mock.non_mocked_hosts = []
    return httpx_mock
