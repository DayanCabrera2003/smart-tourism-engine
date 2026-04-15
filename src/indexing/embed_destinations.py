"""T052 — Genera embeddings de destinos y los sube a Qdrant en batches."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, Protocol

from src.indexing.vector_store import VectorPoint, VectorStore
from src.logging_config import logger

__all__ = ["embed_destinations", "slug_to_uuid", "DEFAULT_COLLECTION"]

DEFAULT_COLLECTION = "destinations_text"
_PAYLOAD_FIELDS = ("name", "country", "region", "tags", "image_urls", "source")
_NAMESPACE = uuid.UUID("6f3c1a1a-7e71-4c6d-9a62-8b5b3e0a0001")


class _Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


def slug_to_uuid(slug: str) -> str:
    """Convierte un slug textual en UUID determinista (Qdrant exige int o UUID)."""
    return str(uuid.uuid5(_NAMESPACE, slug))


def _build_point(doc: dict[str, Any], vector: list[float]) -> VectorPoint:
    slug = doc["id"]
    payload: dict[str, Any] = {"slug": slug}
    for field in _PAYLOAD_FIELDS:
        if field in doc and doc[field] is not None:
            payload[field] = doc[field]
    return (slug_to_uuid(slug), vector, payload)


def embed_destinations(
    source: str | Path,
    store: VectorStore,
    embedder: _Embedder,
    *,
    collection: str = DEFAULT_COLLECTION,
    batch_size: int = 64,
) -> int:
    """
    Lee destinos desde ``source`` (JSONL), genera el embedding de cada uno
    y los sube a ``collection`` en batches de ``batch_size``.

    El texto a embeber es ``"{name}. {description}"`` con acentos (el modelo
    multilingüe aprovecha los diacríticos). El ID del punto es un UUID5
    derivado del ``id`` del destino; el slug original se preserva en el
    payload para que el recuperador pueda devolverlo a la UI.

    Devuelve el número total de puntos enviados.
    """
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f"Archivo de destinos no encontrado: {source}")

    if batch_size <= 0:
        raise ValueError("batch_size debe ser > 0")

    total = 0
    batch: list[VectorPoint] = []

    with source.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            text = f"{doc.get('name', '')}. {doc.get('description', '')}".strip()
            vector = embedder.embed(text)
            batch.append(_build_point(doc, vector))
            if len(batch) >= batch_size:
                total += store.upsert(collection, batch)
                batch = []

    if batch:
        total += store.upsert(collection, batch)

    logger.info("Embeddings subidos a '%s': %d puntos", collection, total)
    return total
