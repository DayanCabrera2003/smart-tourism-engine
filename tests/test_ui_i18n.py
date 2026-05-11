"""Tests for T116 — i18n helper and locale persistence."""
from __future__ import annotations

import pytest

from src.ui.app import (
    LOCALE_SESSION_KEY,
    current_locale,
    store_selected_locale,
)
from src.ui.i18n import (
    DEFAULT_LOCALE,
    LOCALES,
    TRANSLATIONS,
    t,
)


def test_default_locale_is_spanish() -> None:
    assert DEFAULT_LOCALE == "es"


def test_locales_includes_es_and_en() -> None:
    assert "es" in LOCALES
    assert "en" in LOCALES


def test_translation_returns_spanish_by_default() -> None:
    assert t("app_title") == TRANSLATIONS["es"]["app_title"]


def test_translation_returns_english_when_locale_set() -> None:
    assert t("tab_search", "en") == "Search destinations"


def test_translation_falls_back_to_spanish_for_unknown_locale() -> None:
    spanish_value = TRANSLATIONS["es"]["tab_search"]
    assert t("tab_search", "pt") == spanish_value


def test_translation_returns_key_when_not_in_catalog() -> None:
    # Missing keys must not raise; surfacing the raw key keeps the UI
    # visible while flagging the missing translation.
    assert t("definitely_not_a_key") == "definitely_not_a_key"


def test_every_key_is_present_in_every_locale() -> None:
    keys_es = set(TRANSLATIONS["es"].keys())
    keys_en = set(TRANSLATIONS["en"].keys())
    missing_in_en = keys_es - keys_en
    missing_in_es = keys_en - keys_es
    assert not missing_in_en, f"keys missing in English: {missing_in_en}"
    assert not missing_in_es, f"keys missing in Spanish: {missing_in_es}"


def test_current_locale_returns_default_for_empty_state() -> None:
    assert current_locale({}) == DEFAULT_LOCALE


def test_current_locale_reads_from_session_state() -> None:
    state = {LOCALE_SESSION_KEY: "en"}
    assert current_locale(state) == "en"


def test_current_locale_falls_back_when_state_has_invalid_value() -> None:
    state = {LOCALE_SESSION_KEY: "xx"}
    assert current_locale(state) == DEFAULT_LOCALE


def test_store_selected_locale_persists_value() -> None:
    state: dict = {}
    store_selected_locale(state, "en")
    assert state[LOCALE_SESSION_KEY] == "en"


def test_store_selected_locale_rejects_unknown_locale() -> None:
    with pytest.raises(ValueError):
        store_selected_locale({}, "fr")
