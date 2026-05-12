"""Tests for T124 — accessibility helpers."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.ui.accessibility import (
    WCAG_AA_NORMAL_THRESHOLD,
    image_alt,
    image_attribution,
    passes_wcag_aa,
    wcag_contrast_ratio,
)
from src.ui.theme import THEMES

# ─── image_alt ────────────────────────────────────────────────────────────


def test_image_alt_combines_name_country_description() -> None:
    alt = image_alt(
        name="Madrid",
        country="España",
        description="Capital y mayor ciudad de España.",
    )
    assert "Madrid" in alt
    assert "España" in alt
    assert "Capital" in alt


def test_image_alt_with_only_name() -> None:
    alt = image_alt(name="Madrid")
    assert alt == "Madrid"


def test_image_alt_uses_fallback_when_everything_is_empty() -> None:
    alt = image_alt(name=None, country=None, description=None)
    assert "destino" in alt.lower()


def test_image_alt_ignores_blank_fields() -> None:
    alt = image_alt(name="   ", country=None, description="Playa")
    assert alt == "Playa"


def test_image_alt_truncates_long_descriptions() -> None:
    desc = "x" * 200
    alt = image_alt(name="Lugar", description=desc)
    assert alt.endswith("...")
    # Truncated at 117 chars + ellipsis, plus "Lugar: " prefix.
    assert len(alt) < 200


# ─── WCAG contrast ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "fg,bg,expected_min",
    [
        ("#ffffff", "#000000", 20.0),  # Maximum contrast: black on white.
        ("#000000", "#ffffff", 20.0),
        ("#ffffff", "#ffffff", 1.0),  # Same color: contrast = 1.0.
    ],
)
def test_wcag_contrast_ratio_canonical(fg: str, bg: str, expected_min: float) -> None:
    ratio = wcag_contrast_ratio(fg, bg)
    if expected_min == 1.0:
        assert ratio == pytest.approx(1.0)
    else:
        assert ratio >= expected_min


def test_wcag_contrast_ratio_handles_short_hex() -> None:
    short = wcag_contrast_ratio("#fff", "#000")
    full = wcag_contrast_ratio("#ffffff", "#000000")
    assert short == pytest.approx(full)


def test_wcag_contrast_ratio_rejects_bad_hex() -> None:
    with pytest.raises(ValueError):
        wcag_contrast_ratio("not-a-color", "#000000")
    with pytest.raises(ValueError):
        wcag_contrast_ratio("#12345", "#000000")  # 5 digits


def test_passes_wcag_aa_returns_true_for_high_contrast() -> None:
    assert passes_wcag_aa("#000000", "#ffffff") is True


def test_passes_wcag_aa_returns_false_for_low_contrast() -> None:
    # White on a light grey is not legible.
    assert passes_wcag_aa("#ffffff", "#e0e0e0") is False


def test_wcag_aa_threshold_is_official_value() -> None:
    assert WCAG_AA_NORMAL_THRESHOLD == 4.5


# ─── Theme palettes pass WCAG AA ─────────────────────────────────────────


def test_light_theme_text_on_background_passes_aa() -> None:
    palette = THEMES["light"]
    assert passes_wcag_aa(palette["text"], palette["background"])


def test_dark_theme_text_on_background_passes_aa() -> None:
    palette = THEMES["dark"]
    assert passes_wcag_aa(palette["text"], palette["background"])


def test_light_theme_text_on_secondary_passes_aa() -> None:
    palette = THEMES["light"]
    assert passes_wcag_aa(palette["text"], palette["secondary_background"])


def test_dark_theme_text_on_secondary_passes_aa() -> None:
    palette = THEMES["dark"]
    assert passes_wcag_aa(palette["text"], palette["secondary_background"])


# ─── image_attribution (T126) ─────────────────────────────────────────────


def test_image_attribution_returns_sidecar_value(tmp_path: Path) -> None:
    image = tmp_path / "wikipedia.jpg"
    image.write_bytes(b"\xff\xd8\xff")
    sidecar = tmp_path / "wikipedia.json"
    sidecar.write_text(
        '{"attribution": "Imagen de Wikipedia (CC BY-SA) — https://en.wikipedia.org/wiki/Madrid"}'
    )
    out = image_attribution(str(image))
    assert out and "Wikipedia" in out
    assert "CC BY-SA" in out


def test_image_attribution_returns_none_when_sidecar_missing(tmp_path: Path) -> None:
    image = tmp_path / "wikipedia.jpg"
    image.write_bytes(b"x")
    # No sidecar written.
    assert image_attribution(str(image)) is None


def test_image_attribution_returns_none_for_empty_input() -> None:
    assert image_attribution("") is None


def test_image_attribution_returns_none_when_sidecar_unreadable(
    tmp_path: Path,
) -> None:
    sidecar = tmp_path / "wikipedia.json"
    sidecar.write_text("not valid json")
    image = tmp_path / "wikipedia.jpg"
    image.write_bytes(b"x")
    assert image_attribution(str(image)) is None


def test_image_attribution_returns_none_when_attribution_missing(
    tmp_path: Path,
) -> None:
    sidecar = tmp_path / "wikipedia.json"
    sidecar.write_text('{"title": "x"}')  # no attribution field
    image = tmp_path / "wikipedia.jpg"
    image.write_bytes(b"x")
    assert image_attribution(str(image)) is None
