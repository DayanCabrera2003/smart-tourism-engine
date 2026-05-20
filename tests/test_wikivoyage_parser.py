"""T1 - Tests for Wikivoyage parser handling of stubs.

The parser must:
1. Return ``None`` for ``#REDIRECT`` pages so they never reach the index.
2. Return ``None`` for disambiguation pages (``{{disambig}}`` template).
3. Return ``None`` when the cleaned description is shorter than the
   minimum useful length (``MIN_DESCRIPTION_CHARS``).
4. Parse normal city pages as before.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.ingestion.wikivoyage import MIN_DESCRIPTION_CHARS, WikivoyageParser


def _write_raw(tmp_path: Path, title: str, content: str) -> Path:
    """Write a Wikivoyage API JSON fixture mimicking the real shape."""
    payload = {
        "query": {
            "pages": [
                {
                    "title": title,
                    "revisions": [{"content": content}],
                }
            ]
        }
    }
    path = tmp_path / f"{title.lower().replace(' ', '_')}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_parse_skips_redirect_page(tmp_path: Path) -> None:
    """A page whose body is `#REDIRECT [[X]]` must yield no destination."""
    path = _write_raw(tmp_path, "Cordoba", "#REDIRECT [[Córdoba]]")
    parser = WikivoyageParser()

    assert parser.parse_file(path) is None


def test_parse_skips_redirect_with_leading_whitespace(tmp_path: Path) -> None:
    """The redirect detection is whitespace-tolerant at the start."""
    path = _write_raw(tmp_path, "Avila", "\n   #REDIRECT [[Ávila]]\n")
    parser = WikivoyageParser()

    assert parser.parse_file(path) is None


def test_parse_skips_redirect_case_insensitive(tmp_path: Path) -> None:
    """`#redirect` lowercase is also a valid MediaWiki redirect marker."""
    path = _write_raw(tmp_path, "Gijon", "#redirect [[Gijón]]")
    parser = WikivoyageParser()

    assert parser.parse_file(path) is None


def test_parse_skips_disambiguation_page(tmp_path: Path) -> None:
    """A page carrying the `{{disambig}}` template must yield no destination."""
    content = (
        "{{pagebanner|Disambiguation banner.png}}\n"
        "There is more than one article by the name '''Cuenca''':\n"
        "\n"
        "*[[Cuenca (Batangas)]] - A town in [[Batangas]], Philippines\n"
        "*[[Cuenca (Ecuador)]] - A city in Ecuador.\n"
        "*[[Cuenca (Spain)]]\n"
        "\n"
        "{{disambig}}\n"
    )
    path = _write_raw(tmp_path, "Cuenca", content)
    parser = WikivoyageParser()

    assert parser.parse_file(path) is None


def test_parse_skips_disambiguation_alt_template(tmp_path: Path) -> None:
    """Disambiguation pages may use alternative template names."""
    content = (
        "There is more than one place called '''Cartagena''':\n"
        "* [[Cartagena (Colombia)]] - A city in Bolívar.\n"
        "{{geodis}}\n"
    )
    path = _write_raw(tmp_path, "Cartagena", content)
    parser = WikivoyageParser()

    assert parser.parse_file(path) is None


def test_parse_skips_disamb_short_template(tmp_path: Path) -> None:
    """Wikivoyage also uses the abbreviated `{{disamb}}` template."""
    # Fixture has > MIN_DESCRIPTION_CHARS of cleaned body so that the
    # only signal left for detection is the {{disamb}} template itself.
    content = (
        "{{pagebanner|Disambiguation banner.png}}\n"
        "__NOTOC__\n"
        "There is more than one place which has '''San José''' as all or "
        "part of its name. San José is the Spanish form of the name. There "
        "are also places that use the English or French form; see Saint "
        "Joseph. You could be looking for:\n"
        "* [[San José (Costa Rica)]] - The capital of Costa Rica, located "
        "in the Central Valley with about 350 000 inhabitants and a "
        "thriving cultural scene.\n"
        "* [[San José del Cabo]] - a town in Baja California Sur, known "
        "for its arts district and quiet beaches near the southern tip of "
        "the Baja peninsula.\n"
        "{{disamb}}\n"
    )
    path = _write_raw(tmp_path, "San Jose", content)
    parser = WikivoyageParser()

    assert parser.parse_file(path) is None


def test_parse_skips_when_description_below_min_length(tmp_path: Path) -> None:
    """Even non-redirect pages must have a usable amount of body text."""
    short_body = "A tiny stub with not much to say. " * 2  # < 200 chars
    assert len(short_body) < MIN_DESCRIPTION_CHARS
    path = _write_raw(tmp_path, "Stubby", short_body)
    parser = WikivoyageParser()

    assert parser.parse_file(path) is None


def test_parse_keeps_normal_destination(tmp_path: Path) -> None:
    """A regular city page is still parsed into a Destination."""
    body = (
        "Madrid is Spain's capital and largest city. It has world-class "
        "museums, lively neighbourhoods, and a vibrant nightlife. "
        "Visitors enjoy Plaza Mayor, the Prado Museum, Retiro Park, "
        "and an extensive metro system that makes day trips easy. "
        "Cuisine ranges from tapas bars to refined restaurants. "
        "{{Geo|40.4168|-3.7038}}\n"
    )
    path = _write_raw(tmp_path, "Madrid", body)
    parser = WikivoyageParser()

    dest = parser.parse_file(path)

    assert dest is not None
    assert dest.name == "Madrid"
    assert dest.id == "wikivoyage-madrid"
    assert len(dest.description) >= MIN_DESCRIPTION_CHARS
    assert dest.coordinates == (40.4168, -3.7038)


def test_min_description_chars_constant_is_reasonable() -> None:
    """Sanity check on the constant exported by the module."""
    assert MIN_DESCRIPTION_CHARS >= 100
    assert MIN_DESCRIPTION_CHARS <= 500


@pytest.mark.parametrize(
    "redirect_target",
    [
        "Málaga",
        "San Sebastián",
        "Las Palmas de Gran Canaria",
        "Almería",
    ],
)
def test_parse_skips_all_known_redirect_stubs(
    tmp_path: Path, redirect_target: str
) -> None:
    """Regression: the historical stubs that polluted the index must drop."""
    path = _write_raw(tmp_path, redirect_target, f"#REDIRECT [[{redirect_target}]]")
    parser = WikivoyageParser()

    assert parser.parse_file(path) is None
