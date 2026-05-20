"""T3 - Tests for the bilingual language detector.

The detector underpins query-time and index-time decisions about which
Snowball stemmer to use. It must:

- Return ``"es"`` for Spanish text and ``"en"`` for English text.
- Return ``"en"`` for empty / whitespace input as a safe default
  (the corpus is currently English-heavy).
- Be deterministic for the same input.
- Restrict itself to {Spanish, English} so other languages still get
  mapped to one of the two supported branches.
"""
from __future__ import annotations

import pytest

from src.indexing.language import detect_language


@pytest.mark.parametrize(
    "text",
    [
        "ciudad histórica con playas tropicales",
        "destinos romanticos en Europa",
        "museos y galerías de arte en Madrid",
        "comida callejera asiática",
        "esquí en los Alpes franceses",
        "una pequeña aldea pesquera en la costa norte",
    ],
)
def test_detect_spanish_returns_es(text: str) -> None:
    assert detect_language(text) == "es"


@pytest.mark.parametrize(
    "text",
    [
        "historic city with tropical beaches",
        "best wine regions in France",
        "modern art museums in Paris",
        "street food in Asia",
        "skiing in the French Alps",
        "a small fishing village on the northern coast",
    ],
)
def test_detect_english_returns_en(text: str) -> None:
    assert detect_language(text) == "en"


def test_detect_empty_defaults_to_en() -> None:
    assert detect_language("") == "en"
    assert detect_language("   ") == "en"


def test_detect_is_deterministic() -> None:
    text = "ciudad histórica con encanto"
    a = detect_language(text)
    b = detect_language(text)
    assert a == b == "es"


def test_detect_single_word_falls_back_safely() -> None:
    # One-word inputs are ambiguous; the detector must still return a
    # value in the supported set without crashing.
    assert detect_language("Madrid") in {"es", "en"}
    assert detect_language("museum") in {"es", "en"}


def test_detect_only_returns_supported_languages() -> None:
    # Text in a third language must still map to one of the two
    # supported labels (the builder is restricted to es/en).
    portuguese = "uma pequena vila costeira ao norte do país"
    french = "une petite ville historique au bord de la mer"
    for sample in (portuguese, french):
        assert detect_language(sample) in {"es", "en"}
