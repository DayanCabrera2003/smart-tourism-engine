"""T058 — Métricas de calidad del índice vectorial Qdrant.

Reporta el estado de la colección ``destinations_text`` (u otra indicada):
- Número de puntos indexados.
- Dimensión del vector.
- Métrica de distancia configurada.
- Tamaño estimado en disco del payload y los vectores.

Uso:

    python scripts/index_metrics.py
    python scripts/index_metrics.py --url http://localhost:6333
    python scripts/index_metrics.py --collection mi_coleccion
"""
from __future__ import annotations

import argparse
import sys

from src.indexing.embed_destinations import DEFAULT_COLLECTION
from src.indexing.vector_store import VectorStore


def collect_metrics(store: VectorStore, collection: str) -> dict:
    """Devuelve un diccionario con las métricas de la colección.

    Lanza ``ValueError`` si la colección no existe.
    """
    if not store.client.collection_exists(collection):
        raise ValueError(f"La colección '{collection}' no existe en Qdrant.")

    info = store.client.get_collection(collection)
    config = info.config
    vectors_config = config.params.vectors

    vector_size = vectors_config.size if hasattr(vectors_config, "size") else None
    distance = str(vectors_config.distance) if hasattr(vectors_config, "distance") else "N/A"

    points_count = info.points_count or 0
    indexed_count = info.indexed_vectors_count or 0

    vectors_size_bytes = points_count * (vector_size or 0) * 4

    return {
        "collection": collection,
        "points_count": points_count,
        "indexed_vectors_count": indexed_count,
        "vector_dimension": vector_size,
        "distance_metric": distance,
        "vectors_size_bytes": vectors_size_bytes,
        "status": str(info.status),
    }


def format_report(metrics: dict) -> str:
    lines = [
        f"Coleccion        : {metrics['collection']}",
        f"Estado           : {metrics['status']}",
        f"Puntos           : {metrics['points_count']:,}",
        f"Vectores indexados: {metrics['indexed_vectors_count']:,}",
        f"Dimension        : {metrics['vector_dimension']}",
        f"Metrica          : {metrics['distance_metric']}",
        f"Tamaño vectores  : {metrics['vectors_size_bytes'] / 1024:.1f} KB",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Métricas del índice vectorial Qdrant (T058).")
    parser.add_argument("--url", default=None, help="URL de Qdrant (default: settings.QDRANT_URL).")
    parser.add_argument(
        "--collection",
        default=DEFAULT_COLLECTION,
        help=f"Nombre de la colección (default: {DEFAULT_COLLECTION}).",
    )
    args = parser.parse_args(argv)

    store = VectorStore(url=args.url) if args.url else VectorStore()

    try:
        metrics = collect_metrics(store, args.collection)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(format_report(metrics))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
