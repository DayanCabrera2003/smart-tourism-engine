"""T039 — Test del endpoint GET /health.

Verifica que la aplicación FastAPI exponga un endpoint de salud básico
que retorne `{"status": "ok"}` con código 200.
"""

from fastapi.testclient import TestClient

from src.api.main import app


def test_health_endpoint_returns_ok():
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
