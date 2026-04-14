"""T042 — Tests del middleware de logging y manejo unificado de errores.

Cubre: (1) shape uniforme ``{code, message}`` para ``HTTPException``,
validación y excepciones no controladas; (2) cabecera ``X-Request-ID`` en
respuestas normales; (3) logging de cada request manejada.
"""
from __future__ import annotations

import logging

from fastapi.testclient import TestClient

from src.api.main import app


def test_validation_error_uses_unified_shape():
    client = TestClient(app)
    response = client.post("/search", json={"top_k": 3})
    assert response.status_code == 422
    body = response.json()
    assert body == {"code": "validation_error", "message": "Request payload inválido."}


def test_successful_response_has_request_id_header():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID")


def test_unhandled_exception_returns_500_json():
    @app.get("/_boom_t042", include_in_schema=False)
    def _boom() -> None:
        raise RuntimeError("kaboom")

    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/_boom_t042")
    assert response.status_code == 500
    body = response.json()
    assert body["code"] == "internal_error"
    assert body["message"]


def test_http_exception_uses_unified_shape(tmp_path, monkeypatch):
    from src.api import main as api_main
    from src.config import settings

    api_main._load_index_from_disk.cache_clear()
    monkeypatch.setattr(settings, "DATA_DIR", tmp_path)
    try:
        client = TestClient(app)
        response = client.post("/search", json={"query": "beach"})
    finally:
        api_main._load_index_from_disk.cache_clear()

    assert response.status_code == 503
    body = response.json()
    assert body["code"] == "service_unavailable"
    assert "Índice no disponible" in body["message"]


def test_request_is_logged(caplog):
    client = TestClient(app)
    with caplog.at_level(logging.INFO, logger="smart_tourism_engine.api"):
        response = client.get("/health")
    assert response.status_code == 200
    messages = [rec.getMessage() for rec in caplog.records]
    assert any("request handled" in msg for msg in messages)
