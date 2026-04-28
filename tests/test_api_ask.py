"""T065 — Tests del endpoint POST /ask."""
from __future__ import annotations

from fastapi.testclient import TestClient

from src.api.main import app, get_rag_pipeline
from src.api.schemas import AskResponse, DestinationResult


class _StubPipeline:
    def answer(self, query: str, *, top_k: int = 5, mode: str = "hybrid", alpha: float = 0.5):
        low_conf = "zzz" in query.lower()
        answer_text = (
            "No tengo suficiente información para responder."
            if low_conf
            else f"Respuesta sobre {query} [1]."
        )
        return AskResponse(
            answer=answer_text,
            sources=[DestinationResult(id="doc-1", score=0.9, name="Ibiza", country="España")],
            cached=False,
            low_confidence=low_conf,
        )


def _client() -> TestClient:
    app.dependency_overrides[get_rag_pipeline] = lambda: _StubPipeline()
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_ask_returns_answer():
    c = _client()
    resp = c.post("/ask", json={"query": "playas en España"})
    assert resp.status_code == 200
    body = resp.json()
    assert "answer" in body
    assert len(body["answer"]) > 0


def test_ask_returns_sources():
    c = _client()
    resp = c.post("/ask", json={"query": "playas en España"})
    body = resp.json()
    assert "sources" in body
    assert len(body["sources"]) > 0


def test_ask_low_confidence_flag():
    c = _client()
    resp = c.post("/ask", json={"query": "zzzzxxx"})
    body = resp.json()
    assert body["low_confidence"] is True


def test_ask_empty_query_returns_422():
    c = _client()
    resp = c.post("/ask", json={"query": ""})
    assert resp.status_code == 422


def test_ask_default_params_accepted():
    c = _client()
    resp = c.post("/ask", json={"query": "playas"})
    assert resp.status_code == 200


def test_ask_custom_top_k_and_mode():
    c = _client()
    resp = c.post("/ask", json={"query": "museos", "top_k": 3, "mode": "semantic"})
    assert resp.status_code == 200
