"""T069 — Tests del endpoint POST /ask/stream (SSE)."""
from __future__ import annotations

import json

from fastapi.testclient import TestClient

from src.api.main import app, get_rag_pipeline
from src.api.schemas import DestinationResult


class _StubStreamPipeline:
    """Stub con answer_stream() que emite tokens + [DONE] + JSON de sources."""

    def answer_stream(
        self,
        query: str,
        *,
        top_k: int = 5,
        mode: str = "hybrid",
        alpha: float = 0.5,
    ):
        sources = [DestinationResult(id="doc-1", score=0.9, name="Ibiza", country="España")]
        yield "Respuesta "
        yield "de prueba [1]."
        yield "[DONE]"
        yield json.dumps({"sources": [s.model_dump() for s in sources], "low_confidence": False})


def _client() -> TestClient:
    stub = _StubStreamPipeline()
    app.dependency_overrides[get_rag_pipeline] = lambda: stub
    return TestClient(app)


def teardown_function():
    app.dependency_overrides.clear()


def test_stream_returns_200():
    c = _client()
    with c.stream("POST", "/ask/stream", json={"query": "playas"}) as resp:
        assert resp.status_code == 200


def test_stream_content_type_is_event_stream():
    c = _client()
    with c.stream("POST", "/ask/stream", json={"query": "playas"}) as resp:
        assert "text/event-stream" in resp.headers.get("content-type", "")


def test_stream_emits_data_lines():
    c = _client()
    lines = []
    with c.stream("POST", "/ask/stream", json={"query": "playas"}) as resp:
        for line in resp.iter_lines():
            if line:
                lines.append(line)
    data_lines = [line for line in lines if line.startswith("data:")]
    assert len(data_lines) >= 2


def test_stream_contains_done_event():
    c = _client()
    all_data = []
    with c.stream("POST", "/ask/stream", json={"query": "playas"}) as resp:
        for line in resp.iter_lines():
            if line.startswith("data:"):
                all_data.append(line[len("data:"):].strip())
    assert "[DONE]" in all_data


def test_stream_final_event_has_sources():
    c = _client()
    all_data = []
    with c.stream("POST", "/ask/stream", json={"query": "playas"}) as resp:
        for line in resp.iter_lines():
            if line.startswith("data:"):
                all_data.append(line[len("data:"):].strip())
    json_events = [d for d in all_data if d.startswith("{")]
    assert len(json_events) >= 1
    parsed = json.loads(json_events[-1])
    assert "sources" in parsed
    assert len(parsed["sources"]) > 0
