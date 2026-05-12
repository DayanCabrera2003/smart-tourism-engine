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

    The block also includes lightweight polish for result cards
    (rounded corners, shadow, hover lift) so the default Streamlit
    container looks less raw without writing a full component.
    """
    palette = THEMES.get(theme) or THEMES[DEFAULT_THEME]
    return f"""<style>
.stApp {{
    background-color: {palette["background"]};
    color: {palette["text"]};
}}
[data-testid="stSidebar"] {{
    background-color: {palette["secondary_background"]};
    border-right: 1px solid {palette["card_border"]};
}}
[data-testid="stSidebar"] * {{ color: {palette["text"]}; }}
[data-testid="stMarkdownContainer"] {{ color: {palette["text"]}; }}

[data-testid="stExpander"] {{
    background-color: {palette["secondary_background"]};
    border: 1px solid {palette["card_border"]};
    border-radius: 12px;
}}
div[data-testid="stMetricValue"] {{
    color: {palette["primary"]};
    font-weight: 700;
}}

/* Cards: hover lift + rounded corners */
[data-testid="stVerticalBlockBorderWrapper"] {{
    border-radius: 14px !important;
    border: 1px solid {palette["card_border"]} !important;
    transition: transform 0.12s ease, box-shadow 0.12s ease;
    background: {palette["secondary_background"]} !important;
}}
[data-testid="stVerticalBlockBorderWrapper"]:hover {{
    transform: translateY(-1px);
    box-shadow: 0 4px 14px rgba(0,0,0,0.08);
}}

/* Header title */
h1 {{
    letter-spacing: -0.01em;
    font-weight: 700 !important;
}}

/* Primary buttons */
.stButton button[kind="primary"] {{
    background-color: {palette["primary"]};
    border: 1px solid {palette["primary"]};
    border-radius: 8px;
    font-weight: 600;
}}

/* Captions a bit muted */
[data-testid="stCaptionContainer"] {{ opacity: 0.85; }}

/* Tab labels: more breathing room */
button[data-baseweb="tab"] {{
    font-weight: 600;
    padding: 0.45rem 1rem !important;
}}

/* Tighten image captions */
[data-testid="stImageCaption"] {{
    font-size: 0.78rem !important;
    opacity: 0.7;
}}
</style>"""
