"""Bootstrap pipeline that turns an empty system into a queryable one.

The pipeline runs the same steps a developer would run by hand
(crawl + ingest + index + embed) but exposes per-phase progress to the
UI via a :class:`BootstrapTracker`.

The crawl phase is skipped automatically when ``data/raw/wikivoyage/``
already contains downloaded pages. This lets the local developer run
"reset indexes" and re-bootstrap in a few minutes without re-hitting
Wikivoyage, while a fresh clone (no raw) still bootstraps end to end.
"""
from __future__ import annotations

import json
import threading
import time
import traceback
from collections.abc import Callable
from pathlib import Path

import httpx

from src.bootstrap.state import BootstrapTracker, PhaseInfo
from src.config import settings
from src.indexing.embed_destinations import DEFAULT_COLLECTION as TEXT_COLLECTION
from src.indexing.embedder import TextEmbedder
from src.indexing.vector_store import VectorStore
from src.ingestion.pipeline import ingest_wikivoyage
from src.multimodal.image_indexer import IMAGE_COLLECTION

_EMBED_DIM = 384  # multilingual-e5-small
_CLIP_DIM = 512   # clip-ViT-B-32
_DEFAULT_PHASES: list[PhaseInfo] = [
    PhaseInfo("detect", "Detectar datos existentes"),
    PhaseInfo("crawl", "Descargar corpus de Wikivoyage"),
    PhaseInfo("ingest", "Procesar y normalizar destinos"),
    PhaseInfo("sqlite", "Sincronizar catalogo SQLite"),
    PhaseInfo("index", "Construir indice invertido"),
    PhaseInfo("popularity", "Calcular popularidad"),
    PhaseInfo("qdrant", "Inicializar coleccion Qdrant"),
    PhaseInfo("embed", "Generar embeddings y subir a Qdrant"),
    PhaseInfo("embed_images", "Indexar imagenes con CLIP"),
]


def _raw_dir() -> Path:
    return settings.DATA_DIR / "raw" / "wikivoyage"


def _processed_dir() -> Path:
    return settings.DATA_DIR / "processed"


def _has_raw_pages() -> bool:
    raw = _raw_dir()
    if not raw.exists():
        return False
    return any(p.name != "country_map.json" for p in raw.glob("*.json"))


def is_bootstrap_needed() -> tuple[bool, list[str]]:
    """Tell whether the system needs a bootstrap before serving queries.

    A system is considered ready when both the inverted index and the
    Qdrant text collection have content. Anything else (missing JSONL,
    missing index, empty collection) flips the flag.
    """
    reasons: list[str] = []
    jsonl = _processed_dir() / "destinations.jsonl"
    if not jsonl.exists():
        reasons.append("destinations.jsonl missing")
    index = _processed_dir() / "index.pkl"
    if not index.exists():
        reasons.append("index.pkl missing")
    try:
        store = VectorStore()
        if not store.client.collection_exists(TEXT_COLLECTION):
            reasons.append(f"qdrant collection '{TEXT_COLLECTION}' missing")
        else:
            count = store.client.count(TEXT_COLLECTION, exact=True).count
            if count == 0:
                reasons.append(f"qdrant collection '{TEXT_COLLECTION}' empty")
    except Exception as exc:
        reasons.append(f"qdrant unreachable: {exc}")
    return (len(reasons) > 0, reasons)


