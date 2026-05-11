"""Tests for T123 — UI theme palettes and persistence."""
from __future__ import annotations

import pytest

from src.ui.app import (
    THEME_SESSION_KEY,
    current_theme,
    store_selected_theme,
)
from src.ui.theme import (
    DEFAULT_THEME,
    THEMES,
    theme_css,
)


def test_default_theme_is_light() -> None:
    assert DEFAULT_THEME == "light"


def test_themes_catalog_has_light_and_dark() -> None:
    assert "light" in THEMES
    assert "dark" in THEMES


def test_every_theme_defines_the_same_palette_keys() -> None:
    reference = set(THEMES[DEFAULT_THEME].keys())
    for name, palette in THEMES.items():
        assert set(palette.keys()) == reference, name


def test_theme_css_returns_style_block_for_light() -> None:
    css = theme_css("light")
    assert css.startswith("<style>")
    assert css.rstrip().endswith("</style>")
    assert "#ffffff" in css


def test_theme_css_returns_dark_palette_for_dark() -> None:
    css = theme_css("dark")
    assert "#0e1117" in css
    assert "#f5f6f7" in css


def test_theme_css_falls_back_to_light_for_unknown_name() -> None:
    css = theme_css("does-not-exist")
    # The fallback should match the light palette signature.
    assert "#ffffff" in css


def test_current_theme_returns_default_for_empty_state() -> None:
    assert current_theme({}) == DEFAULT_THEME


def test_current_theme_reads_from_session_state() -> None:
    state = {THEME_SESSION_KEY: "dark"}
    assert current_theme(state) == "dark"


def test_current_theme_falls_back_when_state_has_unknown_value() -> None:
    state = {THEME_SESSION_KEY: "neon"}
    assert current_theme(state) == DEFAULT_THEME


def test_store_selected_theme_persists_value() -> None:
    state: dict = {}
    store_selected_theme(state, "dark")
    assert state[THEME_SESSION_KEY] == "dark"


def test_store_selected_theme_rejects_unknown_value() -> None:
    with pytest.raises(ValueError):
        store_selected_theme({}, "rainbow")


def test_theme_css_targets_sidebar_and_main_surfaces() -> None:
    css = theme_css("dark")
    assert ".stApp" in css
    assert "stSidebar" in css
    assert "stExpander" in css
