from __future__ import annotations

from typing import Any, Iterable, Optional

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from src.config import settings

__all__ = ["VectorStore", "VectorPoint", "SearchHit"]


VectorPoint = tuple[str | int, list[float], dict[str, Any]]
SearchHit = tuple[str | int, float, dict[str, Any]]


class VectorStore:
    """
    Envoltorio fino sobre `qdrant-client` para gestionar colecciones de vectores.

    El cliente puede apuntar a una instancia remota (URL HTTP) o, para tests,
    a una instancia en memoria pasando ``url=":memory:"``.
    """

    def __init__(
        self,
        url: Optional[str] = None,
        *,
        api_key: Optional[str] = None,
        client: Optional[QdrantClient] = None,
    ) -> None:
        if client is not None:
            self._client = client
        else:
            target = url if url is not None else settings.QDRANT_URL
            if target == ":memory:":
                self._client = QdrantClient(location=":memory:")
            else:
                self._client = QdrantClient(url=target, api_key=api_key)

    @property
    def client(self) -> QdrantClient:
        return self._client

    def create_collection(
        self,
        name: str,
        *,
        vector_size: int,
        distance: str = "Cosine",
        recreate: bool = False,
    ) -> None:
        """
        Crea (o recrea) una colección con la dimensión y métrica indicadas.

        Si ``recreate`` es False y la colección ya existe, no hace nada.
        """
        distance_enum = qmodels.Distance(distance.capitalize())
        vectors_config = qmodels.VectorParams(size=vector_size, distance=distance_enum)

        if recreate or not self._client.collection_exists(name):
            if recreate and self._client.collection_exists(name):
                self._client.delete_collection(name)
            self._client.create_collection(
                collection_name=name, vectors_config=vectors_config
            )

    def upsert(self, collection: str, points: Iterable[VectorPoint]) -> int:
        """
        Inserta o actualiza una lista de puntos ``(id, vector, payload)``.
        Devuelve el número de puntos enviados.
        """
        batch = [
            qmodels.PointStruct(id=pid, vector=vec, payload=payload)
            for pid, vec, payload in points
        ]
        if not batch:
            return 0
        self._client.upsert(collection_name=collection, points=batch, wait=True)
        return len(batch)

    def list_ids(self, collection: str) -> set[str]:
        """Devuelve el conjunto de IDs (como strings) de todos los puntos de la colección.

        Usa la API ``scroll`` de Qdrant para paginar sobre todos los puntos sin
        cargar los vectores.  Útil para la reindexación incremental (T057).
        """
        if not self._client.collection_exists(collection):
            return set()

        ids: set[str] = set()
        offset = None
        while True:
            results, next_offset = self._client.scroll(
                collection_name=collection,
                scroll_filter=None,
                limit=256,
                offset=offset,
                with_payload=False,
                with_vectors=False,
            )
            for point in results:
                ids.add(str(point.id))
            if next_offset is None:
                break
            offset = next_offset
        return ids

    def search(
        self,
        collection: str,
        query_vector: list[float],
        *,
        top_k: int = 10,
        score_threshold: Optional[float] = None,
    ) -> list[SearchHit]:
        """
        Busca los ``top_k`` vecinos más cercanos. Devuelve tuplas
        ``(id, score, payload)`` ordenadas por score descendente.
        """
        results = self._client.query_points(
            collection_name=collection,
            query=query_vector,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
        ).points
        return [(hit.id, hit.score, hit.payload or {}) for hit in results]
