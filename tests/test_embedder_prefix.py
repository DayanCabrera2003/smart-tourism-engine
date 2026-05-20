"""T4 - Tests for the query/passage prefix contract of TextEmbedder.

The ``intfloat/multilingual-e5-small`` model documents that callers
must prefix inputs depending on their role:

    - Query text  -> "query: <text>"
    - Document    -> "passage: <text>"

Without the prefix the model produces measurably worse vectors. The
``TextEmbedder`` must therefore apply the right prefix transparently
when invoked with ``mode="query"`` (the default) or ``mode="passage"``.
"""
from __future__ import annotations

import math

import pytest

from src.indexing.embedder import TextEmbedder


class _RecordingModel:
    """Captures the exact text sent to the model so tests can assert."""

    def __init__(self, dimension: int = 8) -> None:
        self.dimension = dimension
        self.received: list[str] = []

    def encode(self, text: str, normalize_embeddings: bool = False):
        self.received.append(text)
        # Return a small fixed vector; values don't matter for prefix tests.
        return [0.1 * (i + 1) for i in range(self.dimension)]


def test_embed_query_mode_prepends_query_prefix() -> None:
    stub = _RecordingModel()
    embedder = TextEmbedder(model=stub)

    embedder.embed("ciudades históricas", mode="query")

    assert stub.received == ["query: ciudades históricas"]


def test_embed_passage_mode_prepends_passage_prefix() -> None:
    stub = _RecordingModel()
    embedder = TextEmbedder(model=stub)

    embedder.embed("Madrid is the capital of Spain.", mode="passage")

    assert stub.received == ["passage: Madrid is the capital of Spain."]


def test_embed_defaults_to_query_mode() -> None:
    """Backwards-compatible default: legacy ``embed(text)`` is a query."""
    stub = _RecordingModel()
    embedder = TextEmbedder(model=stub)

    embedder.embed("plaza mayor")

    assert stub.received == ["query: plaza mayor"]


def test_embed_unknown_mode_raises_value_error() -> None:
    embedder = TextEmbedder(model=_RecordingModel())

    with pytest.raises(ValueError):
        embedder.embed("hola", mode="invalid")  # type: ignore[arg-type]


def test_default_model_name_is_multilingual_e5_small() -> None:
    """Guard against accidental reverts to the English-only baseline."""
    assert TextEmbedder.MODEL_NAME == "intfloat/multilingual-e5-small"
    assert TextEmbedder.DIMENSION == 384


def test_embed_preserves_normalization_call() -> None:
    """The embedder must still ask the model for unit-norm vectors."""
    captured: list[bool] = []

    class _NormCheckModel:
        def encode(self, text: str, normalize_embeddings: bool = False):
            captured.append(normalize_embeddings)
            return [1.0 / math.sqrt(8)] * 8

    embedder = TextEmbedder(model=_NormCheckModel())
    embedder.embed("anything")

    assert captured == [True]
