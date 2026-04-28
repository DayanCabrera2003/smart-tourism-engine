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


def test_generate_returns_string(monkeypatch):
    monkeypatch.setattr("src.rag.llm_client._build_genai_client", lambda key: _StubGenaiClient(api_key=key))
    client = LLMClient(provider="gemini", api_key="fake-key")
    result = client.generate("prompt de prueba")
    assert isinstance(result, str)
    assert len(result) > 0


def test_generate_stream_yields_tokens(monkeypatch):
    monkeypatch.setattr("src.rag.llm_client._build_genai_client", lambda key: _StubGenaiClient(api_key=key))
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
