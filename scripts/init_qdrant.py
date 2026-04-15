"""Crea la colección Qdrant `destinations_text` (T051).

Uso:
    python scripts/init_qdrant.py            # crea si no existe
    python scripts/init_qdrant.py --recreate # borra y vuelve a crear
    python scripts/init_qdrant.py --url http://localhost:6333
"""

from __future__ import annotations

import argparse
import logging
import sys
from typing import Optional

from src.indexing.embedder import TextEmbedder
from src.indexing.vector_store import VectorStore

logger = logging.getLogger(__name__)

COLLECTION_NAME = "destinations_text"
VECTOR_SIZE = TextEmbedder.DIMENSION
DISTANCE = "Cosine"


def init(store: VectorStore, *, recreate: bool = False) -> None:
    """Crea (o recrea) la colección de destinos en el ``VectorStore`` dado."""
    store.create_collection(
        COLLECTION_NAME,
        vector_size=VECTOR_SIZE,
        distance=DISTANCE,
        recreate=recreate,
    )
    logger.info(
        "Colección '%s' lista (dim=%d, distance=%s, recreate=%s)",
        COLLECTION_NAME,
        VECTOR_SIZE,
        DISTANCE,
        recreate,
    )


def _parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inicializa la colección Qdrant de destinos.")
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Borra la colección existente antes de crearla.",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="URL de Qdrant (override de settings.QDRANT_URL).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    args = _parse_args(argv)
    store = VectorStore(url=args.url) if args.url else VectorStore()
    init(store, recreate=args.recreate)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
