"""T052/T057 — Genera embeddings de destinos y los sube a Qdrant en batches."""
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
    def embed(self, text: str, mode: str = "passage") -> list[float]: ...


def slug_to_uuid(slug: str) -> str:
    """Convierte un slug textual en UUID determinista (Qdrant exige int o UUID)."""
    return str(uuid.uuid5(_NAMESPACE, slug))


def _build_embedding_text(doc: dict[str, Any]) -> str:
    """Compose the text we feed to the embedder for a destination.

    Includes the country (and region when available) so the dense
    retriever can match geographic intents like "playas en cuba" even
    when the body description does not mention the country literally.
    Order matters: name first so the title carries the highest
    weight in BERT-style tokenization, then geo, then body.
    """
    parts: list[str] = []
    name = (doc.get("name") or "").strip()
    if name:
        parts.append(name)
    country = (doc.get("country") or "").strip()
    if country:
        parts.append(country)
    region = (doc.get("region") or "").strip()
    if region:
        parts.append(region)
    description = (doc.get("description") or "").strip()
    if description:
        parts.append(description)
    return ". ".join(parts)


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
    only_new: bool = False,
) -> int:
    """
    Lee destinos desde ``source`` (JSONL), genera el embedding de cada uno
    y los sube a ``collection`` en batches de ``batch_size``.

    El texto a embeber es ``"{name}. {country}. {region}. {description}"``,
    se conservan los acentos para que el embedder multilingüe
    (``multilingual-e5-small``) pueda aprovecharlos. Cada llamada al
    embedder se hace con ``mode="passage"`` para que se aplique el prefijo
    ``"passage: "`` que el modelo requiere. El ID del punto es un UUID5
    derivado del ``id`` del destino; el slug original se preserva en el
    payload para que el recuperador pueda devolverlo a la UI.

    Si ``only_new=True``, consulta los IDs existentes en Qdrant y omite los
    destinos que ya tienen un punto en la colección (reindexación incremental,
    T057).

    Devuelve el número total de puntos enviados (los ya existentes no se cuentan).
    """
    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f"Archivo de destinos no encontrado: {source}")

    if batch_size <= 0:
        raise ValueError("batch_size debe ser > 0")

    existing_ids: set[str] = set()
    if only_new:
        existing_ids = store.list_ids(collection)
        logger.info(
            "Modo incremental: %d IDs ya presentes en '%s'", len(existing_ids), collection
        )

    total = 0
    batch: list[VectorPoint] = []

    with source.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            point_id = slug_to_uuid(doc["id"])
            if only_new and point_id in existing_ids:
                continue
            text = _build_embedding_text(doc)
            # multilingual-e5-small expects documents to be prefixed with
            # "passage: ". The TextEmbedder applies the prefix transparently
            # when mode="passage" is provided.
            vector = embedder.embed(text, mode="passage")
            batch.append(_build_point(doc, vector))
            if len(batch) >= batch_size:
                total += store.upsert(collection, batch)
                batch = []

    if batch:
        total += store.upsert(collection, batch)

    logger.info("Embeddings subidos a '%s': %d puntos", collection, total)
    return total
