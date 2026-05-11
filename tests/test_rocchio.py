"""Tests for T120 — Rocchio relevance feedback."""
from __future__ import annotations

import math

import pytest

from src.retrieval.rocchio import (
    DEFAULT_ALPHA,
    DEFAULT_BETA,
    DEFAULT_GAMMA,
    RocchioWeights,
    rocchio_update,
)


def _unit(v: list[float]) -> list[float]:
    norm = math.sqrt(sum(x * x for x in v))
    return [x / norm for x in v] if norm else v


def test_default_weights_are_literature_values() -> None:
    assert DEFAULT_ALPHA == 1.0
    assert DEFAULT_BETA == 0.75
    assert DEFAULT_GAMMA == 0.15


def test_weights_reject_negative_values() -> None:
    with pytest.raises(ValueError):
        RocchioWeights(alpha=-0.1)
    with pytest.raises(ValueError):
        RocchioWeights(beta=-1.0)
    with pytest.raises(ValueError):
        RocchioWeights(gamma=-0.5)


def test_no_feedback_returns_normalized_query() -> None:
    query = [3.0, 0.0]
    out = rocchio_update(query, feedback={}, document_embeddings={})
    assert out == _unit(query)


def test_positive_feedback_pulls_toward_relevant_centroid() -> None:
    # Query points along x. Two positive docs point along y. Rocchio
    # should shift the query toward (alpha * x + beta * y).
    query = [1.0, 0.0]
    docs = {"d1": [0.0, 1.0], "d2": [0.0, 1.0]}
    feedback = {"d1": 1, "d2": 1}
    out = rocchio_update(
        query,
        feedback,
        docs,
        weights=RocchioWeights(alpha=1.0, beta=1.0, gamma=0.0),
    )
    # Expected direction proportional to (1, 1), so y component > 0.
    assert out[1] > 0
    # And x kept positive too because alpha was 1.0.
    assert out[0] > 0


def test_negative_feedback_pushes_away_from_irrelevant_centroid() -> None:
    query = [1.0, 0.0]
    docs = {"d1": [1.0, 0.0]}
    feedback = {"d1": -1}
    out = rocchio_update(
        query,
        feedback,
        docs,
        weights=RocchioWeights(alpha=1.0, beta=0.0, gamma=1.0),
    )
    # After subtracting the irrelevant centroid the x component goes
    # to zero exactly (alpha=gamma=1, query=docs).
    # Normalization on a zero vector returns the zero vector itself.
    assert out == [0.0, 0.0]


def test_positive_and_negative_feedback_compose() -> None:
    query = [1.0, 0.0, 0.0]
    docs = {
        "good": [0.0, 1.0, 0.0],
        "bad": [0.0, 0.0, 1.0],
    }
    feedback = {"good": 1, "bad": -1}
    out = rocchio_update(
        query,
        feedback,
        docs,
        weights=RocchioWeights(alpha=1.0, beta=1.0, gamma=1.0),
    )
    # x stays (alpha=1), y goes up (beta), z goes down (-gamma).
    assert out[0] > 0
    assert out[1] > 0
    assert out[2] < 0


def test_missing_document_embedding_is_skipped() -> None:
    query = [1.0, 0.0]
    docs = {"known": [0.0, 1.0]}  # "ghost" is absent.
    feedback = {"known": 1, "ghost": 1}
    out = rocchio_update(query, feedback, docs)
    assert out  # Did not raise and returned something usable.


def test_dimension_mismatch_raises() -> None:
    query = [1.0, 0.0]
    docs = {"d1": [1.0, 0.0, 0.0]}  # 3-d while query is 2-d
    feedback = {"d1": 1}
    with pytest.raises(ValueError):
        rocchio_update(query, feedback, docs)


def test_zero_vote_is_ignored() -> None:
    # Only -1 and +1 are valid votes; the helper silently ignores
    # other values rather than raising so misbehaving callers do not
    # crash the retrieval path.
    query = [1.0, 0.0]
    docs = {"d1": [0.0, 1.0]}
    feedback = {"d1": 0}  # type: ignore[dict-item]
    out = rocchio_update(query, feedback, docs)
    assert out == _unit(query)


def test_normalize_can_be_disabled() -> None:
    query = [2.0, 0.0]
    out = rocchio_update(query, feedback={}, document_embeddings={}, normalize=False)
    assert out == [2.0, 0.0]


def test_unnormalized_output_uses_raw_centroid() -> None:
    query = [1.0, 0.0]
    docs = {"d1": [0.0, 4.0]}
    feedback = {"d1": 1}
    out = rocchio_update(
        query,
        feedback,
        docs,
        weights=RocchioWeights(alpha=1.0, beta=0.5, gamma=0.0),
        normalize=False,
    )
    # alpha*query + beta*centroid = [1, 0] + 0.5*[0, 4] = [1, 2]
    assert out == [1.0, 2.0]


def test_only_negative_feedback_still_modifies_query() -> None:
    query = [1.0, 0.0]
    docs = {"d1": [0.0, 1.0]}
    feedback = {"d1": -1}
    out = rocchio_update(query, feedback, docs)
    # With only negative feedback the query should shift along -y.
    assert out[1] < 0
