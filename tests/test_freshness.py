"""Tests for T100 - exponential-decay freshness score."""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

import pytest

from src.retrieval.freshness import freshness_score


def _now() -> datetime:
    return datetime(2026, 6, 1, tzinfo=timezone.utc)


def test_score_is_1_for_just_fetched() -> None:
    assert freshness_score(_now(), now=_now()) == pytest.approx(1.0)


def test_score_is_0_for_missing_timestamp() -> None:
    assert freshness_score(None, now=_now()) == 0.0


def test_score_halves_after_one_half_life() -> None:
    fetched = _now() - timedelta(days=180)
    assert freshness_score(fetched, now=_now()) == pytest.approx(0.5)


def test_score_quarters_after_two_half_lives() -> None:
    fetched = _now() - timedelta(days=360)
    assert freshness_score(fetched, now=_now()) == pytest.approx(0.25)


def test_score_respects_custom_half_life() -> None:
    fetched = _now() - timedelta(days=30)
    half_life = 30.0
    assert freshness_score(fetched, now=_now(), half_life_days=half_life) == pytest.approx(0.5)


def test_invalid_half_life_raises() -> None:
    with pytest.raises(ValueError):
        freshness_score(_now(), now=_now(), half_life_days=0.0)
    with pytest.raises(ValueError):
        freshness_score(_now(), now=_now(), half_life_days=-5.0)


def test_future_timestamp_clamped_to_now() -> None:
    fetched = _now() + timedelta(days=30)
    # Future timestamps should not exceed the maximum score.
    assert freshness_score(fetched, now=_now()) == pytest.approx(1.0)


def test_score_decays_monotonically() -> None:
    scores = [
        freshness_score(_now() - timedelta(days=age), now=_now())
        for age in (0, 30, 90, 180, 365)
    ]
    for older, newer in zip(scores, scores[1:], strict=False):
        assert older > newer


def test_iso_string_timestamp_accepted() -> None:
    fetched = "2026-03-04T00:00:00Z"  # 89 days before _now()
    score = freshness_score(fetched, now=_now())
    expected = math.pow(2.0, -89 / 180)
    assert score == pytest.approx(expected, rel=1e-3)


def test_naive_datetime_treated_as_utc() -> None:
    fetched_naive = datetime(2026, 6, 1)
    score = freshness_score(fetched_naive, now=_now())
    assert score == pytest.approx(1.0)
