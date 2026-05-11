"""T123 - Theme palettes and CSS injection helpers for the UI.

Streamlit's built-in theming is configured at startup via
``.streamlit/config.toml``. At runtime we cannot switch themes through
the standard API, so this module produces a small CSS snippet that the
app injects with ``st.markdown(..., unsafe_allow_html=True)``. The
snippet overrides the colors of the most visible surfaces (background,
sidebar, cards) so the dark mode looks consistent without us having to
own every Streamlit selector.

The helpers are pure — no Streamlit imports — so they can be unit
tested without booting the runtime.
"""
from __future__ import annotations

__all__ = [
    "DEFAULT_THEME",
    "THEMES",
    "theme_css",
]


DEFAULT_THEME = "light"

THEMES: dict[str, dict[str, str]] = {
    "light": {
        "background": "#ffffff",
        "secondary_background": "#f4f6f8",
        "text": "#1f2933",
        "card_border": "#e1e4e8",
        "primary": "#1f77b4",
    },
    "dark": {
        "background": "#0e1117",
        "secondary_background": "#1c1f26",
        "text": "#f5f6f7",
        "card_border": "#30363d",
        "primary": "#58a6ff",
    },
}


def theme_css(theme: str) -> str:
    """Return a ``<style>`` block tailored for ``theme``.

    Unknown themes fall back to the light palette. The block targets a
    handful of well-known Streamlit selectors:

    - ``.stApp`` for the page background.
    - ``[data-testid="stSidebar"]`` for the sidebar.
    - ``[data-testid="stMarkdownContainer"]`` for body text.
    - ``[data-testid="stExpander"]`` for the section expanders.

    We do not chase every CSS class Streamlit emits; the goal is a
    coherent dark surface, not a pixel-perfect rewrite.
    """
    palette = THEMES.get(theme) or THEMES[DEFAULT_THEME]
    return (
        "<style>\n"
        f".stApp {{ background-color: {palette['background']}; "
        f"color: {palette['text']}; }}\n"
        f"[data-testid=\"stSidebar\"] {{ "
        f"background-color: {palette['secondary_background']}; }}\n"
        f"[data-testid=\"stSidebar\"] * {{ color: {palette['text']}; }}\n"
        f"[data-testid=\"stMarkdownContainer\"] {{ color: {palette['text']}; }}\n"
        f"[data-testid=\"stExpander\"] {{ "
        f"background-color: {palette['secondary_background']}; "
        f"border: 1px solid {palette['card_border']}; }}\n"
        f"div[data-testid=\"stMetricValue\"] {{ color: {palette['primary']}; }}\n"
        "</style>"
    )
