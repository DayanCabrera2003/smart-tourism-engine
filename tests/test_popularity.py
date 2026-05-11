"""Tests for T099 - popularity scoring."""
from __future__ import annotations

import pytest

from src.retrieval.popularity import (
    compute_popularity_scores,
    normalize_min_max,
)


def test_normalize_empty_list() -> None:
    assert normalize_min_max([]) == []


def test_normalize_constant_list_returns_zeros() -> None:
    assert normalize_min_max([5.0, 5.0, 5.0]) == [0.0, 0.0, 0.0]


def test_normalize_scales_into_unit_interval() -> None:
    out = normalize_min_max([0.0, 5.0, 10.0])
    assert out == [0.0, 0.5, 1.0]


def test_compute_popularity_returns_score_per_destination() -> None:
    destinations = [
        {"id": "a", "name": "Madrid", "description": "x" * 100},
        {"id": "b", "name": "Barcelona", "description": "x" * 50},
    ]
    scores = compute_popularity_scores(destinations)
    assert set(scores.keys()) == {"a", "b"}
    assert all(0.0 <= s <= 1.0 for s in scores.values())


def test_longer_description_yields_higher_popularity() -> None:
    destinations = [
        {"id": "short", "name": "Aldea", "description": "Pueblo pequeño."},
        {"id": "long", "name": "Capital", "description": " ".join(["info"] * 200)},
    ]
    scores = compute_popularity_scores(destinations)
    assert scores["long"] > scores["short"]


def test_cross_mentions_boost_popularity() -> None:
    destinations = [
        {"id": "madrid", "name": "Madrid", "description": "Capital de España."},
        {"id": "toledo", "name": "Toledo", "description": "Cerca de Madrid."},
        {"id": "segovia", "name": "Segovia", "description": "Cerca de Madrid también."},
        {"id": "extra", "name": "Extra", "description": "Sin referencias relevantes."},
    ]
    scores = compute_popularity_scores(
        destinations, description_weight=0.0, mention_weight=1.0
    )
    # Madrid is mentioned by Toledo and Segovia; the rest are mentioned zero
    # times so they share the bottom score.
    assert scores["madrid"] == pytest.approx(1.0)
    assert scores["toledo"] == pytest.approx(0.0)
    assert scores["segovia"] == pytest.approx(0.0)


def test_destination_does_not_self_count_mentions() -> None:
    destinations = [
        {
            "id": "madrid",
            "name": "Madrid",
            # Mentions itself twice; should not boost the mention count.
            "description": "Madrid es la capital. Madrid tiene museos.",
        },
        {"id": "other", "name": "Otro", "description": "Sin referencia."},
    ]
    scores = compute_popularity_scores(
        destinations, description_weight=0.0, mention_weight=1.0
    )
    # Nobody else mentions Madrid -> Madrid has zero mentions across the
    # corpus, same as `other`; both get 0.0 after normalization.
    assert scores["madrid"] == pytest.approx(0.0)
    assert scores["other"] == pytest.approx(0.0)


def test_short_names_are_ignored_for_mentions() -> None:
    destinations = [
        # Two-letter names match too aggressively (e.g. "Vi" would match
        # "via", "Vienna"); we skip them.
        {"id": "vi", "name": "Vi", "description": "via via via"},
        {"id": "other", "name": "Otro", "description": "Vi aparece muchas veces."},
    ]
    scores = compute_popularity_scores(
        destinations, description_weight=0.0, mention_weight=1.0
    )
    assert scores["vi"] == pytest.approx(0.0)


def test_weights_are_renormalized() -> None:
    destinations = [
        {"id": "a", "name": "A", "description": "x"},
        {"id": "b", "name": "B", "description": "x" * 100},
    ]
    # Weights that do not sum to 1.0 are accepted and renormalized.
    scores = compute_popularity_scores(
        destinations, description_weight=7.0, mention_weight=3.0
    )
    assert all(0.0 <= s <= 1.0 for s in scores.values())


def test_empty_input_returns_empty_dict() -> None:
    assert compute_popularity_scores([]) == {}


def test_zero_total_weight_raises() -> None:
    with pytest.raises(ValueError):
        compute_popularity_scores(
            [{"id": "a", "name": "A", "description": "x"}],
            description_weight=0.0,
            mention_weight=0.0,
        )
