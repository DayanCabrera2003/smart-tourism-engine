"""T16 - Tests for the Wikidata SPARQL client.

The tests stub httpx so they never hit the live SPARQL endpoint. We
verify (a) the binding parser handles the common shape produced by
Wikidata, and (b) the iterator skips malformed rows instead of
crashing.
"""
from __future__ import annotations

import httpx
import pytest

from src.ingestion.wikidata import WikidataClient, WikidataItem


def _make_binding(
    *,
    qid: str = "Q90",
    name_es: str = "París",
    name_en: str = "Paris",
    country_qid: str = "Q142",
    country_label: str = "Francia",
    coord: str = "Point(2.34 48.85)",
    image: str = "http://commons.wikimedia.org/wiki/Special:FilePath/Eiffel.jpg",
    population: str = "2161000",
    es_title: str = "París",
    en_title: str = "Paris",
) -> dict:
    return {
        "item": {"value": f"http://www.wikidata.org/entity/{qid}"},
        "itemLabel": {"value": name_es},
        "itemLabelEn": {"value": name_en},
        "country": {"value": f"http://www.wikidata.org/entity/{country_qid}"},
        "countryLabel": {"value": country_label},
        "coord": {"value": coord},
        "image": {"value": image},
        "population": {"value": population},
        "article_es": {"value": f"https://es.wikipedia.org/wiki/{es_title.replace(' ', '_')}"},
        "article_en": {"value": f"https://en.wikipedia.org/wiki/{en_title.replace(' ', '_')}"},
    }


def _build_client(bindings: list[dict]) -> WikidataClient:
    """Build a WikidataClient backed by a stubbed httpx.Client."""
    payload = {"results": {"bindings": bindings}}

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    http = httpx.Client(transport=transport, headers={"Accept": "application/sparql-results+json"})
    return WikidataClient(client=http)


def test_fetch_country_returns_parsed_items() -> None:
    binding = _make_binding()
    with _build_client([binding]) as client:
        items = list(client.fetch_country("FR"))

    assert len(items) == 1
    item = items[0]
    assert isinstance(item, WikidataItem)
    assert item.qid == "Q90"
    assert item.name_es == "París"
    assert item.name_en == "Paris"
    assert item.country == "Francia"
    assert item.country_qid == "Q142"
    assert item.latitude == pytest.approx(48.85)
    assert item.longitude == pytest.approx(2.34)
    assert item.population == 2_161_000
    assert item.wikipedia_es_title == "París"
    assert item.wikipedia_en_title == "Paris"


def test_fetch_country_skips_rows_missing_required_fields() -> None:
    good = _make_binding(qid="Q90", name_es="París")
    bad = {"itemLabel": {"value": "Anonymous"}}  # missing 'item' key
    with _build_client([bad, good]) as client:
        items = list(client.fetch_country("FR"))

    qids = [i.qid for i in items]
    assert qids == ["Q90"]


def test_fetch_country_handles_optional_coord_image_population() -> None:
    minimal = {
        "item": {"value": "http://www.wikidata.org/entity/Q1"},
        "itemLabel": {"value": "X"},
        "country": {"value": "http://www.wikidata.org/entity/Q2"},
        "countryLabel": {"value": "Country"},
        "article_es": {"value": "https://es.wikipedia.org/wiki/X"},
    }
    with _build_client([minimal]) as client:
        items = list(client.fetch_country("XX"))

    assert len(items) == 1
    item = items[0]
    assert item.latitude is None
    assert item.longitude is None
    assert item.image is None
    assert item.population is None
    assert item.wikipedia_en_title is None
    assert item.wikipedia_es_title == "X"


def test_fetch_country_handles_malformed_coord() -> None:
    binding = _make_binding(coord="Point(not a number)")
    with _build_client([binding]) as client:
        items = list(client.fetch_country("XX"))

    assert items[0].latitude is None
    assert items[0].longitude is None


def test_wikidata_item_is_immutable() -> None:
    item = WikidataItem(
        qid="Q1",
        name_es="X",
        name_en="X",
        country="C",
        country_qid="Q2",
        latitude=None,
        longitude=None,
        image=None,
        population=None,
        wikipedia_es_title=None,
        wikipedia_en_title=None,
    )
    from dataclasses import FrozenInstanceError

    with pytest.raises(FrozenInstanceError):
        item.qid = "Q999"  # type: ignore[misc]
