"""T061 -- Tests de LLMClient (Gemini, stub)."""
from __future__ import annotations

import pytest

from src.rag.llm_client import LLMClient


class _StubGenaiClient:
    """Reemplaza google.genai.Client en tests."""

    def __init__(self, *, api_key: str) -> None:
        self.api_key = api_key

    class _Models:
        def generate_content(self, model: str, contents: str):
            class _Resp:
                text = "respuesta de prueba"
            return _Resp()

        def generate_content_stream(self, model: str, contents: str):
            for token in ["token1", " ", "token2"]:
                class _Chunk:
                    text = token
                yield _Chunk()

    @property
    def models(self):
        return self._Models()


def _patch_genai(monkeypatch):
    monkeypatch.setattr(
        "src.rag.llm_client._build_genai_client",
        lambda key: _StubGenaiClient(api_key=key),
    )


def test_generate_returns_string(monkeypatch):
    _patch_genai(monkeypatch)
    client = LLMClient(provider="gemini", api_key="fake-key")
    result = client.generate("prompt de prueba")
    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_stream_yields_tokens(monkeypatch):
    _patch_genai(monkeypatch)
    client = LLMClient(provider="gemini", api_key="fake-key")
    tokens = list(client.generate_stream("prompt de prueba"))
    assert len(tokens) >= 1
    assert all(isinstance(t, str) for t in tokens)


def test_raises_if_api_key_missing_in_gemini_mode():
    with pytest.raises(RuntimeError, match="LLM_API_KEY"):
        LLMClient(provider="gemini", api_key=None)


def test_raises_on_unknown_provider():
    with pytest.raises(ValueError, match="provider"):
        LLMClient(provider="unknown", api_key="key")


# T072 — Tests del proveedor Ollama
def test_ollama_generate_calls_correct_endpoint(monkeypatch):
    """Ollama usa la URL y modelo configurados."""
    import httpx

    calls = []

    class _MockResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"response": "respuesta ollama"}

    def _mock_post(url, *, json, timeout):
        calls.append({"url": url, "body": json})
        return _MockResponse()

    monkeypatch.setattr(httpx, "post", _mock_post)
    client = LLMClient(provider="ollama", ollama_url="http://test:11434", ollama_model="llama3")
    result = client.generate("prompt")

    assert result == "respuesta ollama"
    assert len(calls) == 1
    assert "http://test:11434" in calls[0]["url"]
    assert calls[0]["body"]["model"] == "llama3"


def test_ollama_no_api_key_required():
    """Ollama no requiere LLM_API_KEY."""
    client = LLMClient(provider="ollama", api_key=None)
    assert client is not None
