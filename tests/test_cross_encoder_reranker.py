"""T23 - Tests for the multilingual cross-encoder reranker wrapper.

The tests inject a mock CrossEncoder that returns deterministic scores
so they do not hit the network nor download any weights.
"""
from __future__ import annotations

import math

from src.retrieval.cross_encoder_reranker import CrossEncoderReranker


class _MockCE:
    """Tiny mock that returns a configurable score per pair index."""

    def __init__(self, raw_scores: list[float]) -> None:
        self.raw_scores = raw_scores
        self.calls: list[list[tuple[str, str]]] = []

    def predict(self, pairs):
        self.calls.append(list(pairs))
        return list(self.raw_scores)


def test_rerank_returns_sorted_by_descending_score() -> None:
    mock = _MockCE(raw_scores=[1.0, 5.0, -3.0])
    reranker = CrossEncoderReranker(model=mock)

    out = reranker.rerank(
        "Madrid",
        [
            ("doc-a", "some text a"),
            ("doc-b", "some text b"),
            ("doc-c", "some text c"),
        ],
    )

    ids = [doc_id for doc_id, _ in out]
    assert ids == ["doc-b", "doc-a", "doc-c"]


def test_rerank_scores_are_in_unit_interval() -> None:
    mock = _MockCE(raw_scores=[-100.0, 0.0, 100.0])
    reranker = CrossEncoderReranker(model=mock)

    out = reranker.rerank("q", [("a", "x"), ("b", "y"), ("c", "z")])
    scores = [s for _, s in out]
    assert all(0.0 <= s <= 1.0 for s in scores)
    # The neutral logit 0.0 maps to ~0.5 via sigmoid.
    middle = next(s for d, s in out if d == "b")
    assert math.isclose(middle, 0.5, abs_tol=1e-3)


def test_rerank_passes_query_with_each_document() -> None:
    mock = _MockCE(raw_scores=[1.0, 1.0])
    reranker = CrossEncoderReranker(model=mock)

    reranker.rerank("Tokio", [("a", "alpha"), ("b", "beta")])

    assert mock.calls == [[("Tokio", "alpha"), ("Tokio", "beta")]]


def test_rerank_empty_input_returns_empty_list() -> None:
    mock = _MockCE(raw_scores=[])
    reranker = CrossEncoderReranker(model=mock)

    assert reranker.rerank("q", []) == []
    assert mock.calls == []


def test_default_model_name() -> None:
    from src.retrieval.cross_encoder_reranker import DEFAULT_CROSS_ENCODER_MODEL

    assert DEFAULT_CROSS_ENCODER_MODEL == "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"
