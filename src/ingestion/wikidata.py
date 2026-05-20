"""T16 - Wikidata SPARQL client for the canonical destination list.

The previous corpus (Wikivoyage scrape, 179 docs after cleaning) has
sparse coverage: most countries get only 1-3 entries. To reach the
2500-3500 destinations target without paying for an API, we use
Wikidata as the canonical "what cities/towns/attractions exist" index
and pull text from Wikipedia ES later.

Wikidata exposes a public SPARQL endpoint with no auth required at
``https://query.wikidata.org/sparql``. The endpoint enforces a 60-
second per-query budget and asks every client to send a descriptive
User-Agent header. We paginate by country to keep each query small
and resilient to network blips.

A destination is "interesting" if it is an instance (P31) of one of:

- ``wd:Q515``  - city
- ``wd:Q3957`` - town
- ``wd:Q1549591`` - big city
- ``wd:Q5119`` - capital city
- ``wd:Q570116`` - tourist attraction
- ``wd:Q9259``  - UNESCO World Heritage Site
- ``wd:Q1968493`` - tourist destination (catch-all)

…and additionally has a Wikipedia ES article (so we have a source of
text downstream) and coordinates (so we can render it on the map).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Iterator, Optional

import httpx

logger = logging.getLogger(__name__)

__all__ = [
    "WikidataClient",
    "WikidataItem",
    "DEFAULT_USER_AGENT",
    "DEFAULT_SPARQL_ENDPOINT",
]

DEFAULT_SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
DEFAULT_USER_AGENT = (
    "smart-tourism-engine/0.1 (https://github.com/dayancc/smart-tourism-engine) "
    "httpx/0.28"
)

# Wikidata Q-ids for the entity classes we consider tourist-worthy.
DEFAULT_ENTITY_TYPES: tuple[str, ...] = (
    "Q515",  # city
    "Q3957",  # town
    "Q1549591",  # big city
    "Q5119",  # capital
    "Q570116",  # tourist attraction
    "Q9259",  # UNESCO World Heritage Site
    "Q1968493",  # tourist destination
)


@dataclass(frozen=True)
class WikidataItem:
    """A single destination row pulled from Wikidata."""

    qid: str
    name_es: str
    name_en: str
    country: str
    country_qid: str
    latitude: Optional[float]
    longitude: Optional[float]
    image: Optional[str]
    population: Optional[int]
    wikipedia_es_title: Optional[str]
    wikipedia_en_title: Optional[str]


_SPARQL_TEMPLATE = """
SELECT DISTINCT
  ?item ?itemLabel ?itemLabelEn
  ?country ?countryLabel
  ?coord ?image ?population
  ?article_es ?article_en
