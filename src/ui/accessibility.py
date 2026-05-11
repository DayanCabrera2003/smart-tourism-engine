"""T124 - Accessibility helpers for the Streamlit UI.

Two responsibilities live here:

- ``image_alt(...)``: build descriptive alt text for destination
  images. Streamlit renders the value of ``st.image(..., caption=...)``
  inside an ``<img alt>`` attribute, so giving every image a real
  description (rather than ``"image"`` or the empty string) lets
  screen readers announce the destination instead of skipping it.
- WCAG color contrast utilities: compute the contrast ratio between
  two hex colors using the standard relative-luminance formula
  (WCAG 2.1, section 1.4.3) and a convenience ``passes_wcag_aa``
  predicate. The light/dark palettes defined in :mod:`src.ui.theme`
  are validated against this predicate so future palette edits cannot
  silently regress the contrast below the AA threshold.

Everything in this module is a pure function; the Streamlit runtime is
not imported. Tests cover both helpers and the palette contract.
"""
from __future__ import annotations

import re

__all__ = [
    "WCAG_AA_NORMAL_THRESHOLD",
    "image_alt",
    "passes_wcag_aa",
    "wcag_contrast_ratio",
]


WCAG_AA_NORMAL_THRESHOLD = 4.5  # WCAG 2.1 contrast minimum for normal text


def image_alt(
    *,
    name: str | None,
    country: str | None = None,
    description: str | None = None,
    fallback: str = "Imagen del destino turístico",
) -> str:
    """Compose alt text for a destination image.

    Combines the name, the country and a short description into a
    single sentence. Empty fields are skipped so the alt text never
    contains stray separators or trailing commas. The optional
    ``fallback`` is returned when every input is empty so we always
    emit something a screen reader can announce.
    """
    parts: list[str] = []
    if name and name.strip():
        parts.append(name.strip())
    if country and country.strip():
        parts.append(country.strip())
    main = ", ".join(parts)
    if description and description.strip():
        snippet = description.strip()
        if len(snippet) > 120:
            snippet = snippet[:117].rstrip() + "..."
        if main:
            return f"{main}: {snippet}"
        return snippet
    if main:
        return main
    return fallback


# ─── WCAG contrast ────────────────────────────────────────────────────────


_HEX_RE = re.compile(r"^#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")


def _normalize_hex(color: str) -> str:
    match = _HEX_RE.match(color.strip())
    if not match:
        raise ValueError(f"Invalid hex color: {color!r}")
    raw = match.group(1)
    if len(raw) == 3:
        raw = "".join(ch * 2 for ch in raw)
    return raw.lower()


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    raw = _normalize_hex(color)
    return int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)


def _channel_luminance(channel: int) -> float:
    """sRGB to linear conversion per WCAG 2.1."""
    c = channel / 255.0
    if c <= 0.03928:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def _relative_luminance(color: str) -> float:
    r, g, b = _hex_to_rgb(color)
    return (
        0.2126 * _channel_luminance(r)
        + 0.7152 * _channel_luminance(g)
        + 0.0722 * _channel_luminance(b)
    )


def wcag_contrast_ratio(foreground: str, background: str) -> float:
    """Compute the WCAG contrast ratio between two hex colors.

    The result is in the range ``[1.0, 21.0]``. WCAG AA requires at
    least ``4.5`` for normal text and ``3.0`` for large text.
    """
    fg = _relative_luminance(foreground)
    bg = _relative_luminance(background)
    lighter = max(fg, bg)
    darker = min(fg, bg)
    return (lighter + 0.05) / (darker + 0.05)


def passes_wcag_aa(
    foreground: str,
    background: str,
    *,
    threshold: float = WCAG_AA_NORMAL_THRESHOLD,
) -> bool:
    """Return True when the contrast ratio meets WCAG AA for normal text."""
    return wcag_contrast_ratio(foreground, background) >= threshold
