"""T127 - Geographic filter for dense retrieval.

When the user writes a query that mentions a country or a region
("playas en cuba", "ciudades de Francia", "playas en el caribe"),
the dense retriever often returns a foreign destination with a rich
description higher than a local one with a short description — the
embedder weighs the topical word ("playas") more than the geographic
anchor. The semantic fix is to detect the location in the query and
filter post-retrieval to the matching set of countries.

This module ships:

- ``COUNTRY_ALIASES`` — corpus country -> common aliases in English
  and Spanish.
- ``REGION_TO_COUNTRIES`` — region name (Caribe, Mediterraneo, Asia,
  ...) -> set of corpus countries that fall under it.
- ``LOCATION_ALIASES`` — flat map ``alias -> set of countries to
  filter``. Built once at import time by combining the two tables
  above. Only countries present in the current corpus appear; missing
  countries simply will not be detected.
- ``detect_countries(query)`` — return the set of corpus countries
  implied by the query (union of all matched aliases).
- ``apply_country_filter(hits, query)`` — keep only hits whose
  ``country`` is among the detected countries. Returns the original
  list when no location is detected so generic queries are unaffected.
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
    "LOCATION_ALIASES",
    "REGION_TO_COUNTRIES",
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
    # The aliases include the country name in English and Spanish plus
    # the adjective forms ("italianas", "japoneses", "españolas"), so a
    # query like "ciudades italianas" can be resolved geographically
    # even when the user does not write the country name explicitly.
    "Spain": {
        "spain",
        "espana",
        "españa",
        "spanish",
        "español",
        "espanol",
        "española",
        "espanola",
        "españoles",
        "espanoles",
        "españolas",
        "espanolas",
    },
    "France": {
        "france",
        "francia",
        "french",
        "frances",
        "francés",
        "francesa",
        "franceses",
        "francesas",
    },
    "Italy": {
        "italy",
        "italia",
        "italian",
        "italiano",
        "italiana",
        "italianos",
        "italianas",
    },
    "Germany": {
        "germany",
        "alemania",
        "german",
        "aleman",
        "alemán",
        "alemana",
        "alemanes",
        "alemanas",
    },
    "United Kingdom": {
        "united kingdom",
        "reino unido",
        "uk",
        "great britain",
        "gran bretana",
        "british",
        "britanico",
        "británico",
        "britanica",
        "británica",
        "britanicos",
        "británicos",
        "britanicas",
        "británicas",
        "english",
        "england",
        "inglaterra",
        "ingles",
        "inglés",
        "inglesa",
        "ingleses",
        "inglesas",
        "scotland",
        "escocia",
        "scottish",
        "escoces",
        "escocés",
        "escocesa",
        "escoceses",
        "escocesas",
        "wales",
        "gales",
        "welsh",
    },
    "Japan": {
        "japan",
        "japon",
        "japón",
        "japanese",
        "japones",
        "japonés",
        "japonesa",
        "japoneses",
        "japonesas",
    },
    "China": {
        "china",
        "chino",
        "chinos",
        "chinas",
        "chinese",
    },
    "United States": {
        "united states",
        "usa",
        "estados unidos",
        "us",
        "estadounidense",
        "estadounidenses",
        "american",
        "americano",
        "americana",
        "americanos",
        "americanas",
    },
    "Mexico": {
        "mexico",
        "méxico",
        "mexican",
        "mexicano",
        "mexicana",
        "mexicanos",
        "mexicanas",
    },
    "Brazil": {
        "brazil",
        "brasil",
        "brazilian",
        "brasileño",
        "brasileno",
        "brasileña",
        "brasilena",
        "brasileños",
        "brasilenos",
        "brasileñas",
        "brasilenas",
    },
    "Peru": {
        "peru",
        "perú",
        "peruvian",
        "peruano",
        "peruana",
        "peruanos",
        "peruanas",
    },
    "Thailand": {
        "thailand",
        "tailandia",
        "thai",
        "tailandes",
        "tailandés",
        "tailandesa",
        "tailandeses",
        "tailandesas",
    },
    "Colombia": {
        "colombia",
        "colombian",
        "colombiano",
        "colombiana",
        "colombianos",
        "colombianas",
    },
    "Argentina": {
        "argentina",
        "argentinian",
        "argentino",
        "argentinos",
        "argentinas",
    },
    "Cuba": {
        "cuba",
        "cuban",
        "cubano",
        "cubana",
        "cubanos",
        "cubanas",
    },
    "Chile": {
        "chile",
        "chilean",
        "chileno",
        "chilena",
        "chilenos",
        "chilenas",
    },
    "Australia": {
        "australia",
        "australian",
        "australiano",
        "australiana",
        "australianos",
        "australianas",
    },
    "Canada": {
        "canada",
        "canadá",
        "canadian",
        "canadiense",
        "canadienses",
    },
    "Russia": {"russia", "rusia", "russian", "ruso", "rusa", "rusos", "rusas"},
    "India": {"india", "indian", "indio", "indios", "indias", "hindu"},
    "Egypt": {
        "egypt",
        "egipto",
        "egyptian",
        "egipcio",
        "egipcia",
        "egipcios",
        "egipcias",
    },
    "Greece": {
        "greece",
        "grecia",
        "greek",
        "griego",
        "griega",
        "griegos",
        "griegas",
    },
    "Turkey": {
        "turkey",
        "turquia",
        "turquía",
        "turkish",
        "turco",
        "turca",
        "turcos",
        "turcas",
    },
    "Vietnam": {
        "vietnam",
        "vietnamese",
        "vietnamita",
        "vietnamitas",
    },
    "South Korea": {
        "south korea",
        "corea del sur",
        "korea",
        "coreano",
        "coreana",
        "coreanos",
        "coreanas",
        "korean",
    },
    "Indonesia": {
        "indonesia",
        "indonesian",
        "indonesio",
        "indonesios",
        "indonesias",
    },
    "Singapore": {"singapore", "singapur"},
    "Malaysia": {"malaysia", "malasia"},
    "United Arab Emirates": {"united arab emirates", "emiratos arabes unidos", "uae"},
    "Morocco": {
        "morocco",
        "marruecos",
        "moroccan",
        "marroqui",
        "marroquí",
        "marroquies",
        "marroquíes",
    },
    "Costa Rica": {"costa rica", "costarricense", "costarricenses"},
    "Dominican Republic": {
        "dominican republic",
        "republica dominicana",
        "dominicano",
        "dominicana",
        "dominicanos",
        "dominicanas",
    },
    "Ecuador": {
        "ecuador",
        "ecuadorian",
        "ecuatoriano",
        "ecuatoriana",
        "ecuatorianos",
        "ecuatorianas",
    },
    "Bolivia": {
        "bolivia",
        "bolivian",
        "boliviano",
        "boliviana",
        "bolivianos",
        "bolivianas",
    },
    "Uruguay": {
        "uruguay",
        "uruguayan",
        "uruguayo",
        "uruguaya",
        "uruguayos",
        "uruguayas",
    },
    "Paraguay": {
        "paraguay",
        "paraguayan",
        "paraguayo",
        "paraguaya",
        "paraguayos",
        "paraguayas",
    },
    "Portugal": {
        "portugal",
        "portuguese",
        "portugues",
        "portugués",
        "portuguesa",
        "portugueses",
        "portuguesas",
    },
    "Netherlands": {
        "netherlands",
        "paises bajos",
        "holanda",
        "holland",
        "dutch",
        "holandes",
        "holandés",
        "holandesa",
        "holandeses",
        "holandesas",
    },
    "Belgium": {
        "belgium",
        "belgica",
        "bélgica",
        "belgian",
        "belga",
        "belgas",
    },
    "Czech Republic": {
        "czech republic",
        "republica checa",
        "chequia",
        "checo",
        "checa",
        "checos",
        "checas",
    },
    "Austria": {
        "austria",
        "austrian",
        "austriaco",
        "austriaca",
        "austriacos",
        "austriacas",
    },
    "Switzerland": {
        "switzerland",
        "suiza",
        "swiss",
        "suizo",
        "suizos",
        "suizas",
    },
    "Hungary": {
        "hungary",
        "hungria",
        "hungría",
        "hungarian",
        "hungaro",
        "húngaro",
        "hungara",
        "húngara",
        "hungaros",
        "húngaros",
        "hungaras",
        "húngaras",
    },
    "Poland": {
        "poland",
        "polonia",
        "polish",
        "polaco",
        "polaca",
        "polacos",
        "polacas",
    },
    "Norway": {
        "norway",
        "noruega",
        "norwegian",
        "noruego",
        "noruegos",
        "noruegas",
    },
    "Sweden": {"sweden", "suecia", "swedish", "sueco", "sueca", "suecos", "suecas"},
    "Denmark": {
        "denmark",
        "dinamarca",
        "danish",
        "danes",
        "danés",
        "danesa",
        "daneses",
        "danesas",
    },
    "Finland": {
        "finland",
        "finlandia",
        "finnish",
        "finlandes",
        "finlandés",
        "finlandesa",
        "finlandeses",
        "finlandesas",
    },
    "Ireland": {"ireland", "irlanda", "irish", "irlandes", "irlandés", "irlandesa"},
    "Iceland": {
        "iceland",
        "islandia",
        "icelandic",
        "islandes",
        "islandés",
        "islandesa",
    },
    "Croatia": {
        "croatia",
        "croacia",
        "croatian",
        "croata",
        "croatas",
    },
    "South Africa": {
        "south africa",
        "sudafrica",
        "sudáfrica",
        "south african",
        "sudafricano",
        "sudafricana",
        "sudafricanos",
        "sudafricanas",
    },
}


# Regions / continents -> set of corpus countries they cover. Only
# countries present in COUNTRY_ALIASES are referenced; missing ones
# would be silently ignored, but we kept the lists explicit so the
# scope of each region is auditable.
REGION_TO_COUNTRIES: dict[str, set[str]] = {
    "Caribbean": {"Cuba", "Dominican Republic", "Puerto Rico"},
    "Mediterranean": {
        "Spain",
        "France",
        "Italy",
        "Greece",
        "Turkey",
        "Morocco",
        "Croatia",
        "Egypt",
    },
    "Europe": {
        "Spain",
        "France",
        "Italy",
        "Germany",
        "United Kingdom",
        "Portugal",
        "Netherlands",
        "Belgium",
        "Czech Republic",
        "Austria",
        "Switzerland",
        "Hungary",
        "Poland",
        "Norway",
        "Sweden",
        "Denmark",
        "Finland",
        "Ireland",
        "Iceland",
        "Croatia",
        "Greece",
        "Russia",
    },
    "Asia": {
        "Japan",
        "China",
        "Thailand",
        "Vietnam",
        "South Korea",
        "Indonesia",
        "Singapore",
        "Malaysia",
        "India",
        "United Arab Emirates",
    },
    "Latin America": {
        "Mexico",
        "Brazil",
        "Peru",
        "Argentina",
        "Colombia",
        "Chile",
        "Ecuador",
        "Bolivia",
        "Uruguay",
        "Paraguay",
        "Costa Rica",
        "Cuba",
        "Dominican Republic",
        "Puerto Rico",
    },
    "South America": {
        "Brazil",
        "Peru",
        "Argentina",
        "Colombia",
        "Chile",
        "Ecuador",
        "Bolivia",
        "Uruguay",
        "Paraguay",
    },
    "Central America": {"Costa Rica"},
    "North America": {"United States", "Canada", "Mexico"},
    "Africa": {"Egypt", "Morocco", "South Africa"},
    "Oceania": {"Australia"},
    "Iberia": {"Spain", "Portugal"},
    "Scandinavia": {"Norway", "Sweden", "Denmark", "Finland", "Iceland"},
}


# Aliases for the regions above. Same normalization rules apply
# (lowercase, accent-insensitive).
_REGION_ALIASES: dict[str, set[str]] = {
    "Caribbean": {"caribbean", "caribe", "caribena", "caribeno", "antillas"},
    "Mediterranean": {"mediterranean", "mediterraneo", "mediterranea"},
    "Europe": {"europe", "europa", "europeo", "europea"},
    "Asia": {"asia", "asiatico", "asiatica"},
    "Latin America": {
        "latin america",
        "latinoamerica",
        "latinoamericano",
        "america latina",
    },
    "South America": {
        "south america",
        "sudamerica",
        "suramerica",
        "america del sur",
    },
    "Central America": {"central america", "centroamerica", "america central"},
    "North America": {
        "north america",
        "norteamerica",
        "america del norte",
    },
    "Africa": {"africa", "africano", "africana"},
    "Oceania": {"oceania"},
    "Iberia": {"iberia", "peninsula iberica"},
    "Scandinavia": {"scandinavia", "escandinavia", "nordic countries", "paises nordicos"},
}


def _build_location_aliases() -> dict[str, set[str]]:
    """Flatten countries + regions into ``alias -> set of countries``.

    All aliases are stored in their accent-stripped, lower-case form so
    that matching works against ``normalize(query)`` without further
    transformation. The author can write the alias with diacritics for
    readability (``"japón"``) and it gets normalized automatically.
    """
    table: dict[str, set[str]] = {}
    for country, aliases in COUNTRY_ALIASES.items():
        for alias in aliases:
            normalized_alias = normalize(alias)
            table.setdefault(normalized_alias, set()).add(country)
    for region, countries in REGION_TO_COUNTRIES.items():
        for alias in _REGION_ALIASES.get(region, set()):
            normalized_alias = normalize(alias)
            table.setdefault(normalized_alias, set()).update(countries)
    return table


LOCATION_ALIASES: dict[str, set[str]] = _build_location_aliases()


def _build_country_alias_set() -> set[str]:
    """Set of aliases that resolve to a single concrete country.

    Used to distinguish a query that mentions a specific country
    ("ciudades japonesas") from one that only mentions a region
    ("ciudades en el Caribe"). The first should trigger strict
    filtering (return empty when no candidate matches the country);
    the second falls back to the unfiltered list because a region is
    inherently ambiguous.
    """
    out: set[str] = set()
    for aliases in COUNTRY_ALIASES.values():
        for alias in aliases:
            out.add(normalize(alias))
    return out


_COUNTRY_ALIAS_SET: set[str] = _build_country_alias_set()


def _alias_pattern(alias: str) -> re.Pattern[str]:
    """Build a word-boundary regex matching the alias as a whole token.

    Multi-word aliases ('latin america') stay verbatim — the boundary
    metacharacters are placed at the extremes only.
    """
    return re.compile(rf"\b{re.escape(alias)}\b", re.IGNORECASE)


_ALIAS_PATTERNS: list[tuple[re.Pattern[str], set[str]]] = [
    (_alias_pattern(alias), targets)
    for alias, targets in LOCATION_ALIASES.items()
]


def detect_countries(query: str) -> set[str]:
    """Return the corpus countries implied by ``query``.

    Aliases match countries directly (``cuba`` -> {Cuba}) or regions
    (``caribe`` -> {Cuba, Dominican Republic, Puerto Rico}). Multiple
    aliases in the same query union their target sets. Matching is
    whole-word and accent-insensitive. The empty set is returned when
    no location is detected; callers should treat that as "the user
    did not constrain geographically".
    """
    if not query or not query.strip():
        return set()
    normalized = normalize(query)
    hits: set[str] = set()
    for pattern, targets in _ALIAS_PATTERNS:
        if pattern.search(normalized):
            hits.update(targets)
    return hits


def query_has_country_alias(query: str) -> bool:
    """Return True iff the query mentions a specific country alias.

    Distinguishes "ciudades en España" (country alias → strict-ready)
    from "ciudades en el Caribe" (region only → not strict). Helps
    callers decide whether to apply :func:`apply_country_filter` with
    ``strict=True``.
    """
    if not query or not query.strip():
        return False
    normalized = normalize(query)
    for alias in _COUNTRY_ALIAS_SET:
        if re.search(rf"\b{re.escape(alias)}\b", normalized):
            return True
    return False


def apply_country_filter(
    hits: list[Any],
    query: str,
    *,
    country_getter=None,
    strict: bool = False,
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
        strict: when ``True``, an empty filtered result is returned
            verbatim instead of falling back to the unfiltered list.
            Default is ``False`` because making strict automatic on
            country aliases empties the lexical retriever for
            Spanish queries against an English corpus (it has no
            country-matching candidates in its top-N).

    Returns the filtered list. When no country is detected in the
    query, the input list is returned unchanged. When filtering would
    empty the result, ``strict=True`` returns ``[]`` (and the UI can
    render "no results"); ``strict=False`` falls back to the
    unfiltered list so the user still sees *something*.
    """
    targets = detect_countries(query)
    if not targets:
        return list(hits)
    getter = country_getter or _default_country_getter
    filtered = [hit for hit in hits if (getter(hit) or "") in targets]
    if filtered:
        return filtered
    if strict:
        return []
    return list(hits)


def _default_country_getter(hit: Any) -> str | None:
    """Extract a country field from a hit using common conventions."""
    if isinstance(hit, dict):
        return hit.get("country")
    return getattr(hit, "country", None)


def filter_search_hits(
    raw_hits: Iterable[tuple[Any, float, dict[str, Any]]],
    query: str,
    *,
    strict: bool | None = None,
) -> list[tuple[Any, float, dict[str, Any]]]:
    """Convenience wrapper for tuples ``(point_id, score, payload)``.

    Reads the country from ``payload['country']``. Used by the
    semantic / hybrid endpoints in :mod:`src.api.main`. ``strict``
    propagates to :func:`apply_country_filter`.
    """
    hits = list(raw_hits)
    return apply_country_filter(
        hits,
        query,
        country_getter=lambda h: h[2].get("country") if h[2] else None,
        strict=strict,
    )
