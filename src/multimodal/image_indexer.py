"""T083 — Lógica de indexación de imágenes con CLIP en Qdrant.

Recorre ``data/raw/images/{destination_id}/`` y sube un embedding CLIP por
cada imagen, asociando el ``destination_id`` y la ruta como payload.
"""
from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Iterable

from src.indexing.vector_store import VectorStore
from src.multimodal.clip_embedder import ClipEmbedder

logger = logging.getLogger(__name__)

SUPPORTED_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
IMAGE_COLLECTION = "destinations_image"


def _stable_id(destination_id: str, image_path: Path) -> str:
    """Genera un ID UUID v5 estable a partir del destino + ruta de imagen."""
    key = f"{destination_id}:{image_path.name}"
    return str(hashlib.md5(key.encode()).hexdigest())


def _iter_images(images_dir: Path) -> Iterable[tuple[str, Path]]:
    """Genera pares (destination_id, image_path) para todas las imágenes."""
    if not images_dir.exists():
        return
    for dest_dir in sorted(images_dir.iterdir()):
        if not dest_dir.is_dir():
            continue
        destination_id = dest_dir.name
        for img_file in sorted(dest_dir.iterdir()):
            if img_file.suffix.lower() in SUPPORTED_SUFFIXES:
                yield destination_id, img_file


def embed_images(
    images_dir: Path,
    store: VectorStore,
    embedder: ClipEmbedder,
    *,
    collection: str = IMAGE_COLLECTION,
    batch_size: int = 32,
    only_new: bool = False,
) -> int:
    """Indexa imágenes de ``images_dir`` en Qdrant.

    Devuelve el número de imágenes indexadas.
    """
    store.create_collection(collection, vector_size=ClipEmbedder.DIMENSION)

    existing_ids: set[str] = set()
    if only_new:
        existing_ids = store.list_ids(collection)

    batch: list[tuple[str, list[float], dict]] = []
    total = 0

    def _flush():
        nonlocal total
        if batch:
            store.upsert(collection, batch)
            total += len(batch)
            batch.clear()

    for destination_id, img_path in _iter_images(images_dir):
        point_id = _stable_id(destination_id, img_path)
        if only_new and point_id in existing_ids:
            continue
        try:
            vector = embedder.embed_image(img_path)
        except Exception as exc:
            logger.warning("Error al embeber %s: %s", img_path, exc)
            continue
        payload = {
            "destination_id": destination_id,
            "image_path": str(img_path),
        }
        batch.append((point_id, vector, payload))
        if len(batch) >= batch_size:
            _flush()
            logger.info("Indexadas %d imágenes...", total)

    _flush()
    logger.info("Indexación completada: %d imágenes en '%s'", total, collection)
    return total