def _crawl_wikivoyage(tracker: BootstrapTracker) -> None:
    """Download Wikivoyage seed pages, reporting per-page progress."""
    from scripts.download_wikivoyage import (
        COUNTRY_MAP,
        INITIAL_DESTINATIONS,
        REQUEST_DELAY_SECONDS,
        USER_AGENT,
        WIKIVOYAGE_API_URL,
    )

    raw = _raw_dir()
    raw.mkdir(parents=True, exist_ok=True)
    total = len(INITIAL_DESTINATIONS)
    downloaded = 0
    failed = 0

    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30.0) as client:
        for idx, page_title in enumerate(INITIAL_DESTINATIONS, start=1):
            tracker.update_message(f"{idx}/{total}: {page_title}")
            params = {
                "action": "query",
                "format": "json",
                "titles": page_title,
                "prop": "revisions",
                "rvprop": "content",
                "formatversion": "2",
            }
            try:
                response = client.get(WIKIVOYAGE_API_URL, params=params)
                response.raise_for_status()
                data = response.json()
                file_path = raw / f"{page_title.lower().replace(' ', '_')}.json"
                with file_path.open("w", encoding="utf-8") as fh:
                    json.dump(data, fh, ensure_ascii=False, indent=2)
                downloaded += 1
            except Exception as exc:  # network errors are non-fatal per page
                failed += 1
                tracker.update_message(f"{idx}/{total} failed ({page_title}): {exc}")
            time.sleep(REQUEST_DELAY_SECONDS)

    with (raw / "country_map.json").open("w", encoding="utf-8") as fh:
        json.dump(COUNTRY_MAP, fh, ensure_ascii=False, indent=2)
    tracker.update_message(
        f"downloaded={downloaded}, failed={failed}, total={total}"
    )


def _ingest(tracker: BootstrapTracker) -> int:
    """Parse raw JSON into destinations.jsonl + SQLite."""
    raw = _raw_dir()
    processed = _processed_dir() / "destinations.jsonl"
    processed.parent.mkdir(parents=True, exist_ok=True)
    tracker.update_message("Parsing raw Wikivoyage pages")
    results = ingest_wikivoyage(raw, processed)
    count = len(results) if results else 0
    tracker.update_message(f"{count} destinations ingested")
    return count


def _sync_sqlite_from_jsonl(tracker: BootstrapTracker) -> int:
    """Re-upsert every destination from JSONL into the SQLite catalog.

    The ingest phase already populates SQLite during a fresh crawl, but
    when the JSONL exists and the parse step is skipped the SQLite can
    drift out of sync (e.g. wiped by hand, never populated). This step
    is idempotent: upserts only touch rows already present and insert
    the rest, so it is safe to run unconditionally.
    """
    from src.ingestion.models import Destination
    from src.ingestion.store import upsert_destination

    source = _processed_dir() / "destinations.jsonl"
    if not source.exists():
        return 0
    count = 0
    with source.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            try:
                upsert_destination(Destination.model_validate(doc))
                count += 1
            except Exception as exc:
                tracker.update_message(
                    f"skip {doc.get('id', '?')}: {type(exc).__name__}: {exc}"
                )
            if count % 100 == 0:
                tracker.update_message(f"SQLite sync: {count} rows upserted")
    tracker.update_message(f"SQLite synced ({count} rows)")
    return count


def _build_index(tracker: BootstrapTracker) -> int:
    from src.indexing.build_index import build_index

    source = _processed_dir() / "destinations.jsonl"
    output = _processed_dir() / "index.pkl"
    tracker.update_message("Building inverted index")
    count = build_index(source, output)
    tracker.update_message(f"index.pkl built ({count} docs)")
    return count


def _compute_popularity(tracker: BootstrapTracker) -> None:
    from scripts.compute_popularity import recompute_popularity

    source = _processed_dir() / "destinations.jsonl"
    tracker.update_message("Computing popularity scores")
    count = recompute_popularity(source)
    tracker.update_message(f"Popularity recomputed for {count} destinations")


def _init_qdrant(tracker: BootstrapTracker, store: VectorStore) -> None:
    tracker.update_message(f"Ensuring collection '{TEXT_COLLECTION}' exists")
    store.create_collection(TEXT_COLLECTION, vector_size=_EMBED_DIM)
    tracker.update_message("Collection ready")


