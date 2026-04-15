"""T054 — Recuperador híbrido: Booleano Extendido + semántico.

Combina el ranking léxico del Booleano Extendido (p-norm) con el ranking
semántico (coseno sobre embeddings en Qdrant) mediante una mezcla lineal
convexa controlada por ``alpha``:

    final(d) = α · score_lexico(d) + (1 - α) · score_semantico(d)

Un documento que solo aparece en una rama recibe ``0`` en la otra (unión de
candidatos, no intersección).  Ambos scores viven en ``[0, 1]`` antes de la
fusión —el léxico lo garantiza el p-norm, y el coseno se recorta a ``[0, 1]``
para que valores ligeramente negativos no arrastren el score fusionado.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.indexing.embedder import TextEmbedder
    from src.indexing.inverted_index import InvertedIndex
    from src.indexing.vector_store import VectorStore
    from src.retrieval.extended_boolean import ExtendedBoolean

__all__ = ["HybridRetriever"]


class HybridRetriever:
    """Recuperador híbrido que fusiona p-norm léxico y coseno semántico.

    Atributos:
        alpha: Peso de la rama léxica en ``[0, 1]``.  ``alpha=1.0`` usa solo
               el Booleano Extendido; ``alpha=0.0`` usa solo la rama semántica.
    """

    def __init__(
        self,
        extended: ExtendedBoolean,
        embedder: TextEmbedder,
        store: VectorStore,
        collection: str,
        alpha: float = 0.5,
    ) -> None:
        if not 0.0 <= alpha <= 1.0:
            raise ValueError(
                f"alpha debe estar en [0, 1], se recibió: {alpha}"
            )
        self._extended = extended
        self._embedder = embedder
        self._store = store
        self._collection = collection
        self.alpha = alpha

    def search(
        self,
        query: str,
        index: InvertedIndex,
        top_k: int = 10,
        *,
        fetch_k: int | None = None,
    ) -> list[tuple[str, float]]:
        """Devuelve los ``top_k`` destinos con mayor score fusionado.

        Recupera ``fetch_k`` candidatos de cada rama (por defecto
        ``max(top_k * 3, 30)``) para que la fusión disponga de material
        suficiente cuando los dos rankings discrepan.

        Args:
            query:    Consulta natural/booleana.  La rama léxica parsea
                      AND/OR; la semántica la embebe directamente.
            index:    Índice invertido con TF-IDF ya calculado.
            top_k:    Número máximo de resultados a devolver.
            fetch_k:  Candidatos a traer de cada rama antes de fusionar.

        Returns:
            Lista ``(doc_id, score)`` ordenada de mayor a menor score.
        """
        fetch = fetch_k if fetch_k is not None else max(top_k * 3, 30)

        lexical_hits: list[tuple[str, float]]
        semantic_hits: list[tuple[str, float]] = []

        if self.alpha > 0.0:
            lexical_hits = self._extended.search(query, index, top_k=fetch)
        else:
            lexical_hits = []

        if self.alpha < 1.0:
            vector = self._embedder.embed(query)
            for _point_id, score, payload in self._store.search(
                self._collection, vector, top_k=fetch
            ):
                slug = str(payload.get("slug") or _point_id)
                clamped = max(0.0, min(1.0, float(score)))
                semantic_hits.append((slug, clamped))

        lex_map = dict(lexical_hits)
        sem_map = dict(semantic_hits)

        combined: dict[str, float] = {}
        for doc_id in lex_map.keys() | sem_map.keys():
            lex = lex_map.get(doc_id, 0.0)
            sem = sem_map.get(doc_id, 0.0)
            combined[doc_id] = self.alpha * lex + (1.0 - self.alpha) * sem

        ranked = sorted(combined.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]