WHERE {{
  VALUES ?type {{ {types} }}
  ?item wdt:P31 ?type .
  ?item wdt:P17 ?country .
  ?country wdt:P297 "{country_code}" .
  ?article_es schema:about ?item ;
              schema:isPartOf <https://es.wikipedia.org/> .
  OPTIONAL {{ ?item wdt:P625 ?coord . }}
  OPTIONAL {{ ?item wdt:P18 ?image . }}
  OPTIONAL {{ ?item wdt:P1082 ?population . }}
  OPTIONAL {{
    ?article_en schema:about ?item ;
                schema:isPartOf <https://en.wikipedia.org/> .
  }}
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "es,en".
    ?item rdfs:label ?itemLabel.
    ?country rdfs:label ?countryLabel.
  }}
  SERVICE wikibase:label {{
    bd:serviceParam wikibase:language "en".
    ?item rdfs:label ?itemLabelEn.
  }}
}}
LIMIT {limit}
"""


class WikidataClient:
    """Thin SPARQL client tailored to the destination-list query."""

    def __init__(
        self,
        *,
        endpoint: str = DEFAULT_SPARQL_ENDPOINT,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = 60.0,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self._endpoint = endpoint
        self._user_agent = user_agent
        self._timeout = timeout
        self._client = client
        self._owns_client = client is None

    def __enter__(self) -> "WikidataClient":
        if self._client is None:
            self._client = httpx.Client(
                timeout=self._timeout,
                headers={
                    "User-Agent": self._user_agent,
                    "Accept": "application/sparql-results+json",
                },
            )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def _ensure_client(self) -> httpx.Client:
        if self._client is None:
            self.__enter__()
        assert self._client is not None
        return self._client

    def query(self, sparql: str) -> dict:
        """POST a SPARQL query and return the parsed JSON response."""
        client = self._ensure_client()
        response = client.post(
            self._endpoint,
            data={"query": sparql},
            headers={"Accept": "application/sparql-results+json"},
        )
        response.raise_for_status()
        return response.json()

    def fetch_country(
        self,
        country_code: str,
        *,
        limit: int = 200,
        entity_types: Iterable[str] = DEFAULT_ENTITY_TYPES,
    ) -> Iterator[WikidataItem]:
        """Yield destinations for a single ISO 3166-1 alpha-2 country code.

        Pagination is left to the caller: pass a higher ``limit`` to
        widen the net per country, but keep an eye on the SPARQL
        endpoint's 60-second budget. With 7 entity types, ~200
        candidates per country usually completes in 5-15 s.
        """
        types_clause = " ".join(f"wd:{q}" for q in entity_types)
        sparql = _SPARQL_TEMPLATE.format(
            types=types_clause,
            country_code=country_code.upper(),
            limit=limit,
        )
        logger.info(
            "Wikidata SPARQL: country=%s limit=%d",
            country_code,
            limit,
        )
        payload = self.query(sparql)
        for binding in payload.get("results", {}).get("bindings", []):
            item = _parse_binding(binding)
            if item is not None:
                yield item


def _parse_binding(binding: dict) -> Optional[WikidataItem]:
    """Convert one SPARQL JSON binding into a :class:`WikidataItem`.

    Returns ``None`` for malformed rows so the iterator can skip them
    rather than crashing on a missing field.
    """
    try:
        item_uri = binding["item"]["value"]
        qid = item_uri.rsplit("/", 1)[-1]
        name_es = binding["itemLabel"]["value"]
        name_en = binding.get("itemLabelEn", {}).get("value", name_es)
        country_uri = binding["country"]["value"]
        country_qid = country_uri.rsplit("/", 1)[-1]
        country_label = binding["countryLabel"]["value"]
    except KeyError:
        return None

    lat = lon = None
    coord = binding.get("coord", {}).get("value")
    if coord and coord.startswith("Point("):
        try:
            inner = coord[len("Point("):].rstrip(")")
            lon_s, lat_s = inner.split()
            lon = float(lon_s)
            lat = float(lat_s)
        except (ValueError, IndexError):
            lat = lon = None

    image = binding.get("image", {}).get("value")

    population = None
    pop_raw = binding.get("population", {}).get("value")
    if pop_raw:
        try:
            population = int(float(pop_raw))
        except ValueError:
            population = None

    wikipedia_es = _wikipedia_title(binding.get("article_es", {}).get("value"))
    wikipedia_en = _wikipedia_title(binding.get("article_en", {}).get("value"))

    return WikidataItem(
        qid=qid,
        name_es=name_es,
        name_en=name_en,
        country=country_label,
        country_qid=country_qid,
        latitude=lat,
        longitude=lon,
        image=image,
        population=population,
        wikipedia_es_title=wikipedia_es,
        wikipedia_en_title=wikipedia_en,
    )


def _wikipedia_title(article_url: Optional[str]) -> Optional[str]:
    """Extract the page title from a Wikipedia article URL.

    Wikipedia URLs look like ``https://es.wikipedia.org/wiki/Madrid``;
    we URL-decode the suffix so future API calls receive the title in
    plain UTF-8.
    """
    if not article_url:
        return None
    suffix = article_url.split("/wiki/", 1)[-1]
    from urllib.parse import unquote

    return unquote(suffix).replace("_", " ")
