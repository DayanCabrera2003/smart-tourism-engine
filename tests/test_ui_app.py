"""T043/T055 — Tests de la capa de llamada HTTP de la UI Streamlit.

La función :func:`search_destinations` se prueba pasándole un
:class:`fastapi.testclient.TestClient` (subclase de ``httpx.Client``) montado
sobre la app FastAPI real, para verificar que parsea correctamente la
respuesta de los endpoints ``POST /search``, ``/search/semantic`` y
``/search/hybrid``.
"""
from __future__ import annotations

import math

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.api.main import (
    app,
    get_destinations,
    get_embedder,
    get_index,
    get_retriever_factory,
    get_semantic_collection,
    get_vector_store,
)
from src.api.schemas import DestinationResult
from src.indexing.embed_destinations import slug_to_uuid
from src.indexing.inverted_index import InvertedIndex
from src.indexing.vector_store import VectorStore
from src.retrieval.extended_boolean import ExtendedBoolean
from src.ui.app import (
    SEARCH_MODE_HYBRID,
    SEARCH_MODE_SEMANTIC,
    pick_cover_image,
    search_destinations,
    truncate_description,
)

_DESTINATIONS = {
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

_COLLECTION = "ui_test"
_DIM = 4


class _StubEmbedder:
    VECTORS: dict[str, list[float]] = {
        "beach": [1.0, 0.0, 0.0, 0.0],
        "mountain": [0.0, 1.0, 0.0, 0.0],
    }

    def embed(self, text: str) -> list[float]:
        key = text.strip().lower()
        if key in self.VECTORS:
            return list(self.VECTORS[key])
        raw = [float((ord(c) % 7) + 1) for c in (key or "x")[:_DIM]]
        raw.extend([0.0] * (_DIM - len(raw)))
        norm = math.sqrt(sum(v * v for v in raw)) or 1.0
        return [v / norm for v in raw]


def _build_index() -> InvertedIndex:
    idx = InvertedIndex()
    idx.add_document("doc-beach", ["beach", "sun", "sea"])
    idx.add_document("doc-mountain", ["mountain", "snow", "hike"])
    idx.compute_tf_idf()
    return idx


def _build_store() -> VectorStore:
    store = VectorStore(url=":memory:")
    store.create_collection(_COLLECTION, vector_size=_DIM)
    embedder = _StubEmbedder()
    points = [
        (slug_to_uuid("doc-beach"), embedder.embed("beach"), {"slug": "doc-beach"}),
        (slug_to_uuid("doc-mountain"), embedder.embed("mountain"), {"slug": "doc-mountain"}),
    ]
    store.upsert(_COLLECTION, points)
    return store


@pytest.fixture
def api_client() -> TestClient:
    idx = _build_index()
    store = _build_store()
    embedder = _StubEmbedder()
    app.dependency_overrides[get_index] = lambda: idx
    app.dependency_overrides[get_retriever_factory] = lambda: lambda p: ExtendedBoolean(p=p)
    app.dependency_overrides[get_destinations] = lambda: _DESTINATIONS
    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_embedder] = lambda: embedder
    app.dependency_overrides[get_semantic_collection] = lambda: _COLLECTION
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
    """T047 — ``search_destinations`` envía ``p`` en el body para el modo booleano."""
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json
        captured.update(_json.loads(request.content))
        return httpx.Response(200, json={"results": []})

    transport = httpx.MockTransport(handler)
    with httpx.Client(base_url="http://test", transport=transport) as client:
        search_destinations("beach", top_k=7, p=3.5, client=client)

    assert captured == {"query": "beach", "top_k": 7, "p": 3.5}


def test_search_destinations_semantic_mode(api_client: TestClient) -> None:
    """T055 — modo semántico llama a /search/semantic."""
    results = search_destinations("beach", mode=SEARCH_MODE_SEMANTIC, top_k=2, client=api_client)
    assert len(results) >= 1
    assert results[0].id == "doc-beach"


def test_search_destinations_hybrid_mode(api_client: TestClient) -> None:
    """T055 — modo híbrido llama a /search/hybrid y devuelve resultados."""
    results = search_destinations(
        "beach", mode=SEARCH_MODE_HYBRID, top_k=2, alpha=0.5, client=api_client
    )
    assert len(results) >= 1


def test_search_destinations_hybrid_sends_alpha() -> None:
    """T055 — modo híbrido incluye alpha en el payload."""
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json
        captured.update(_json.loads(request.content))
        return httpx.Response(200, json={"results": []})

    transport = httpx.MockTransport(handler)
    with httpx.Client(base_url="http://test", transport=transport) as client:
        search_destinations(
            "beach", mode=SEARCH_MODE_HYBRID, top_k=5, alpha=0.3, p=2.0, client=client
        )

    assert captured["alpha"] == 0.3
    assert captured["top_k"] == 5


def test_search_destinations_semantic_omits_p() -> None:
    """T055 — modo semántico no envía p ni alpha."""
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json as _json
        captured.update(_json.loads(request.content))
        return httpx.Response(200, json={"results": []})

    transport = httpx.MockTransport(handler)
    with httpx.Client(base_url="http://test", transport=transport) as client:
        search_destinations("beach", mode=SEARCH_MODE_SEMANTIC, top_k=3, client=client)

    assert "p" not in captured
    assert "alpha" not in captured
    assert captured == {"query": "beach", "top_k": 3}


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
