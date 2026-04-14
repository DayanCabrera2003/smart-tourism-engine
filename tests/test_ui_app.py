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

from src.api.main import app, get_index, get_retriever
from src.api.schemas import DestinationResult
from src.indexing.inverted_index import InvertedIndex
from src.retrieval.extended_boolean import ExtendedBoolean
from src.ui.app import search_destinations


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
    app.dependency_overrides[get_retriever] = lambda: ExtendedBoolean(p=2.0)
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


def test_search_destinations_raises_on_http_error() -> None:
    def _fail() -> InvertedIndex:
        raise HTTPException(status_code=503, detail="index unavailable")

    app.dependency_overrides[get_index] = _fail
    app.dependency_overrides[get_retriever] = lambda: ExtendedBoolean(p=2.0)

    try:
        with TestClient(app) as client:
            with pytest.raises(httpx.HTTPStatusError) as exc_info:
                search_destinations("beach", client=client)
            assert exc_info.value.response.status_code == 503
    finally:
        app.dependency_overrides.clear()
