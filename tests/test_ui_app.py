"""T043 — Tests de la capa de llamada HTTP de la UI Streamlit.

La función :func:`search_destinations` se prueba pasándole un
:class:`fastapi.testclient.TestClient` (subclase de ``httpx.Client``) montado
sobre la app FastAPI real, para verificar que parsea correctamente la
respuesta del endpoint ``POST /search``.
"""
from __future__ import annotations

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.api.main import app, get_destinations, get_index, get_retriever_factory
from src.api.schemas import DestinationResult
from src.indexing.inverted_index import InvertedIndex
from src.retrieval.extended_boolean import ExtendedBoolean
from src.ui.app import pick_cover_image, search_destinations, truncate_description


def _build_index() -> InvertedIndex:
    idx = InvertedIndex()
    idx.add_document("doc-beach", ["beach", "sun", "sea"])
    idx.add_document("doc-mountain", ["mountain", "snow", "hike"])
    idx.compute_tf_idf()
    return idx


@pytest.fixture
def api_client() -> TestClient:
    idx = _build_index()
    app.dependency_overrides[get_index] = lambda: idx
    app.dependency_overrides[get_retriever_factory] = lambda: lambda p: ExtendedBoolean(p=p)
    app.dependency_overrides[get_destinations] = lambda: {
        "doc-beach": {
            "name": "Playa Azul",
            "country": "México",
            "description": "Arena blanca y mar tibio durante todo el año.",
            "image_urls": ["https://example.com/playa-azul.jpg"],
        },
        "doc-mountain": {
            "name": "Pico Nevado",
            "country": "Chile",
            "description": "Rutas de montaña con nieve eterna.",
            "image_urls": [],
        },
    }
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


def test_search_destinations_returns_ranked_results(api_client: TestClient) -> None:
    results = search_destinations("beach OR mountain", top_k=5, client=api_client)

    assert results, "Debe devolver al menos un resultado"
    assert all(isinstance(r, DestinationResult) for r in results)
    ids = {r.id for r in results}
    assert {"doc-beach", "doc-mountain"}.issubset(ids)
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_search_destinations_respects_top_k(api_client: TestClient) -> None:
    results = search_destinations("beach OR mountain", top_k=1, client=api_client)
    assert len(results) == 1


def test_search_destinations_propagates_metadata(api_client: TestClient) -> None:
    """T044 — La UI recibe nombre/país/descripción cuando la API los provee."""
    results = search_destinations("beach", top_k=5, client=api_client)
    top = next(r for r in results if r.id == "doc-beach")
    assert top.name == "Playa Azul"
    assert top.country == "México"
    assert top.description is not None
    assert "Arena blanca" in top.description


def test_search_destinations_propagates_image_urls(api_client: TestClient) -> None:
    """T045 — La UI recibe ``image_urls`` y degrada a lista vacía si faltan."""
    results = search_destinations("beach OR mountain", top_k=5, client=api_client)
    beach = next(r for r in results if r.id == "doc-beach")
    mountain = next(r for r in results if r.id == "doc-mountain")
    assert beach.image_urls == ["https://example.com/playa-azul.jpg"]
    assert mountain.image_urls == []


def test_search_destinations_forwards_p_parameter() -> None:
    """T047 — ``search_destinations`` envía ``p`` en el body a la API."""
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json
        captured.update(_json.loads(request.content))
        return httpx.Response(200, json={"results": []})

    transport = httpx.MockTransport(handler)
    with httpx.Client(base_url="http://test", transport=transport) as client:
        search_destinations("beach", top_k=7, p=3.5, client=client)

    assert captured == {"query": "beach", "top_k": 7, "p": 3.5}


def test_pick_cover_image_returns_first_valid_url() -> None:
    assert pick_cover_image(["https://a.jpg", "https://b.jpg"]) == "https://a.jpg"


def test_pick_cover_image_skips_empty_entries() -> None:
    assert pick_cover_image(["", "   ", "https://real.jpg"]) == "https://real.jpg"


def test_pick_cover_image_handles_missing_or_empty() -> None:
    assert pick_cover_image(None) is None
    assert pick_cover_image([]) is None
    assert pick_cover_image(["", "   "]) is None


def test_truncate_description_respects_limit() -> None:
    text = "palabra " * 80
    out = truncate_description(text, max_chars=50)
    assert len(out) <= 51  # incluye el carácter de elipsis
    assert out.endswith("…")


def test_truncate_description_keeps_short_text() -> None:
    assert truncate_description("corto") == "corto"
    assert truncate_description(None) == ""
    assert truncate_description("") == ""


def test_search_destinations_raises_on_http_error() -> None:
    def _fail() -> InvertedIndex:
        raise HTTPException(status_code=503, detail="index unavailable")

    app.dependency_overrides[get_index] = _fail
    app.dependency_overrides[get_retriever_factory] = lambda: lambda p: ExtendedBoolean(p=p)
    app.dependency_overrides[get_destinations] = lambda: {}

    try:
        with TestClient(app) as client:
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                search_destinations("beach", client=client)
            assert exc_info.value.response.status_code == 503
    finally:
        app.dependency_overrides.clear()
