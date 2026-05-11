"""Tests for T103 - UI positioning sections."""
from __future__ import annotations

import pytest

from src.retrieval.positioning import (
    build_positioning_sections,
    diverse_by_country_section,
    fresh_section,
    popular_section,
)


def test_popular_section_promotes_popular_destinations() -> None:
    hits = [("a", 0.6), ("b", 0.6), ("c", 0.6)]
    popularity = {"a": 0.1, "b": 0.9, "c": 0.5}
    out = popular_section(hits, popularity, top_k=3)
    assert [d for d, _ in out] == ["b", "c", "a"]


def test_popular_section_validates_weight_range() -> None:
    with pytest.raises(ValueError):
        popular_section([("a", 0.5)], {"a": 0.5}, popularity_weight=0.0)
    with pytest.raises(ValueError):
        popular_section([("a", 0.5)], {"a": 0.5}, popularity_weight=1.0)


def test_popular_section_caps_top_k() -> None:
    hits = [("a", 0.6), ("b", 0.6), ("c", 0.6)]
    out = popular_section(hits, {"a": 1.0, "b": 0.5, "c": 0.0}, top_k=2)
    assert len(out) == 2


def test_fresh_section_promotes_fresh_destinations() -> None:
    hits = [("a", 0.5), ("b", 0.5)]
    freshness = {"a": 0.1, "b": 0.9}
    out = fresh_section(hits, freshness, top_k=2)
    assert out[0][0] == "b"


def test_diverse_section_avoids_repeated_country() -> None:
    hits = [
        ("madrid", 0.95),
        ("barcelona", 0.94),
        ("seville", 0.93),
        ("paris", 0.90),
        ("rome", 0.85),
    ]
    countries = {
        "madrid": "Spain",
        "barcelona": "Spain",
        "seville": "Spain",
        "paris": "France",
        "rome": "Italy",
    }
    out = diverse_by_country_section(hits, countries, top_k=3)
    ids = [d for d, _ in out]
    # Top1 stays the same; the next two should be Paris and Rome, not
    # the second/third Spanish destination.
    assert ids == ["madrid", "paris", "rome"]


def test_diverse_section_falls_back_to_relevance_when_countries_exhausted() -> None:
    hits = [
        ("madrid", 0.95),
        ("barcelona", 0.94),
        ("seville", 0.93),
    ]
    countries = {
        "madrid": "Spain",
        "barcelona": "Spain",
        "seville": "Spain",
    }
    out = diverse_by_country_section(hits, countries, top_k=3)
    ids = [d for d, _ in out]
    # First Spanish destination always wins; the rest fill in
    # relevance order to satisfy top_k.
    assert ids == ["madrid", "barcelona", "seville"]


def test_diverse_section_treats_unknown_country_as_unique() -> None:
    hits = [("a", 0.9), ("b", 0.8), ("c", 0.7)]
    countries = {"a": None, "b": None, "c": "Spain"}
    out = diverse_by_country_section(hits, countries, top_k=3)
    ids = [d for d, _ in out]
    # Both unknowns pass through; "c" follows because it has a unique
    # country and never collides with the unknowns.
    assert ids == ["a", "b", "c"]


def test_diverse_section_handles_empty_input() -> None:
    assert diverse_by_country_section([], {}, top_k=5) == []


def test_diverse_section_zero_top_k() -> None:
    assert diverse_by_country_section([("a", 0.5)], {"a": "ES"}, top_k=0) == []


def test_build_sections_returns_all_four_keys() -> None:
    hits = [("a", 0.9), ("b", 0.5)]
    out = build_positioning_sections(
        hits,
        popularity={"a": 0.2, "b": 0.8},
        freshness={"a": 0.9, "b": 0.1},
        country_by_id={"a": "ES", "b": "FR"},
        top_k=2,
    )
    assert set(out.keys()) == {"relevantes", "populares", "recientes", "variados"}
    assert [d for d, _ in out["relevantes"]] == ["a", "b"]
    assert out["populares"][0][0] == "b"  # boosted by popularity
    assert out["recientes"][0][0] == "a"  # boosted by freshness


def test_build_sections_falls_back_when_signals_missing() -> None:
    hits = [("a", 0.9), ("b", 0.5)]
    out = build_positioning_sections(hits, top_k=2)
    # Without popularity/freshness/country, every section equals the
    # relevance order so the UI does not have to handle missing keys.
    for section in out.values():
        assert [d for d, _ in section] == ["a", "b"]


def test_build_sections_respects_top_k() -> None:
    hits = [(f"d{i}", 0.9 - i * 0.05) for i in range(10)]
    out = build_positioning_sections(
        hits,
        popularity={d: 0.5 for d, _ in hits},
        freshness={d: 0.5 for d, _ in hits},
        country_by_id={d: "X" for d, _ in hits},
        top_k=3,
    )
    for section in out.values():
        assert len(section) <= 3
