"""Tests for T127 — geographic filter for dense retrieval."""
from __future__ import annotations

from src.retrieval.geo_filter import (
    apply_country_filter,
    detect_countries,
    filter_search_hits,
    normalize,
)

# ─── normalize ────────────────────────────────────────────────────────


def test_normalize_strips_accents() -> None:
    assert normalize("España") == "espana"
    assert normalize("Perú") == "peru"
    assert normalize("Japón") == "japon"


def test_normalize_lowercases() -> None:
    assert normalize("CUBA") == "cuba"


def test_normalize_handles_none() -> None:
    assert normalize("") == ""


# ─── detect_countries ────────────────────────────────────────────────


def test_detect_countries_finds_spanish_name() -> None:
    assert detect_countries("playas en cuba") == {"Cuba"}


def test_detect_countries_finds_accented_name() -> None:
    assert detect_countries("destinos en España") == {"Spain"}


def test_detect_countries_finds_english_name() -> None:
    assert detect_countries("cities in Germany") == {"Germany"}


def test_detect_countries_finds_multiple() -> None:
    assert detect_countries("playas en cuba o mexico") == {"Cuba", "Mexico"}


def test_detect_countries_uk_aliases() -> None:
    assert detect_countries("destinos en Reino Unido") == {"United Kingdom"}
    assert detect_countries("travel to UK") == {"United Kingdom"}


def test_detect_countries_returns_empty_for_generic_query() -> None:
    assert detect_countries("ciudades historicas") == set()


def test_detect_countries_ignores_partial_word() -> None:
    # "cuba" should match, but not embedded in a longer word.
    assert detect_countries("incubando ideas") == set()


def test_detect_countries_empty_input() -> None:
    assert detect_countries("") == set()
    assert detect_countries("   ") == set()


# ─── apply_country_filter ────────────────────────────────────────────


def test_apply_country_filter_keeps_only_matching() -> None:
    hits = [
        {"id": "h", "country": "Cuba"},
        {"id": "lp", "country": "Spain"},
        {"id": "v", "country": "Cuba"},
    ]
    filtered = apply_country_filter(hits, "playas en cuba")
    assert [h["id"] for h in filtered] == ["h", "v"]


def test_apply_country_filter_returns_input_when_no_country_detected() -> None:
    hits = [{"id": "a", "country": "Spain"}, {"id": "b", "country": "Italy"}]
    out = apply_country_filter(hits, "ciudades historicas")
    assert out == hits


def test_apply_country_filter_returns_input_when_filter_would_empty() -> None:
    hits = [{"id": "a", "country": "Italy"}]
    # 'Cuba' is in the query but no Cuban hits; we keep the original
    # so the user does not see a blank page.
    out = apply_country_filter(hits, "playas en cuba")
    assert out == hits


def test_apply_country_filter_handles_objects_with_country_attr() -> None:
    class _Hit:
        def __init__(self, country: str) -> None:
            self.country = country

    hits = [_Hit("Cuba"), _Hit("Spain"), _Hit("Cuba")]
    out = apply_country_filter(hits, "destinos en cuba")
    assert [h.country for h in out] == ["Cuba", "Cuba"]


def test_apply_country_filter_supports_custom_getter() -> None:
    hits = [("v", 0.9, {"meta": {"pais": "Cuba"}}), ("lp", 0.8, {"meta": {"pais": "Spain"}})]
    out = apply_country_filter(
        hits, "cuba", country_getter=lambda h: h[2]["meta"].get("pais")
    )
    assert [h[0] for h in out] == ["v"]


# ─── filter_search_hits (Qdrant tuple shape) ─────────────────────────


def test_filter_search_hits_reads_country_from_payload() -> None:
    raw = [
        ("uuid-v", 0.9, {"slug": "varadero", "country": "Cuba"}),
        ("uuid-lp", 0.95, {"slug": "las-palmas", "country": "Spain"}),
        ("uuid-h", 0.85, {"slug": "havana", "country": "Cuba"}),
    ]
    out = filter_search_hits(raw, "playas en cuba")
    assert [h[0] for h in out] == ["uuid-v", "uuid-h"]


def test_filter_search_hits_no_country_query_passes_through() -> None:
    raw = [
        ("uuid-a", 0.9, {"slug": "a", "country": "Spain"}),
        ("uuid-b", 0.8, {"slug": "b", "country": "Italy"}),
    ]
    out = filter_search_hits(raw, "ciudades historicas")
    assert out == raw


# ─── Region aliases (T127.2) ─────────────────────────────────────────


def test_detect_countries_caribbean_alias_returns_caribbean_countries() -> None:
    countries = detect_countries("playas en el caribe")
    assert "Cuba" in countries
    assert "Dominican Republic" in countries
    assert "Puerto Rico" in countries
    assert "Spain" not in countries


def test_detect_countries_caribbean_english_alias() -> None:
    countries = detect_countries("beaches in the caribbean")
    assert {"Cuba", "Dominican Republic", "Puerto Rico"}.issubset(countries)


def test_detect_countries_mediterranean_alias() -> None:
    countries = detect_countries("ciudades del mediterraneo")
    assert "Spain" in countries
    assert "Italy" in countries
    assert "Greece" in countries


def test_detect_countries_asia_alias() -> None:
    countries = detect_countries("destinos en asia")
    assert "Japan" in countries
    assert "Thailand" in countries
    assert "Spain" not in countries


def test_detect_countries_europe_alias() -> None:
    countries = detect_countries("travel through europa")
    assert "Spain" in countries
    assert "France" in countries
    assert "Cuba" not in countries


def test_detect_countries_latin_america_alias() -> None:
    countries = detect_countries("destinos en latinoamerica")
    assert "Mexico" in countries
    assert "Argentina" in countries
    # The plain Caribbean countries are also part of LATAM
    assert "Cuba" in countries


def test_detect_countries_combines_region_and_country() -> None:
    countries = detect_countries("playas en cuba o el caribe")
    assert "Cuba" in countries
    assert "Dominican Republic" in countries


def test_detect_countries_iberia_alias() -> None:
    countries = detect_countries("destinos en iberia")
    assert countries == {"Spain", "Portugal"}


def test_detect_countries_scandinavia_alias() -> None:
    countries = detect_countries("paises nordicos para ver auroras")
    # Detects 'paises nordicos' as Scandinavia alias
    assert "Norway" in countries
    assert "Sweden" in countries
