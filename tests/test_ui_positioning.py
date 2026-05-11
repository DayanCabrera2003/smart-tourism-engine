"""Tests for T103 - the UI helper that turns DestinationResult lists into sections."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src.api.schemas import DestinationResult
from src.ui.app import (
    POSITIONING_SECTION_LABELS,
    build_positioning_sections_from_results,
)


def _result(
    doc_id: str,
    *,
    score: float = 0.5,
    country: str | None = None,
    popularity: float | None = None,
    fetched_at: str | None = None,
) -> DestinationResult:
    return DestinationResult(
        id=doc_id,
        score=score,
        country=country,
        popularity=popularity,
        fetched_at=fetched_at,
    )


def test_empty_results_returns_empty_sections() -> None:
    out = build_positioning_sections_from_results([])
    for key in POSITIONING_SECTION_LABELS:
        assert out[key] == []


def test_relevantes_preserves_input_order() -> None:
    results = [_result("a", score=0.9), _result("b", score=0.5)]
    out = build_positioning_sections_from_results(results, top_k=2)
    assert [r.id for r in out["relevantes"]] == ["a", "b"]


def test_populares_boosts_high_popularity() -> None:
    results = [
        _result("a", score=0.6, popularity=0.1),
        _result("b", score=0.6, popularity=0.9),
    ]
    out = build_positioning_sections_from_results(results, top_k=2)
    assert out["populares"][0].id == "b"


def test_recientes_boosts_recent_fetched_at() -> None:
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=365)).isoformat()
    recent = (now - timedelta(days=1)).isoformat()
    results = [
        _result("a", score=0.5, fetched_at=old),
        _result("b", score=0.5, fetched_at=recent),
    ]
    out = build_positioning_sections_from_results(results, top_k=2)
    assert out["recientes"][0].id == "b"


def test_variados_diversifies_by_country() -> None:
    results = [
        _result("a", score=0.95, country="Spain"),
        _result("b", score=0.94, country="Spain"),
        _result("c", score=0.90, country="France"),
    ]
    out = build_positioning_sections_from_results(results, top_k=2)
    ids = [r.id for r in out["variados"]]
    assert ids == ["a", "c"]


def test_sections_fall_back_to_relevantes_when_signals_missing() -> None:
    # No popularity, no fetched_at, no country — every section should
    # mirror the input order so the UI never shows a broken section.
    results = [_result("a", score=0.9), _result("b", score=0.5)]
    out = build_positioning_sections_from_results(results, top_k=2)
    for key in POSITIONING_SECTION_LABELS:
        assert [r.id for r in out[key]] == ["a", "b"]


def test_sections_preserve_destination_result_instances() -> None:
    results = [_result("a", score=0.9, country="X")]
    out = build_positioning_sections_from_results(results, top_k=1)
    assert out["relevantes"][0] is results[0]


def test_sections_respect_top_k() -> None:
    results = [_result(f"d{i}", score=0.9 - i * 0.05) for i in range(8)]
    out = build_positioning_sections_from_results(results, top_k=3)
    for section in out.values():
        assert len(section) <= 3
