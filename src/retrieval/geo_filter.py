"""T127 - Geographic filter for dense retrieval.

When the user writes a query that mentions a country ("playas en
cuba", "ciudades de Francia"), the dense retriever often returns a
foreign destination with a rich description higher than a local one
with a short description — the embedder weighs the topical word
("playas") more than the geographic anchor ("cuba"). The semantic
fix is to detect the country in the query and filter post-retrieval.

This module ships:

- ``COUNTRY_ALIASES`` — a mapping ``corpus country -> set of common
  aliases`` covering English and Spanish (the two languages our UI
  exposes). Only the countries present in the current corpus need
  entries; missing countries simply will not be detected.
- ``detect_countries(query)`` — return the set of corpus countries the
  query mentions.
- ``apply_country_filter(hits, query)`` — keep only hits whose
  ``country`` is among the detected countries. Returns the original
  list when no country is detected so generic queries are unaffected.
  When the filter would leave nothing, it returns the original list
  too — better degrade gracefully than answer with an empty page.

The module is pure (no Qdrant, no HTTP) so it can be unit tested
without integration scaffolding.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

__all__ = [
    "COUNTRY_ALIASES",
    "apply_country_filter",
    "detect_countries",
    "normalize",
]


def normalize(text: str) -> str:
    """Lowercase and strip accents so 'España' matches 'espana'."""
    text = unicodedata.normalize("NFD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return text.lower()


# Mapping corpus country (as stored in destinations.country) -> aliases.
# Aliases are stored in normalized form (lowercase, no accents). We
# keep this list small: only countries present in the Wikivoyage
# corpus (~45). Additions are cheap; spurious matches are not.
COUNTRY_ALIASES: dict[str, set[str]] = {
    "Spain": {"spain", "espana", "españa"},
    "France": {"france", "francia"},
    "Italy": {"italy", "italia"},
    "Germany": {"germany", "alemania"},
    "United Kingdom": {
        "united kingdom",
        "reino unido",
        "uk",
        "great britain",
        "gran bretana",
        "england",
        "inglaterra",
        "scotland",
        "escocia",
        "wales",
        "gales",
    },
    "Japan": {"japan", "japon"},
    "China": {"china"},
    "United States": {
        "united states",
        "usa",
        "estados unidos",
        "us",
        "estadounidense",
        "america",
    },
    "Mexico": {"mexico", "méxico"},
    "Brazil": {"brazil", "brasil"},
    "Peru": {"peru", "perú"},
    "Thailand": {"thailand", "tailandia"},
    "Colombia": {"colombia"},
    "Argentina": {"argentina"},
    "Cuba": {"cuba"},
    "Chile": {"chile"},
    "Australia": {"australia"},
    "Canada": {"canada", "canadá"},
    "Russia": {"russia", "rusia"},
    "India": {"india"},
    "Egypt": {"egypt", "egipto"},
    "Greece": {"greece", "grecia"},
    "Turkey": {"turkey", "turquia", "turquía"},
    "Vietnam": {"vietnam"},
    "South Korea": {"south korea", "corea del sur", "korea"},
    "Indonesia": {"indonesia"},
    "Singapore": {"singapore", "singapur"},
    "Malaysia": {"malaysia", "malasia"},
    "United Arab Emirates": {"united arab emirates", "emiratos arabes unidos", "uae"},
    "Morocco": {"morocco", "marruecos"},
    "Costa Rica": {"costa rica"},
    "Dominican Republic": {"dominican republic", "republica dominicana"},
    "Ecuador": {"ecuador"},
    "Bolivia": {"bolivia"},
    "Uruguay": {"uruguay"},
    "Paraguay": {"paraguay"},
    "Portugal": {"portugal"},
    "Netherlands": {"netherlands", "paises bajos", "holanda", "holland"},
    "Belgium": {"belgium", "belgica", "bélgica"},
    "Czech Republic": {"czech republic", "republica checa", "chequia"},
    "Austria": {"austria"},
    "Switzerland": {"switzerland", "suiza"},
    "Hungary": {"hungary", "hungria", "hungría"},
    "Poland": {"poland", "polonia"},
    "Norway": {"norway", "noruega"},
    "Sweden": {"sweden", "suecia"},
    "Denmark": {"denmark", "dinamarca"},
    "Finland": {"finland", "finlandia"},
    "Ireland": {"ireland", "irlanda"},
    "Iceland": {"iceland", "islandia"},
    "Croatia": {"croatia", "croacia"},
    "South Africa": {"south africa", "sudafrica", "sudáfrica"},
}


def _alias_pattern(alias: str) -> re.Pattern[str]:
    """Build a word-boundary regex matching the alias as a whole token."""
    return re.compile(rf"\b{re.escape(alias)}\b", re.IGNORECASE)


_ALIAS_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    country: [_alias_pattern(alias) for alias in aliases]
    for country, aliases in COUNTRY_ALIASES.items()
}


def detect_countries(query: str) -> set[str]:
    """Return the corpus countries mentioned in ``query``.

    Matching is whole-word and accent-insensitive. The empty set is
    returned when no country is detected; callers should treat that
    as "the user did not constrain by country".
    """
    if not query or not query.strip():
        return set()
    normalized = normalize(query)
    hits: set[str] = set()
    for country, patterns in _ALIAS_PATTERNS.items():
        for pattern in patterns:
            if pattern.search(normalized):
                hits.add(country)
                break
    return hits


def apply_country_filter(
    hits: list[Any],
    query: str,
    *,
    country_getter=None,
) -> list[Any]:
    """Filter ``hits`` to those whose country matches the query.

    Parameters:
        hits: list of items the retriever returned. Anything whose
            country can be read by ``country_getter`` is acceptable.
        query: the original user query.
        country_getter: callable ``hit -> str | None``. Defaults to
            reading the ``country`` key on a dict-like payload or
            attribute, falling back to ``None`` when neither is
            available.

    Returns the filtered list. When no country is detected in the
    query, or when filtering would empty the result, the input list
    is returned unchanged so the user still gets *something* (we do
    not want a country filter to turn a useful query into a blank
    page).
    """
    targets = detect_countries(query)
    if not targets:
        return list(hits)
    getter = country_getter or _default_country_getter
    filtered = [hit for hit in hits if (getter(hit) or "") in targets]
    if not filtered:
        return list(hits)
    return filtered


def _default_country_getter(hit: Any) -> str | None:
    """Extract a country field from a hit using common conventions."""
    if isinstance(hit, dict):
        return hit.get("country")
    return getattr(hit, "country", None)


def filter_search_hits(
    raw_hits: Iterable[tuple[Any, float, dict[str, Any]]],
    query: str,
) -> list[tuple[Any, float, dict[str, Any]]]:
    """Convenience wrapper for tuples ``(point_id, score, payload)``.

    Reads the country from ``payload['country']``. Used by the
    semantic / hybrid endpoints in :mod:`src.api.main`.
    """
    hits = list(raw_hits)
    return apply_country_filter(
        hits,
        query,
        country_getter=lambda h: h[2].get("country") if h[2] else None,
    )
