"""Reset operations used by the bootstrap UI to wipe data before reindexing.

Two scopes are supported:

* :func:`reset_indexes`  drops the Qdrant collections and the local
  inverted index (``index.pkl``). The raw corpus, the JSONL and the
  SQLite catalog stay, so the next bootstrap can rebuild everything in
  a couple of minutes without touching the network.
* :func:`reset_all`  does the same plus removes ``data/raw/*``,
  ``data/processed/*`` and the SQLite database, forcing the next
  bootstrap to crawl from scratch.

The functions never touch ``qdrant_storage/`` on the host filesystem:
that directory is owned by Qdrant (root in its own container) and the
right way to drop data is the HTTP API, which both reclaims storage and
keeps Qdrant's internal state consistent.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from src.config import settings
from src.indexing.embed_destinations import DEFAULT_COLLECTION as TEXT_COLLECTION
from src.indexing.vector_store import VectorStore
from src.multimodal.image_indexer import IMAGE_COLLECTION

_INDEX_FILE = "index.pkl"
_JSONL_FILE = "destinations.jsonl"
_SQLITE_FILE = "destinations.db"


@dataclass
class ResetReport:
    """What the reset actually did, so the UI can surface a clear summary."""

    collections_dropped: list[str]
    files_removed: list[str]
    directories_emptied: list[str]


def _drop_collections(store: VectorStore, names: list[str]) -> list[str]:
    dropped: list[str] = []
    for name in names:
        try:
            if store.client.collection_exists(name):
                store.client.delete_collection(name)
                dropped.append(name)
        except Exception:
            # The collection might have been removed by a concurrent
            # reset or Qdrant might be temporarily unreachable. Either
            # way, surface the rest of the work; the caller can re-run.
            continue
    return dropped


def _remove_file(path: Path, report: list[str]) -> None:
    if path.exists():
        path.unlink()
        report.append(str(path))


def _empty_directory(path: Path, report: list[str]) -> None:
    """Remove all entries inside ``path`` but keep the directory itself.

    Keeping the parent directory matters because it is bind-mounted from
    the host: removing it would detach the mount inside the container.
    """
    if not path.exists():
        return
    for child in path.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()
    report.append(str(path))


def reset_indexes(store: VectorStore | None = None) -> ResetReport:
    """Drop both Qdrant collections and ``index.pkl``.

    Leaves the raw corpus and the JSONL/SQLite catalog untouched. The
    next bootstrap will rebuild the index and re-upload embeddings from
    the existing JSONL.
    """
    store = store or VectorStore()
    processed = settings.DATA_DIR / "processed"

    collections = _drop_collections(store, [TEXT_COLLECTION, IMAGE_COLLECTION])
    files: list[str] = []
    _remove_file(processed / _INDEX_FILE, files)

    return ResetReport(
        collections_dropped=collections,
        files_removed=files,
        directories_emptied=[],
    )


def reset_all(store: VectorStore | None = None) -> ResetReport:
    """Wipe everything the bootstrap can rebuild.

    Removes Qdrant collections, the inverted index, the JSONL, the
    SQLite database and the contents of ``data/raw/``. The next
    bootstrap is forced to crawl from scratch.
    """
    store = store or VectorStore()
    processed = settings.DATA_DIR / "processed"
    raw = settings.DATA_DIR / "raw"

    collections = _drop_collections(store, [TEXT_COLLECTION, IMAGE_COLLECTION])

    files: list[str] = []
    _remove_file(processed / _INDEX_FILE, files)
    _remove_file(processed / _JSONL_FILE, files)
    _remove_file(processed / _SQLITE_FILE, files)

    directories: list[str] = []
    _empty_directory(raw, directories)

    return ResetReport(
        collections_dropped=collections,
        files_removed=files,
        directories_emptied=directories,
    )
