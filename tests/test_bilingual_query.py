"""Tests for the bilingual query expansion helper."""
from __future__ import annotations

import pytest

from src.retrieval.bilingual_query import expand_query


def test_expand_spanish_query_appends_english_terms() -> None:
    out = expand_query("ciudades de Alemania")
    assert "germany" in out.lower()
    assert "cities" in out.lower()
    # Original query content stays.
    assert "ciudades" in out.lower()


def test_expand_english_query_appends_spanish_terms() -> None:
    out = expand_query("German cities")
    # ``german`` matches the reverse map (any es key whose translation
    # is ``german``); the first hit (``alemanas``) is what the reverse
    # dict stores. Either ``alemania`` or ``alemanas`` is acceptable.
    assert "aleman" in out.lower()
    assert "ciudades" in out.lower()


def test_expand_handles_multi_word_phrase() -> None:
    out = expand_query("destinos para vida nocturna")
    assert "nightlife" in out.lower()


def test_expand_handles_accented_input() -> None:
    out = expand_query("destinos en Japón")
    assert "japan" in out.lower()


def test_expand_returns_original_when_no_match() -> None:
    text = "xyzabc qwertyuiop"
    assert expand_query(text) == text


def test_expand_does_not_duplicate_when_translation_already_present() -> None:
    text = "germany Alemania"
    out = expand_query(text)
    # ``germany`` already in input → not appended again.
    # Counting occurrences as words.
    import re
    assert len(re.findall(r"\bgermany\b", out.lower())) == 1


def test_expand_empty_returns_empty() -> None:
    assert expand_query("") == ""
    assert expand_query("   ").strip() == ""


@pytest.mark.parametrize(
    "es, expected",
    [
        ("museos", "museums"),
        ("playas", "beaches"),
        ("regiones vinícolas", "wine"),
        ("destinos coloniales", "colonial"),
        ("ciudades históricas", "historic"),
        ("comida típica", "food"),
        ("luna de miel romántica", "honeymoon"),
    ],
)
def test_expand_covers_tourism_vocabulary(es: str, expected: str) -> None:
    out = expand_query(es).lower()
    assert expected in out
