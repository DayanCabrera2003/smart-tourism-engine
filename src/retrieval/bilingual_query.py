"""Bilingual query expansion to bridge the embedder's cross-language gap.

multilingual-e5-small does well in both Spanish and English, but
cross-language retrieval (Spanish query → English document) is weaker
than mono-language. The corpus mixes Wikivoyage (English) with
Wikipedia ES; a query like "ciudades de Alemania" matches Polish
cities whose Spanish descriptions mention "alemán" instead of the
German Wikivoyage entries.

This module ships a small tourism-themed keyword dictionary and a
``expand_query(text)`` helper that appends the equivalent terms in
the *other* language. The expanded form is then embedded once and
fed to the dense retriever. Net effect: query gains both vocabularies
simultaneously, so it can resolve documents in either language.

The dictionary is deliberately small (~70 entries) — it covers the
high-frequency tourism vocabulary that drives most failing queries
in the eval set. It is *not* a general-purpose translator; phrases
not in the dictionary pass through unchanged.
"""
from __future__ import annotations

import re

__all__ = ["expand_query", "BILINGUAL_DICT"]


# Bidirectional tourism vocabulary. Each entry maps one form to its
# equivalent in the other language. ``expand_query`` looks up both
# directions so the same dict drives es→en and en→es expansion.
BILINGUAL_DICT: dict[str, str] = {
    # Country adjectives (the geo_filter already handles these for
    # post-retrieval filtering; including them here lets the embedder
    # see the English form too, which improves dense retrieval).
    "alemania": "germany",
    "alemanas": "german",
    "alemanes": "german",
    "alemán": "german",
    "francia": "france",
    "francesas": "french",
    "franceses": "french",
    "italia": "italy",
    "italianas": "italian",
    "italianos": "italian",
    "japón": "japan",
    "japon": "japan",
    "japonesas": "japanese",
    "japoneses": "japanese",
    "españa": "spain",
    "espana": "spain",
    "españolas": "spanish",
    "españoles": "spanish",
    "reino unido": "united kingdom",
    "inglaterra": "england",
    "estados unidos": "united states",
    "méxico": "mexico",
    "perú": "peru",
    "brasil": "brazil",
    "argentina": "argentina",
    "cuba": "cuba",
    "marruecos": "morocco",
    "egipto": "egypt",
    "china": "china",
    # Tourism nouns.
    "ciudad": "city",
    "ciudades": "cities",
    "playa": "beach",
    "playas": "beaches",
    "montaña": "mountain",
    "montañas": "mountains",
    "isla": "island",
    "islas": "islands",
    "desierto": "desert",
    "museo": "museum",
    "museos": "museums",
    "galería": "gallery",
    "galerías": "galleries",
    "catedral": "cathedral",
    "catedrales": "cathedrals",
    "templo": "temple",
    "templos": "temples",
    "iglesia": "church",
    "castillo": "castle",
    "vino": "wine",
    "vinícola": "wine",
    "vinícolas": "wine",
    "comida": "food",
    "gastronomía": "food",
    "gastronómica": "food",
    "vida nocturna": "nightlife",
    "arte": "art",
    "cultura": "culture",
    "historia": "history",
    "histórica": "historic",
    "históricas": "historic",
    "histórico": "historic",
    "históricos": "historic",
    "colonial": "colonial",
    "coloniales": "colonial",
    "medieval": "medieval",
    "medievales": "medieval",
    "destino": "destination",
    "destinos": "destinations",
    "región": "region",
    "regiones": "regions",
    "esquí": "skiing",
    "nieve": "snow",
    "tropical": "tropical",
    "tropicales": "tropical",
    "romántico": "romantic",
    "romántica": "romantic",
    "romanticos": "romantic",
    "luna de miel": "honeymoon",
    "aventura": "adventure",
    "mochilero": "backpacker",
    "lujo": "luxury",
    # Continents/regions.
    "europa": "europe",
    "asia": "asia",
    "áfrica": "africa",
    "africa": "africa",
    "sudamérica": "south america",
    "norteamérica": "north america",
    "centroamérica": "central america",
    "caribe": "caribbean",
    "mediterráneo": "mediterranean",
}


# Reverse direction so en→es works just as well. We keep the first
# Spanish hit per English token to stay deterministic.
def _build_reverse(table: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for spanish, english in table.items():
        out.setdefault(english.lower(), spanish)
    return out


_REVERSE_DICT: dict[str, str] = _build_reverse(BILINGUAL_DICT)


def _strip_accents(text: str) -> str:
    import unicodedata

    nfd = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in nfd if not unicodedata.combining(ch))


def expand_query(query: str) -> str:
    """Return the query enriched with translated keywords.

    Conservative: appends the translation only when the original keyword
    is present, never replaces. The dictionary keys are matched against
    the accent-stripped lowercase form of the query so "Japón" / "japon"
    both resolve. Multi-word keys ("vida nocturna", "luna de miel") are
    handled before single tokens to avoid partial matches.

    Returns the original query if no keyword is recognised.
    """
    if not query or not query.strip():
        return query

    lower = query.lower()
    no_accents = _strip_accents(lower)

    added: list[str] = []

    # Try multi-word keys first (longer wins so "vida nocturna" is
    # tried before "vida" alone would be).
    keys = sorted(BILINGUAL_DICT.keys() | _REVERSE_DICT.keys(), key=len, reverse=True)

    seen_translations: set[str] = set()
    for key in keys:
        key_clean = _strip_accents(key.lower())
        pattern = re.compile(rf"\b{re.escape(key_clean)}\b")
        if not pattern.search(no_accents):
            continue
        translation = BILINGUAL_DICT.get(key) or _REVERSE_DICT.get(key)
        if translation is None or translation in seen_translations:
            continue
        # Skip adding if the translation already appears in the original.
        if re.search(rf"\b{re.escape(_strip_accents(translation.lower()))}\b", no_accents):
            seen_translations.add(translation)
            continue
        added.append(translation)
        seen_translations.add(translation)

    if not added:
        return query
    return f"{query} {' '.join(added)}"
