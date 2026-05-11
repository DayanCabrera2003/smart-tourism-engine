"""Tests for T104 - pure helpers behind the interactive map."""
from __future__ import annotations

import math

import pytest

from src.api.schemas import DestinationResult
from src.ui.app import (
    build_marker_popup_html,
    map_center,
    results_with_coordinates,
)


def _result(
    doc_id: str,
    *,
    lat: float | None = None,
    lon: float | None = None,
    name: str | None = None,
    country: str | None = None,
    description: str | None = None,
    score: float = 0.5,
) -> DestinationResult:
    return DestinationResult(
        id=doc_id,
        score=score,
        name=name,
        country=country,
        description=description,
        latitude=lat,
        longitude=lon,
    )


def test_results_with_coordinates_filters_missing() -> None:
    results = [
        _result("a", lat=40.0, lon=-3.7),
        _result("b"),  # no coords
        _result("c", lat=48.8, lon=2.3),
    ]
    filtered = results_with_coordinates(results)
    assert [r.id for r in filtered] == ["a", "c"]


def test_results_with_coordinates_treats_partial_as_missing() -> None:
    results = [
        _result("a", lat=40.0, lon=None),
        _result("b", lat=None, lon=-3.7),
    ]
    assert results_with_coordinates(results) == []


def test_map_center_returns_centroid_of_geocoded() -> None:
    results = [
        _result("a", lat=10.0, lon=20.0),
        _result("b", lat=30.0, lon=40.0),
    ]
    center = map_center(results)
    assert center is not None
    assert math.isclose(center[0], 20.0)
    assert math.isclose(center[1], 30.0)


def test_map_center_returns_none_without_coordinates() -> None:
    assert map_center([_result("a"), _result("b")]) is None


def test_marker_popup_html_includes_name_and_score() -> None:
    r = _result("a", lat=40.0, lon=-3.7, name="Madrid", score=0.81)
    html = build_marker_popup_html(r)
    assert "Madrid" in html
    assert "0.810" in html


def test_marker_popup_html_falls_back_to_id_when_name_missing() -> None:
    r = _result("destino-x", lat=0.0, lon=0.0)
    html = build_marker_popup_html(r)
    assert "destino-x" in html


def test_marker_popup_html_truncates_long_description() -> None:
    long_text = "x" * 500
    r = _result("a", lat=0.0, lon=0.0, description=long_text)
    html = build_marker_popup_html(r)
    # Truncated to 199 chars plus the ellipsis.
    assert "…" in html
    assert html.count("x") <= 200


def test_marker_popup_html_escapes_unsafe_characters() -> None:
    r = _result(
        "a",
        lat=0.0,
        lon=0.0,
        name='Hotel "Sol & Mar"',
        country="<script>",
        description="A & B",
    )
    html = build_marker_popup_html(r)
    # HTML special characters must be escaped to keep the popup intact.
    assert "&quot;" in html or "&#x22;" in html
    assert "&lt;script&gt;" in html
    assert "&amp;" in html


def test_marker_popup_html_omits_country_when_missing() -> None:
    r = _result("a", lat=0.0, lon=0.0, name="X")
    html = build_marker_popup_html(r)
    assert "<em>" not in html  # country block is gated on having a country


@pytest.mark.parametrize(
    "lat,lon",
    [(91.0, 0.0), (-91.0, 0.0), (0.0, 181.0), (0.0, -181.0)],
)
def test_destination_result_validates_lat_lon_range(lat: float, lon: float) -> None:
    with pytest.raises(ValueError):
        DestinationResult(id="x", score=0.5, latitude=lat, longitude=lon)
