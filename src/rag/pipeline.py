"""T064 — Pipeline RAG: recuperacion -> contexto -> generacion."""
from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Any

from src.api.schemas import AskResponse, DestinationResult
from src.rag.context_builder import build_context
from src.rag.prompts import build_prompt

if TYPE_CHECKING:
    from src.indexing.inverted_index import InvertedIndex
    from src.indexing.vector_store import VectorStore

__all__ = ["RagPipeline"]

_CACHE_MAX = 128


def _cache_key(query: str, top_k: int, mode: str, alpha: float) -> str:
    raw = f"{query.strip().lower()}|{top_k}|{mode}|{alpha:.2f}"
    return hashlib.sha256(raw.encode()).hexdigest()


class RagPipeline:
    """Orquesta recuperacion -> contexto -> generacion."""

    def __init__(
        self,
        *,
        index: InvertedIndex,
        embedder: Any,
        store: VectorStore,
        collection: str,
        destinations: dict[str, dict[str, Any]],
        llm: Any,
    ) -> None:
        self._index = index
        self._embedder = embedder
        self._store = store
        self._collection = collection
        self._destinations = destinations
        self._llm = llm
        self._cache: dict[str, AskResponse] = {}

    def answer(
        self,
        query: str,
        *,
        top_k: int = 5,
        mode: str = "hybrid",
        alpha: float = 0.5,
    ) -> AskResponse:
        """Devuelve respuesta generada con fuentes."""
        key = _cache_key(query, top_k, mode, alpha)
        if key in self._cache:
            cached = self._cache[key]
            return AskResponse(
                answer=cached.answer,
                sources=cached.sources,
                cached=True,
                low_confidence=cached.low_confidence,
            )

        hits = self._retrieve(query, top_k=top_k, mode=mode, alpha=alpha)
        sources = self._hits_to_results(hits)
        context = build_context(sources)
        prompt = build_prompt(query, context)
        answer_text = self._llm.generate(prompt)
        low_conf = False

        response = AskResponse(
            answer=answer_text,
            sources=sources,
            cached=False,
            low_confidence=low_conf,
        )
        if len(self._cache) >= _CACHE_MAX:
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[key] = response
        return response

    def _clear_cache(self) -> None:
        self._cache.clear()

    def answer_stream(
        self,
        query: str,
        *,
        top_k: int = 5,
        mode: str = "hybrid",
        alpha: float = 0.5,
    ):
        """Itera sobre tokens y emite el evento final JSON con fuentes.

        VERSION PRELIMINAR: low_confidence siempre False, sin acumulacion de tokens.
        Task 5 (T068) es una DEPENDENCIA HARD: actualiza este metodo con
        acumulacion de tokens y deteccion real de low_confidence.
        """
        hits = self._retrieve(query, top_k=top_k, mode=mode, alpha=alpha)
        sources = self._hits_to_results(hits)
        context = build_context(sources)
        prompt = build_prompt(query, context)

        for token in self._llm.generate_stream(prompt):
            yield token

        import json

        yield "[DONE]"
        yield json.dumps(
            {"sources": [s.model_dump() for s in sources], "low_confidence": False}
        )

    def _retrieve(
        self, query: str, *, top_k: int, mode: str, alpha: float
    ) -> list[tuple[str, float]]:
        from src.retrieval.extended_boolean import ExtendedBoolean
        from src.retrieval.hybrid import HybridRetriever

        if mode == "semantic":
            vector = self._embedder.embed(query)
            hits_raw = self._store.search(self._collection, vector, top_k=top_k)
            return [
                (str(payload.get("slug") or pid), max(0.0, min(1.0, float(score))))
                for pid, score, payload in hits_raw
            ]

        extended = ExtendedBoolean(p=2.0)
        if mode == "boolean":
            return extended.search(query, self._index, top_k=top_k)

        retriever = HybridRetriever(
            extended=extended,
            embedder=self._embedder,
            store=self._store,
            collection=self._collection,
            alpha=alpha,
        )
        return retriever.search(query, self._index, top_k=top_k)

    def _hits_to_results(self, hits: list[tuple[str, float]]) -> list[DestinationResult]:
        results: list[DestinationResult] = []
        for doc_id, score in hits:
            meta = self._destinations.get(doc_id) or {}
            results.append(
                DestinationResult(
                    id=doc_id,
                    score=max(0.0, min(1.0, score)),
                    name=meta.get("name"),
                    country=meta.get("country"),
                    description=meta.get("description"),
                    image_urls=list(meta.get("image_urls") or []),
                )
            )
        return results
