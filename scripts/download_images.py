"""T126 - Download Wikipedia thumbnails for every destination in the corpus.

The script iterates over ``data/processed/destinations.jsonl`` and, for
each destination:

1. Looks up the Wikipedia summary for the destination's ``name``.
2. Downloads the thumbnail (or the original image when
   ``--prefer-original`` is set) to
   ``data/raw/images/<destination_id>/wikipedia.jpg``.
3. Records the license short name and the source page URL in a
   sidecar JSON next to the image so attribution can be surfaced in
   the UI.
4. Rewrites the JSONL in place with the new ``image_urls`` field
   pointing to the local files. The original payload is preserved
   apart from the ``image_urls`` list, which is replaced with the
   list of newly downloaded files (one entry per destination).
5. Updates the SQLite ``destinations`` table with the same list so
   the API can surface the local images in /search responses.

Run::

    python scripts/download_images.py

Or with custom flags::

    python scripts/download_images.py --max 50 --prefer-original
    python scripts/download_images.py --dry-run

Idempotent: re-running skips destinations that already have a
downloaded file. Use ``--force`` to re-download.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from sqlalchemy import update

from src.config import settings
from src.ingestion.store import Session, destinations
from src.ingestion.wikipedia_images import (
    DEFAULT_USER_AGENT,
    WikipediaImageClient,
)

logger = logging.getLogger(__name__)


SIDECAR_FILENAME = "wikipedia.json"
IMAGE_FILENAME = "wikipedia.jpg"


def _images_dir(root: Path, destination_id: str) -> Path:
    return root / destination_id


def _is_already_downloaded(root: Path, destination_id: str) -> bool:
    return (_images_dir(root, destination_id) / IMAGE_FILENAME).exists()


def _build_attribution(
    license_short_name: str | None, page_url: str | None
) -> str | None:
    """Render a human-friendly attribution sentence.

    The Wikipedia REST summary endpoint omits the license field for
    many entries (the image is hosted on Commons but the page itself
    falls back to the global CC BY-SA 4.0 license of Wikipedia). We
    surface 'CC BY-SA' as the default when the license is missing so
    the UI still shows a meaningful credit instead of 'None'.
    """
    if not page_url:
        return None
    license_label = license_short_name or "CC BY-SA"
    return f"Imagen de Wikipedia ({license_label}) — {page_url}"


def _write_sidecar(
    images_dir: Path,
    *,
    title: str,
    page_url: str | None,
    license_short_name: str | None,
    width: int | None,
    height: int | None,
) -> None:
    sidecar = {
        "title": title,
        "source": "wikipedia",
        "page_url": page_url,
        "license": license_short_name,
        "width": width,
        "height": height,
        "attribution": _build_attribution(license_short_name, page_url),
    }
    (images_dir / SIDECAR_FILENAME).write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2)
    )


def _update_jsonl(
    jsonl_path: Path, image_urls_by_id: dict[str, list[str]]
) -> None:
    rewritten: list[dict] = []
    with jsonl_path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            dest_id = record.get("id")
            if dest_id in image_urls_by_id:
                record["image_urls"] = image_urls_by_id[dest_id]
            rewritten.append(record)
    tmp = jsonl_path.with_suffix(jsonl_path.suffix + ".tmp")
    with tmp.open("w") as fh:
        for record in rewritten:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    tmp.replace(jsonl_path)


def _update_sqlite(image_urls_by_id: dict[str, list[str]]) -> int:
    """Sync ``destinations.image_urls`` with the new local paths."""
    updated = 0
    with Session() as session:
        for dest_id, urls in image_urls_by_id.items():
            payload = json.dumps(urls)
            result = session.execute(
                update(destinations)
                .where(destinations.c.id == dest_id)
                .values(image_urls=payload)
            )
            if (result.rowcount or 0) > 0:
                updated += 1
        session.commit()
    return updated


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=settings.DATA_DIR / "processed" / "destinations.jsonl",
    )
    parser.add_argument(
        "--images-root",
        type=Path,
        default=settings.DATA_DIR / "raw" / "images",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=0,
        help="Procesa solo los primeros N destinos (0 = todos).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.2,
        help="Segundos entre llamadas a Wikipedia (default 0.2 = 5 req/s).",
    )
    parser.add_argument(
        "--contact",
        type=str,
        default=None,
        help="Email opcional para el User-Agent.",
    )
    parser.add_argument(
        "--prefer-original",
        action="store_true",
        help="Descarga la imagen completa en vez del thumbnail.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-descarga aunque ya exista la imagen local.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo reporta lo que haría, no toca disco ni DB.",
    )
    parser.add_argument(
        "--language",
        type=str,
        default="en",
        help="Idioma de Wikipedia a consultar (default 'en').",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=settings.LOG_LEVEL, format="%(levelname)s %(message)s")

    records: list[dict] = []
    with args.source.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    if args.max > 0:
        records = records[: args.max]

    logger.info(
        "Procesando %d destinos desde %s", len(records), args.source
    )

    user_agent = DEFAULT_USER_AGENT
    if args.contact:
        from src.ingestion.wikipedia_images import build_user_agent

        user_agent = build_user_agent(args.contact)

    successes = 0
    skipped = 0
    failures: list[str] = []
    image_urls_by_id: dict[str, list[str]] = {}

    with WikipediaImageClient(
        lang=args.language,
        user_agent=user_agent,
        delay_seconds=args.delay,
    ) as client:
        for index, record in enumerate(records, start=1):
            dest_id = record["id"]
            name = record.get("name")
            if not name:
                failures.append(dest_id)
                continue

            if not args.force and _is_already_downloaded(args.images_root, dest_id):
                skipped += 1
                image_path = (
                    _images_dir(args.images_root, dest_id) / IMAGE_FILENAME
                )
                image_urls_by_id[dest_id] = [str(image_path)]
                continue

            info = client.fetch_summary(name)
            if info is None:
                failures.append(dest_id)
                continue
            url = info.best_url(prefer_original=args.prefer_original)
            if not url:
                failures.append(dest_id)
                continue
            target = _images_dir(args.images_root, dest_id) / IMAGE_FILENAME
            if args.dry_run:
                logger.info("[dry-run] %s -> %s", name, url)
                successes += 1
                image_urls_by_id[dest_id] = [str(target)]
                continue
            ok = client.download(url, target)
            if not ok:
                failures.append(dest_id)
                continue
            _write_sidecar(
                target.parent,
                title=info.title,
                page_url=info.page_url,
                license_short_name=info.license_short_name,
                width=info.width,
                height=info.height,
            )
            image_urls_by_id[dest_id] = [str(target)]
            successes += 1

            if index % 20 == 0:
                logger.info(
                    "Progreso: %d/%d (ok=%d, skip=%d, fail=%d)",
                    index,
                    len(records),
                    successes,
                    skipped,
                    len(failures),
                )

    if args.dry_run:
        logger.info(
            "[dry-run] Resumen: %d descargas posibles, %d ya existentes, "
            "%d fallarían/sin imagen",
            successes,
            skipped,
            len(failures),
        )
        return 0

    if image_urls_by_id:
        logger.info("Actualizando JSONL en %s", args.source)
        _update_jsonl(args.source, image_urls_by_id)
        sqlite_updated = _update_sqlite(image_urls_by_id)
        logger.info("SQLite filas actualizadas: %d", sqlite_updated)

    logger.info(
        "Resumen: %d descargadas, %d ya existían, %d sin imagen",
        successes,
        skipped,
        len(failures),
    )
    if failures:
        logger.info("IDs sin imagen: %s", ", ".join(failures[:20]))
    return 0


if __name__ == "__main__":
    sys.exit(_main())
