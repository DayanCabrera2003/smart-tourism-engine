"""T099 - Recompute popularity scores over the existing corpus.

Reads ``data/processed/destinations.jsonl``, computes the popularity
score with ``compute_popularity_scores`` and writes back to both the
JSONL and the SQLite ``destinations`` table.

The script is idempotent: running it twice on the same corpus produces
the same scores. Re-run after any ingestion that adds or removes
destinations so the popularity remains comparable across the corpus.
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
from src.retrieval.popularity import compute_popularity_scores

logger = logging.getLogger(__name__)


def recompute_popularity(jsonl_path: Path) -> int:
    """Compute popularity for every destination in ``jsonl_path``.

    The JSONL is rewritten in place with the new ``popularity`` field.
    Each destination's ``popularity`` column in SQLite is updated only
    when the row exists; rows missing from SQLite are skipped (they
    will get the right popularity the next time the ingestion pipeline
    upserts them).

    Returns the number of destinations processed.
    """
    if not jsonl_path.exists():
        raise FileNotFoundError(f"JSONL not found: {jsonl_path}")

    records: list[dict] = []
    with jsonl_path.open() as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    scores = compute_popularity_scores(records)

    for record in records:
        record["popularity"] = scores[record["id"]]

    tmp_path = jsonl_path.with_suffix(jsonl_path.suffix + ".tmp")
    with tmp_path.open("w") as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    tmp_path.replace(jsonl_path)

    with Session() as session:
        for record in records:
            session.execute(
                update(destinations)
                .where(destinations.c.id == record["id"])
                .values(popularity=record["popularity"])
            )
        session.commit()

    return len(records)


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=settings.DATA_DIR / "processed" / "destinations.jsonl",
        help="Path to the destinations JSONL (default: data/processed/destinations.jsonl).",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=settings.LOG_LEVEL, format="%(levelname)s %(message)s")
    count = recompute_popularity(args.source)
    logger.info("Updated popularity for %d destinations in %s", count, args.source)
    return 0


if __name__ == "__main__":
    sys.exit(_main())
