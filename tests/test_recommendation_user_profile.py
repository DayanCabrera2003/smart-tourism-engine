"""Tests for T091 - UserProfile model and profile embedding builder."""
from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from src.recommendation.user_profile import (
    UserProfile,
    _average_vectors,
    _normalize,
    build_profile_embedding,
)


class _FakeEmbedder:
    """Deterministic stand-in for ``TextEmbedder`` in tests.

    Maps each token to a unit vector along a fixed axis. This makes it trivial
    to predict the aggregated embedding and keeps the test independent of any
    downloaded model.
    """

    def __init__(self, vocab: dict[str, list[float]]):
        self._vocab = vocab

    def embed(self, text: str, mode: str = "query") -> list[float]:
        return list(self._vocab[text])


def test_user_profile_defaults() -> None:
    profile = UserProfile(id="u1")
    assert profile.interests == []
    assert profile.history == []
    assert profile.embedding is None


def test_user_profile_validates_required_id() -> None:
    with pytest.raises(ValidationError):
        UserProfile()  # type: ignore[call-arg]


def test_average_vectors_returns_none_for_empty_input() -> None:
    assert _average_vectors([]) is None
    assert _average_vectors([[]]) is None


def test_average_vectors_averages_componentwise() -> None:
    result = _average_vectors([[1.0, 0.0], [0.0, 1.0]])
    assert result == [0.5, 0.5]


def test_average_vectors_raises_on_dimension_mismatch() -> None:
    with pytest.raises(ValueError):
        _average_vectors([[1.0, 0.0], [0.0]])


def test_normalize_unit_vector_is_unchanged() -> None:
    out = _normalize([1.0, 0.0, 0.0])
    assert out == [1.0, 0.0, 0.0]


def test_normalize_zero_vector_returns_copy() -> None:
    out = _normalize([0.0, 0.0])
    assert out == [0.0, 0.0]


def test_normalize_produces_unit_norm() -> None:
    out = _normalize([3.0, 4.0])
    norm = math.sqrt(sum(v * v for v in out))
    assert math.isclose(norm, 1.0)


def test_build_profile_embedding_from_interests() -> None:
    embedder = _FakeEmbedder({"playa": [1.0, 0.0], "sol": [0.0, 1.0]})
    profile = UserProfile(id="u1", interests=["playa", "sol"])
    vec = build_profile_embedding(profile, embedder)
    assert vec is not None
    # Average of [1,0] and [0,1] is [0.5, 0.5]; normalized.
    expected = _normalize([0.5, 0.5])
    assert vec == expected


def test_build_profile_embedding_combines_history() -> None:
    embedder = _FakeEmbedder({"playa": [1.0, 0.0]})
    profile = UserProfile(id="u1", interests=["playa"], history=["caribbean-mx"])
    history_vecs = {"caribbean-mx": [0.0, 1.0]}
    vec = build_profile_embedding(profile, embedder, history_embeddings=history_vecs)
    assert vec is not None
    expected = _normalize([0.5, 0.5])
    assert vec == expected


def test_build_profile_embedding_ignores_missing_history_ids() -> None:
    embedder = _FakeEmbedder({"playa": [1.0, 0.0]})
    profile = UserProfile(id="u1", interests=["playa"], history=["unknown"])
    vec = build_profile_embedding(profile, embedder, history_embeddings={})
    assert vec is not None
    assert vec == _normalize([1.0, 0.0])


def test_build_profile_embedding_returns_none_without_signal() -> None:
    embedder = _FakeEmbedder({})
    profile = UserProfile(id="u1")
    assert build_profile_embedding(profile, embedder) is None


def test_build_profile_embedding_ignores_blank_interests() -> None:
    embedder = _FakeEmbedder({"playa": [1.0, 0.0]})
    profile = UserProfile(id="u1", interests=["playa", "   "])
    vec = build_profile_embedding(profile, embedder)
    assert vec == _normalize([1.0, 0.0])
