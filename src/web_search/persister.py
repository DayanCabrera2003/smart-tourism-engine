"""T077 — Persiste resultados web en SQLite y Qdrant para reutilizacion."""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.indexing.embed_destinations import slug_to_uuid
from src.ingestion.models import Destination
from src.ingestion.store import upsert_destination

if TYPE_CHECKING:
    from src.indexing.embedder import TextEmbedder
    from src.indexing.vector_store import VectorStore

__all__ = ["persist_web_destination"]

logger = logging.getLogger(__name__)


def persist_web_destination(
    dest: Destination,
    *,
    embedder: "TextEmbedder",
    store: "VectorStore",
    collection: str,
) -> None:
    """Guarda destino web en SQLite y sube su embedding a Qdrant.

    Los errores se loguean pero no se propagan para no interrumpir
    el flujo de respuesta al usuario.
    """
    try:
        upsert_destination(dest)
    except Exception:
        logger.warning("No se pudo persistir destino web %s en SQLite", dest.id)

    try:
        vector = embedder.embed(dest.description)
        point_id = slug_to_uuid(dest.id)
        store.upsert(
            collection,
            [
                (
                    point_id,
                    vector,
                    {"slug": dest.id, "name": dest.name, "country": dest.country},
                )
            ],
        )
    except Exception:
        logger.warning("No se pudo indexar destino web %s en Qdrant", dest.id)
