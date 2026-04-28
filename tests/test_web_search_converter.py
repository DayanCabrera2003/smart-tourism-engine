"""T076 — Tests del convertidor WebResult -> Destination."""
from __future__ import annotations

import hashlib

from src.web_search.converter import web_result_to_destination
from src.web_search.tavily import WebResult


def test_conversion_fills_required_fields():
    wr = WebResult(title="Bali", snippet="Isla de Indonesia.", url="https://bali.com")
    dest = web_result_to_destination(wr)
    assert dest.id != ""
    assert dest.name == "Bali"
    assert dest.country == "web"
    assert dest.source == "tavily"
    assert "Indonesia" in dest.description


def test_conversion_id_is_url_hash():
    wr = WebResult(title="X", snippet="desc", url="https://example.com/page")
    dest = web_result_to_destination(wr)
    expected = "web-" + hashlib.sha256("https://example.com/page".encode()).hexdigest()[:12]
    assert dest.id == expected


def test_conversion_empty_snippet_uses_title():
    wr = WebResult(title="Roma", snippet="", url="https://roma.com")
    dest = web_result_to_destination(wr)
    assert dest.description != ""


def test_conversion_image_urls_empty():
    wr = WebResult(title="X", snippet="y", url="https://x.com")
    dest = web_result_to_destination(wr)
    assert dest.image_urls == []
