"""T9 - Tests for the bilingual surface of preprocess().

``preprocess`` must accept both the short language codes returned by
``detect_language`` (``"es"`` / ``"en"``) and the long Snowball names
(``"spanish"`` / ``"english"``), and produce equivalent stems for each
form. Anything outside that set must raise.
"""
from __future__ import annotations

import pytest

from src.indexing.preprocess import preprocess, snowball_language_for


def test_preprocess_accepts_short_es_code() -> None:
    short = preprocess("ciudades históricas", language="es")
    long = preprocess("ciudades históricas", language="spanish")
    assert short == long
    assert short  # not empty


def test_preprocess_accepts_short_en_code() -> None:
    short = preprocess("historic cities", language="en")
    long = preprocess("historic cities", language="english")
    assert short == long
    assert any(t.startswith("histor") for t in short)


def test_preprocess_default_language_is_spanish() -> None:
    """Preserve legacy default for callers that pass no language."""
    default = preprocess("museos importantes")
    explicit = preprocess("museos importantes", language="es")
    assert default == explicit


@pytest.mark.parametrize(
    "label, expected",
    [
        ("es", "spanish"),
        ("en", "english"),
        ("ES", "spanish"),
        ("Spanish", "spanish"),
        ("ENGLISH", "english"),
    ],
)
def test_snowball_language_for_resolves_valid_labels(label: str, expected: str) -> None:
    assert snowball_language_for(label) == expected


def test_snowball_language_for_rejects_unknown_label() -> None:
    with pytest.raises(ValueError):
        snowball_language_for("french")


def test_preprocess_rejects_unknown_language() -> None:
    with pytest.raises(ValueError):
        preprocess("texto cualquiera", language="portuguese")
