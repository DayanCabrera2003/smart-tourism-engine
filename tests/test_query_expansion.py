"""Tests for T119 — query expansion with synonym neighbours."""
from __future__ import annotations

import pytest

from src.retrieval.query_expansion import (
    expand_query,
    similar_terms,
)


class _FakeEmbedder:
    """Deterministic embedder driven by a token->vector dictionary."""

    def __init__(self, vocab: dict[str, list[float]], default_dim: int = 3):
        self._vocab = vocab
        self._default_dim = default_dim

    def embed(self, text: str) -> list[float]:
        if text in self._vocab:
            return list(self._vocab[text])
        return [0.0] * self._default_dim


def test_similar_terms_returns_top_neighbours_above_threshold() -> None:
    vocab = {
        "playa": [1.0, 0.0, 0.0],
        "beach": [0.95, 0.05, 0.0],
        "costa": [0.9, 0.1, 0.0],
        "litoral": [0.85, 0.15, 0.0],
        "montaña": [0.0, 1.0, 0.0],
    }
    embedder = _FakeEmbedder(vocab)
    result = similar_terms(
        "playa", vocab.keys(), embedder, max_terms=2, threshold=0.5
    )
    ids = [term for term, _ in result]
    assert "beach" in ids
    assert "costa" in ids
    assert "montaña" not in ids
    assert len(result) == 2


def test_similar_terms_respects_threshold() -> None:
    vocab = {
        "playa": [1.0, 0.0, 0.0],
        "beach": [0.95, 0.05, 0.0],
        "weak": [0.4, 0.4, 0.4],
    }
    embedder = _FakeEmbedder(vocab)
    result = similar_terms(
        "playa", vocab.keys(), embedder, max_terms=5, threshold=0.9
    )
    assert [term for term, _ in result] == ["beach"]


def test_similar_terms_handles_zero_max_terms() -> None:
    embedder = _FakeEmbedder({"a": [1.0, 0.0]})
    assert similar_terms("a", ["a"], embedder, max_terms=0) == []


def test_similar_terms_excludes_self() -> None:
    embedder = _FakeEmbedder({"a": [1.0, 0.0], "b": [0.99, 0.01]})
    result = similar_terms("a", ["a", "b"], embedder, max_terms=5, threshold=0.0)
    assert "a" not in [term for term, _ in result]


def test_expand_query_inserts_or_clauses() -> None:
    vocab = {
        "playa": [1.0, 0.0],
        "beach": [0.99, 0.01],
        "costa": [0.95, 0.05],
        "montaña": [0.0, 1.0],
    }
    embedder = _FakeEmbedder(vocab)
    out = expand_query(
        "playa AND montaña",
        vocab.keys(),
        embedder,
        max_terms_per_word=1,
        threshold=0.5,
    )
    # "playa" should expand with its top neighbour; AND must stay verbatim.
    assert "AND" in out
    assert "(playa OR beach)" in out or "(playa OR costa)" in out


def test_expand_query_keeps_operators_intact() -> None:
    embedder = _FakeEmbedder({})
    out = expand_query(
        "x AND y OR z",
        ["x", "y", "z"],
        embedder,
        max_terms_per_word=1,
    )
    # No neighbours -> tokens stay; operators stay where they were.
    assert out.split() == ["x", "AND", "y", "OR", "z"]


def test_expand_query_falls_back_when_no_neighbours_above_threshold() -> None:
    vocab = {
        "playa": [1.0, 0.0],
        "weak": [0.1, 0.1],
    }
    embedder = _FakeEmbedder(vocab)
    out = expand_query(
        "playa", vocab.keys(), embedder, max_terms_per_word=2, threshold=0.9
    )
    # Threshold too high -> original token returned verbatim.
    assert out == "playa"


def test_expand_query_preserves_parentheses() -> None:
    embedder = _FakeEmbedder({})
    out = expand_query("(a AND b) OR c", ["a", "b", "c"], embedder)
    # Parentheses stay; original tokens stay because no neighbours.
    assert "(" in out and ")" in out


def test_expand_query_uses_cache_to_avoid_re_embedding() -> None:
    calls: list[str] = []

    class _CountingEmbedder:
        def embed(self, text: str) -> list[float]:
            calls.append(text)
            return {"playa": [1.0, 0.0], "beach": [0.99, 0.01]}.get(
                text, [0.0, 0.0]
            )

    cache = {"beach": [0.99, 0.01]}
    expand_query(
        "playa",
        ["beach"],
        _CountingEmbedder(),
        term_embeddings=cache,
        max_terms_per_word=1,
        threshold=0.5,
    )
    # "playa" was embedded; "beach" was served from cache so the
    # counter did not record it.
    assert "playa" in calls
    assert calls.count("beach") == 0


def test_similar_terms_raises_on_dimension_mismatch() -> None:
    vocab = {"a": [1.0, 0.0], "b": [1.0]}
    embedder = _FakeEmbedder(vocab)
    with pytest.raises(ValueError):
        similar_terms("a", ["b"], embedder, threshold=0.0)
