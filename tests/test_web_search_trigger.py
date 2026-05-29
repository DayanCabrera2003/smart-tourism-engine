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


def test_should_fallback_by_relevance_triggers_when_relevance_below_threshold():
    from src.web_search.trigger import should_fallback_by_relevance

    hits = [("a", 0.44), ("b", 0.43)]  # coseno alto pero relevancia real baja
    assert should_fallback_by_relevance(
        hits, relevance=0.05, relevance_threshold=0.10
    ) is True


def test_should_fallback_by_relevance_keeps_local_when_relevant():
    from src.web_search.trigger import should_fallback_by_relevance

    hits = [("a", 0.44)]
    assert should_fallback_by_relevance(
        hits, relevance=0.80, relevance_threshold=0.10
    ) is False


def test_should_fallback_by_relevance_degrades_to_cosine_when_no_cross_encoder():
    from src.web_search.trigger import should_fallback_by_relevance

    # Sin relevancia (cross-encoder no disponible) -> usa el gate por coseno.
    low = [("a", 0.20)]
    high = [("a", 0.55)]
    assert should_fallback_by_relevance(
        low, relevance=None, relevance_threshold=0.10, score_threshold=0.30
    ) is True
    assert should_fallback_by_relevance(
        high, relevance=None, relevance_threshold=0.10, score_threshold=0.30
    ) is False


def test_should_fallback_by_relevance_empty_hits_always_triggers():
    from src.web_search.trigger import should_fallback_by_relevance

    assert should_fallback_by_relevance(
        [], relevance=0.9, relevance_threshold=0.10
    ) is True
