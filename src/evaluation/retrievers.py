"""T108 - Retriever adapters that turn the production code into the
``RetrieverFn`` shape consumed by :func:`src.evaluation.runner.evaluate`.

Each builder wraps an instance of a production retriever so the
evaluation runner sees a uniform ``(query, top_k) -> list[str]``
callable regardless of the underlying machinery. Builders that depend
on optional services (Qdrant) raise at construction time so the CLI
can fall back to ``available=False`` for that mode.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.evaluation.runner import RetrieverFn


def build_boolean_retriever(index_path: Path, *, p: float = 2.0) -> RetrieverFn:
    """Wrap the Extended Boolean retriever (p-norm).

    Loading the index from disk is the only side effect — the function
    returned is a closure that reuses the loaded index across queries.
    """
    from src.indexing.inverted_index import InvertedIndex
    from src.retrieval.extended_boolean import ExtendedBoolean

    index = InvertedIndex.load(index_path)
    retriever = ExtendedBoolean(p=p)

    def _retrieve(query: str, top_k: int) -> list[str]:
        hits = retriever.search(query, index, top_k=top_k)
        return [doc_id for doc_id, _score in hits]

    return _retrieve


def build_semantic_retriever(
    collection: Optional[str] = None,
) -> RetrieverFn:
    """Wrap the dense semantic retriever (Qdrant + TextEmbedder)."""
    from src.indexing.embed_destinations import DEFAULT_COLLECTION
    from src.indexing.embedder import TextEmbedder
    from src.indexing.vector_store import VectorStore

    embedder = TextEmbedder()
    store = VectorStore()
    coll = collection or DEFAULT_COLLECTION

    def _retrieve(query: str, top_k: int) -> list[str]:
        vector = embedder.embed(query)
        hits = store.search(coll, vector, top_k=top_k)
        return [str(payload.get("slug") or point_id) for point_id, _score, payload in hits]

    return _retrieve


def build_hybrid_retriever(
    index_path: Path,
    *,
    p: float = 2.0,
    alpha: float = 0.5,
    collection: Optional[str] = None,
) -> RetrieverFn:
    """Wrap the hybrid retriever (Boolean Extended + semantic)."""
    from src.indexing.embed_destinations import DEFAULT_COLLECTION
    from src.indexing.embedder import TextEmbedder
    from src.indexing.inverted_index import InvertedIndex
    from src.indexing.vector_store import VectorStore
    from src.retrieval.extended_boolean import ExtendedBoolean
    from src.retrieval.hybrid import HybridRetriever

    index = InvertedIndex.load(index_path)
    embedder = TextEmbedder()
    store = VectorStore()
    coll = collection or DEFAULT_COLLECTION

    hybrid = HybridRetriever(
        extended=ExtendedBoolean(p=p),
        embedder=embedder,
        store=store,
        collection=coll,
        alpha=alpha,
    )

    def _retrieve(query: str, top_k: int) -> list[str]:
        hits = hybrid.search(query, index, top_k=top_k)
        return [doc_id for doc_id, _score in hits]

    return _retrieve
