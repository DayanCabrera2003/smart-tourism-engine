"""T074 — Tests del detector de fallback."""
from __future__ import annotations

from src.web_search.trigger import should_fallback

_GOOD_HIT = ("doc-1", 0.85)
_LOW_HIT = ("doc-2", 0.15)


def test_no_fallback_when_scores_high():
    assert should_fallback([_GOOD_HIT, ("doc-3", 0.7)]) is False


def test_fallback_when_all_scores_below_threshold():
    assert should_fallback([_LOW_HIT, ("doc-3", 0.2)]) is True


def test_fallback_when_hits_empty():
    assert should_fallback([]) is True


def test_fallback_when_low_confidence_flag():
    assert should_fallback([_GOOD_HIT], low_confidence=True) is True


def test_no_fallback_high_score_and_no_flag():
    assert should_fallback([_GOOD_HIT], low_confidence=False) is False


def test_custom_threshold_activates():
    assert should_fallback([("doc", 0.5)], threshold=0.6) is True


def test_custom_threshold_no_activates():
    assert should_fallback([("doc", 0.7)], threshold=0.6) is False
