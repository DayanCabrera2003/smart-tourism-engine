"""T3 - Bilingual language detection for query/document preprocessing.

The Smart Tourism Engine receives queries mostly in Spanish but indexes
documents authored in both Spanish (Wikipedia ES, Wikivoyage ES) and
English (Wikivoyage EN). Each branch needs its own Snowball stemmer to
yield matching stems. This module wraps Lingua restricted to the two
supported languages so the rest of the code can stay agnostic to the
detector implementation.

Lingua was preferred over ``langdetect`` because it is more accurate on
short text (queries are often 2-5 words) and its v2 release uses Rust
under the hood for fast, deterministic detection without any external
network call.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

__all__ = ["detect_language", "Language"]

Language = Literal["es", "en"]

# Default returned for empty or whitespace-only input. We pick English
# because the legacy corpus is English-heavy and the lexical index was
# originally built with the English Snowball stemmer; falling back to
# English keeps existing tokens reachable.
_DEFAULT: Language = "en"


@lru_cache(maxsize=1)
def _detector():
    """Build the Lingua detector lazily so importing the module is cheap.

    Lingua loads language models on first use; restricting the set to
    Spanish + English keeps the memory footprint small and biases the
    decision to one of the two supported branches even when the input
    is actually in a third language (Portuguese, French, etc.).
    """
    from lingua import Language as LinguaLanguage
    from lingua import LanguageDetectorBuilder

    # High-accuracy mode is the default and the right trade-off here:
    # we only have two languages to discriminate, queries are short and
    # the cost of a misdetection (wrong stemmer) is real. Low-accuracy
    # mode mislabelled short Spanish queries as English during testing.
    return LanguageDetectorBuilder.from_languages(
        LinguaLanguage.SPANISH, LinguaLanguage.ENGLISH
    ).build()


def detect_language(text: str) -> Language:
    """Return ``"es"`` for Spanish-looking input, ``"en"`` otherwise.

    Empty, whitespace-only, or otherwise unresolvable input yields
    :data:`_DEFAULT` so callers can pass the result straight to a
    stemmer without handling ``None``.
    """
    if not text or not text.strip():
        return _DEFAULT

    detected = _detector().detect_language_of(text)
    if detected is None:
        return _DEFAULT
    # Lingua's enum is Rust-backed and does not honour `is` identity
    # checks across imports, so compare by symbolic name instead.
    name = detected.name
    if name == "SPANISH":
        return "es"
    if name == "ENGLISH":
        return "en"
    return _DEFAULT
