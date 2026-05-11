"""T110 — End-to-end robustness tests for the API.

Each test exercises an endpoint with a payload that has historically
been a footgun (empty queries, oversized top_k, malformed lat/lon, bad
mode strings) and asserts the API answers with the right 4xx status
plus the unified error body, never a 500.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.main import app, get_destinations, get_index, get_recommendation_service
from src.api.middleware import qdrant_unavailable_handler
from src.indexing.inverted_index import InvertedIndex
from src.recommendation.service import RecommendationOutcome


def _index() -> InvertedIndex:
    idx = InvertedIndex()
    idx.add_document("doc-a", ["beach"])
    idx.compute_tf_idf()
    return idx


def _client_with_index() -> TestClient:
    app.dependency_overrides[get_index] = lambda: _index()
    app.dependency_overrides[get_destinations] = lambda: {}
    return TestClient(app, raise_server_exceptions=False)


def teardown_function() -> None:
    app.dependency_overrides.clear()


# ─── Inputs inválidos: deben dar 422 con cuerpo {code, message} ─────────


def test_search_empty_query_rejected_with_422() -> None:
    client = _client_with_index()
    r = client.post("/search", json={"query": "", "top_k": 5})
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "validation_error"


def test_search_top_k_above_max_rejected() -> None:
    client = _client_with_index()
    r = client.post("/search", json={"query": "beach", "top_k": 999})
    assert r.status_code == 422


def test_search_top_k_zero_rejected() -> None:
    client = _client_with_index()
    r = client.post("/search", json={"query": "beach", "top_k": 0})
    assert r.status_code == 422


def test_search_p_out_of_range_rejected() -> None:
    client = _client_with_index()
    r = client.post("/search", json={"query": "beach", "top_k": 5, "p": 100.0})
    assert r.status_code == 422


def test_search_missing_query_rejected() -> None:
    client = _client_with_index()
    r = client.post("/search", json={"top_k": 5})
    assert r.status_code == 422


def test_search_unknown_field_is_ignored() -> None:
    # Pydantic models ignore unknown fields by default; the request still
    # succeeds. Documenting it here in case the policy ever changes.
    client = _client_with_index()
    r = client.post(
        "/search",
        json={"query": "beach", "top_k": 5, "this_field_does_not_exist": True},
    )
    assert r.status_code == 200


def test_recommend_rejects_invalid_mode() -> None:
    client = _client_with_index()
    r = client.post("/recommend", json={"user_id": "mochilero", "mode": "nope"})
    assert r.status_code == 422


def test_recommend_alpha_out_of_range_rejected() -> None:
    client = _client_with_index()
    r = client.post(
        "/recommend",
        json={"user_id": "mochilero", "mode": "hybrid", "alpha": 1.5},
    )
    assert r.status_code == 422


def test_ask_rejects_invalid_mode() -> None:
    client = _client_with_index()
    r = client.post("/ask", json={"query": "x", "mode": "invalid"})
    assert r.status_code == 422


# ─── Recursos no disponibles: 503 limpio ──────────────────────────────


def test_recommend_returns_503_when_qdrant_down() -> None:
    """The Qdrant-aware service raises ResponseHandlingException; the
    new middleware handler should turn it into a 503."""
    from qdrant_client.http.exceptions import ResponseHandlingException

    class _DownService:
        def recommend(self, profile, *, top_k, mode, alpha):
            raise ResponseHandlingException(  # type: ignore[call-arg]
                source=RuntimeError("connection refused")
            )

    app.dependency_overrides[get_recommendation_service] = lambda: _DownService()
    app.dependency_overrides[get_destinations] = lambda: {}
    client = TestClient(app, raise_server_exceptions=False)

    r = client.post(
        "/recommend",
        json={"user_id": "synthetic:mochilero", "top_k": 5},
    )
    assert r.status_code == 503
    body = r.json()
    assert body["code"] == "service_unavailable"
    assert "Qdrant" in body["message"]


def test_recommend_returns_empty_when_no_signal_does_not_call_qdrant() -> None:
    """A profile without signal short-circuits before hitting Qdrant."""

    class _Service:
        def recommend(self, profile, *, top_k, mode, alpha):
            return RecommendationOutcome([], empty=True)

    app.dependency_overrides[get_recommendation_service] = lambda: _Service()
    app.dependency_overrides[get_destinations] = lambda: {}
    client = TestClient(app, raise_server_exceptions=False)

    r = client.post("/recommend", json={"top_k": 3})
    assert r.status_code == 200
    assert r.json()["empty"] is True


# ─── Errores internos: cuerpo unificado, no payload de stack ──────────


def test_internal_error_returns_unified_body() -> None:
    """Unhandled exceptions surface as 500 with the unified body shape."""

    class _BoomService:
        def recommend(self, profile, *, top_k, mode, alpha):
            raise ValueError("boom")

    app.dependency_overrides[get_recommendation_service] = lambda: _BoomService()
    app.dependency_overrides[get_destinations] = lambda: {}
    client = TestClient(app, raise_server_exceptions=False)

    r = client.post("/recommend", json={"user_id": "synthetic:mochilero", "top_k": 3})
    assert r.status_code == 500
    body = r.json()
    assert body["code"] == "internal_error"
    # The body must not leak the exception message or stack trace.
    assert "boom" not in body["message"].lower()


# ─── Validation por presencia del handler exportado ───────────────────


def test_qdrant_handler_is_installed() -> None:
    """Sanity check: middleware.install registered the Qdrant handler."""
    from qdrant_client.http.exceptions import ResponseHandlingException

    assert app.exception_handlers.get(ResponseHandlingException) is qdrant_unavailable_handler