def _embed_text(tracker: BootstrapTracker, store: VectorStore) -> int:
    """Embed JSONL rows in batches, reporting per-batch progress."""
    from src.indexing.embed_destinations import (
        _build_embedding_text,
        _build_point,
    )

    source = _processed_dir() / "destinations.jsonl"
    embedder = TextEmbedder()

    rows = [
        json.loads(line)
        for line in source.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    total = len(rows)
    if total == 0:
        tracker.update_message("destinations.jsonl is empty; nothing to embed")
        return 0

    batch_size = 32
    sent = 0
    batch = []
    for idx, doc in enumerate(rows, start=1):
        text = _build_embedding_text(doc)
        vector = embedder.embed(text, mode="passage")
        batch.append(_build_point(doc, vector))
        if len(batch) >= batch_size:
            sent += store.upsert(TEXT_COLLECTION, batch)
            batch = []
            tracker.update_message(f"{idx}/{total} embedded")
    if batch:
        sent += store.upsert(TEXT_COLLECTION, batch)
    tracker.update_message(f"{sent} points uploaded to '{TEXT_COLLECTION}'")
    return sent


def _embed_images_phase(tracker: BootstrapTracker, store: VectorStore) -> None:
    """Crea la colección CLIP y sube embeddings de todas las imágenes disponibles.

    Si no hay imágenes en data/raw/images/, la fase se salta sin error.
    """
    from src.multimodal.clip_embedder import ClipEmbedder
    from src.multimodal.image_indexer import embed_images

    images_dir = settings.DATA_DIR / "raw" / "images"
    if not images_dir.exists() or not any(
        f for d in images_dir.iterdir() if d.is_dir()
        for f in d.iterdir() if f.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}
    ):
        tracker.update_message("Sin imagenes en data/raw/images/; fase omitida")
        return

    tracker.update_message("Creando coleccion destinations_image")
    store.create_collection(IMAGE_COLLECTION, vector_size=_CLIP_DIM)
    tracker.update_message("Cargando modelo CLIP")
    embedder = ClipEmbedder()
    tracker.update_message("Indexando imagenes con CLIP")
    count = embed_images(images_dir, store, embedder)
    tracker.update_message(f"{count} imagenes indexadas en '{IMAGE_COLLECTION}'")


def run(tracker: BootstrapTracker, *, on_done: Callable[[], None] | None = None) -> None:
    """Run the bootstrap pipeline, updating ``tracker`` as it progresses.

    Designed to be called from a worker thread. Catches any exception
    and stores it in the tracker so the UI can surface it.
    """
    tracker.begin_run(_DEFAULT_PHASES)
    store = VectorStore()
    try:
        tracker.advance("Checking what is already on disk")
        already_has_raw = _has_raw_pages()
        already_has_jsonl = (_processed_dir() / "destinations.jsonl").exists()
        if already_has_jsonl:
            tracker.update_message("destinations.jsonl present; skipping crawl + ingest")
        elif already_has_raw:
            tracker.update_message("Raw pages present; skipping crawl, will ingest")
        else:
            tracker.update_message("Nothing on disk; full bootstrap")

        tracker.advance()
        if already_has_jsonl or already_has_raw:
            tracker.update_message("Skipped (raw already present)")
        else:
            _crawl_wikivoyage(tracker)

        tracker.advance()
        if already_has_jsonl:
            tracker.update_message("Skipped (destinations.jsonl already present)")
        else:
            _ingest(tracker)

        tracker.advance()
        _sync_sqlite_from_jsonl(tracker)

        tracker.advance()
        _build_index(tracker)

        tracker.advance()
        _compute_popularity(tracker)

        tracker.advance()
        _init_qdrant(tracker, store)

        tracker.advance()
        _embed_text(tracker, store)

        tracker.advance()
        _embed_images_phase(tracker, store)

        tracker.finish()
    except Exception as exc:
        tracker.fail(f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")
    finally:
        if on_done is not None:
            try:
                on_done()
            except Exception:
                pass


def run_in_thread(
    tracker: BootstrapTracker, *, on_done: Callable[[], None] | None = None
) -> threading.Thread:
    """Spawn a daemon thread that runs :func:`run`.

    Returns the thread so the caller can join it in tests; production
    callers fire-and-forget.
    """
    thread = threading.Thread(
        target=run, kwargs={"tracker": tracker, "on_done": on_done}, daemon=True
    )
    thread.start()
    return thread
