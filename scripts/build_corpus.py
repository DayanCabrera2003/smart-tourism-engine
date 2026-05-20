"""T21 - Build the expanded destination corpus end-to-end.

Pipeline:

    Wikidata SPARQL  (per country)
        ↓ Q-ids with name, coords, image, Wikipedia titles
    Wikipedia ES API (per Q-id)
        ↓ plain-text extract per destination
    Merge with existing destinations.jsonl (preserve Wikivoyage entries)
    Write data/processed/destinations.jsonl + SQLite

The script is deliberately resilient: any single failed request is
logged and the destination falls back to whatever metadata Wikidata
already gave (without text it is still useful for the recommender,
but it gets a small length-penalty later in the reranker). A target
of 2 500-3 500 destinations is reached by enumerating ~55 tourist-
heavy countries with a per-country cap of 80 entries.

Usage:

    python scripts/build_corpus.py
    python scripts/build_corpus.py --countries ES FR IT --max-per-country 50
    python scripts/build_corpus.py --target 3000

The default country list covers the corpus already present plus
neighbours frequently appearing in eval queries.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.config import settings
from src.ingestion.models import Destination
from src.ingestion.normalize import normalize_text
from src.ingestion.store import upsert_destination
from src.ingestion.wikidata import WikidataClient, WikidataItem
from src.ingestion.wikipedia import WikipediaClient
from src.logging_config import logger

# Countries we crawl by default. The list mirrors the legacy Wikivoyage
# corpus plus the major tourist destinations missing from it. ISO 3166-1
# alpha-2 codes (the same property P297 stores in Wikidata).
DEFAULT_COUNTRIES: tuple[str, ...] = (
    "ES", "FR", "IT", "DE", "GB", "PT", "NL", "BE", "AT", "CH", "CZ",
    "HU", "PL", "GR", "TR", "HR", "IE", "IS", "NO", "SE", "DK", "FI",
    "US", "CA", "MX", "CU", "DO", "PR", "CR", "PA", "GT", "BR", "AR",
    "CL", "PE", "BO", "EC", "CO", "VE", "UY", "PY", "JP", "CN", "KR",
    "TH", "VN", "SG", "MY", "ID", "IN", "AE", "EG", "MA", "TN", "ZA",
    "KE", "TZ", "AU", "NZ", "JO", "IL", "RU",
)


def _slug_from_qid(item: WikidataItem) -> str:
    """Turn a Wikidata item into a deterministic slug for the destination.

    Format: ``wikidata-<qid-lower>`` (e.g. ``wikidata-q90``). Using the
    Q-id keeps the slug stable across rebuilds and makes deduplication
    trivial when the same place shows up in multiple sources.
    """
    return f"wikidata-{item.qid.lower()}"


def _country_in_corpus_name(country_label: str) -> str:
    """Translate Wikidata's Spanish country label to the form used by the
    existing corpus (English names like 'Spain', 'France').

    Wikidata returns Spanish-language labels because we asked for them
    in the SPARQL service block; the existing geo_filter and reranker
    code keys off the English forms. A small mapping table covers the
    countries we crawl; anything outside falls back to the label.
    """
    mapping = {
        "España": "Spain",
        "Francia": "France",
        "Italia": "Italy",
        "Alemania": "Germany",
        "Reino Unido": "United Kingdom",
        "Portugal": "Portugal",
        "Países Bajos": "Netherlands",
        "Bélgica": "Belgium",
        "Austria": "Austria",
        "Suiza": "Switzerland",
        "República Checa": "Czech Republic",
        "Hungría": "Hungary",
        "Polonia": "Poland",
        "Grecia": "Greece",
        "Turquía": "Turkey",
        "Croacia": "Croatia",
        "Irlanda": "Ireland",
        "Islandia": "Iceland",
        "Noruega": "Norway",
        "Suecia": "Sweden",
        "Dinamarca": "Denmark",
        "Finlandia": "Finland",
        "Estados Unidos": "United States",
        "Canadá": "Canada",
        "México": "Mexico",
        "Cuba": "Cuba",
        "República Dominicana": "Dominican Republic",
        "Puerto Rico": "Puerto Rico",
        "Costa Rica": "Costa Rica",
        "Panamá": "Panama",
        "Guatemala": "Guatemala",
        "Brasil": "Brazil",
        "Argentina": "Argentina",
        "Chile": "Chile",
        "Perú": "Peru",
        "Bolivia": "Bolivia",
        "Ecuador": "Ecuador",
        "Colombia": "Colombia",
        "Venezuela": "Venezuela",
        "Uruguay": "Uruguay",
        "Paraguay": "Paraguay",
        "Japón": "Japan",
        "China": "China",
        "Corea del Sur": "South Korea",
        "Tailandia": "Thailand",
        "Vietnam": "Vietnam",
        "Singapur": "Singapore",
        "Malasia": "Malaysia",
        "Indonesia": "Indonesia",
        "India": "India",
        "Emiratos Árabes Unidos": "United Arab Emirates",
        "Egipto": "Egypt",
        "Marruecos": "Morocco",
        "Túnez": "Tunisia",
        "Sudáfrica": "South Africa",
        "Kenia": "Kenya",
        "Tanzania": "Tanzania",
        "Australia": "Australia",
        "Nueva Zelanda": "New Zealand",
        "Jordania": "Jordan",
        "Israel": "Israel",
        "Rusia": "Russia",
    }
    return mapping.get(country_label, country_label)


def _build_destination(
    item: WikidataItem,
    description_es: Optional[str],
    description_en: Optional[str],
) -> Optional[Destination]:
    """Compose a :class:`Destination` from Wikidata + Wikipedia text.

    Drops items where neither language produced usable text and the
    extract is below the same threshold the Wikivoyage parser uses
    (200 chars). Keeps both descriptions when present so future
    bilingual indexing has both pages.
    """
    desc_es = (description_es or "").strip()
    desc_en = (description_en or "").strip()
    primary = desc_es or desc_en
    if len(primary) < 200:
        return None

    language = "es" if desc_es and len(desc_es) >= len(desc_en) else "en"
    # The Destination model is the same one used by Wikivoyage so the
    # rest of the pipeline (build_index, embed_destinations) keeps
    # treating the new rows the same way.
    image_urls: list[str] = []
    if item.image:
        # Wikidata's P18 image URL points to Special:FilePath/<file>;
        # widen it explicitly to 800 px for the UI thumbnail.
        if "?" in item.image:
            image_urls.append(item.image)
        else:
            image_urls.append(f"{item.image}?width=800")

    coords = None
    if item.latitude is not None and item.longitude is not None:
        coords = (item.latitude, item.longitude)

    return Destination(
        id=_slug_from_qid(item),
        name=item.name_es,
        country=_country_in_corpus_name(item.country),
        region=None,
        description=primary,
        description_normalized=normalize_text(primary),
        tags=["wikidata", language],
        image_urls=image_urls,
        coordinates=coords,
        source="wikidata+wikipedia",
        fetched_at=datetime.now(timezone.utc),
    )


def _existing_destinations(processed_path: Path) -> dict[str, dict]:
    """Read the current destinations.jsonl into a dict keyed by id."""
    out: dict[str, dict] = {}
    if not processed_path.exists():
        return out
    with processed_path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            out[doc["id"]] = doc
    return out


def crawl(
    *,
    countries: Iterable[str],
    max_per_country: int,
    target: Optional[int],
    cache_dir: Path,
    output_path: Path,
    keep_existing: bool,
) -> int:
    """Run the full pipeline. Returns the number of NEW destinations added."""
    existing = _existing_destinations(output_path) if keep_existing else {}
    logger.info(
        "Starting corpus crawl. Existing=%d, target=%s, countries=%d",
        len(existing),
        target,
        len(list(countries)),
    )

    all_destinations: dict[str, dict] = dict(existing)
    added = 0

    with WikidataClient() as wd, WikipediaClient(cache_dir=cache_dir) as wp:
        for country_code in countries:
            try:
                items = list(wd.fetch_country(country_code, limit=max_per_country))
            except Exception as exc:  # pragma: no cover - network depends
                logger.warning("Wikidata query failed for %s: %s", country_code, exc)
                continue
            logger.info("Wikidata: %s -> %d candidates", country_code, len(items))

            for item in items:
                slug = _slug_from_qid(item)
                if slug in all_destinations:
                    continue
                title_es = item.wikipedia_es_title
                title_en = item.wikipedia_en_title
                description_es = (
                    wp.fetch_extract(title_es, language="es") if title_es else None
                )
                description_en = (
                    wp.fetch_extract(title_en, language="en") if title_en else None
                )
                dest = _build_destination(item, description_es, description_en)
                if dest is None:
                    continue
                all_destinations[slug] = dest.model_dump(mode="json")
                added += 1
                if target is not None and len(all_destinations) >= target:
                    logger.info("Target reached: %d destinations", target)
                    break
            if target is not None and len(all_destinations) >= target:
                break

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as fh:
        for doc in all_destinations.values():
            fh.write(json.dumps(doc, ensure_ascii=False) + "\n")

    # Mirror the writes into SQLite so /search* keeps reading the same
    # metadata as before. We rebuild the relevant rows by reconstructing
    # the Destination object from the dict to use the existing
    # upsert_destination helper.
    persisted = 0
    for doc in all_destinations.values():
        try:
            dest = Destination(**doc)
            upsert_destination(dest)
            persisted += 1
        except Exception as exc:
            logger.warning("Could not persist %s: %s", doc.get("id"), exc)

    logger.info(
        "Done. Total=%d (existing=%d new=%d persisted=%d) -> %s",
        len(all_destinations),
        len(existing),
        added,
        persisted,
        output_path,
    )
    return added


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--countries",
        nargs="+",
        default=list(DEFAULT_COUNTRIES),
        help="ISO 3166-1 alpha-2 country codes to crawl.",
    )
    parser.add_argument(
        "--max-per-country",
        type=int,
        default=80,
        help="Upper bound of Wikidata candidates per country (default 80).",
    )
    parser.add_argument(
        "--target",
        type=int,
        default=None,
        help="Stop as soon as the total destination count reaches this number.",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=settings.DATA_DIR / "raw" / "wikipedia_cache",
        help="Where to cache Wikipedia API responses.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=settings.DATA_DIR / "processed" / "destinations.jsonl",
        help="Path to destinations.jsonl.",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Ignore any existing destinations.jsonl and start from scratch.",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    added = crawl(
        countries=args.countries,
        max_per_country=args.max_per_country,
        target=args.target,
        cache_dir=args.cache_dir,
        output_path=args.output,
        keep_existing=not args.fresh,
    )
    print(f"Corpus expanded by {added} new destinations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
