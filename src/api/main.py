"""Aplicación FastAPI del Smart Tourism Engine.

T039 — Expone el endpoint ``GET /health`` para verificación de disponibilidad.
T040 — Expone el endpoint ``POST /search`` que delega en el recuperador
       Booleano Extendido (p-norm) y devuelve los destinos rankeados.
T042 — Registra el middleware de logging y los handlers de errores unificados
       definidos en ``src/api/middleware.py``.
T044 — Enriquece la respuesta con metadatos (nombre, país, descripción)
       leídos de ``destinations.db`` para alimentar las tarjetas de la UI.
T045 — Propaga ``image_urls`` (lista de URLs) para que la UI muestre la
       primera imagen disponible en cada tarjeta.
T047 — Acepta ``p`` en el body y construye el recuperador p-norm por
       petición, permitiendo a la UI exponer el parámetro en un slider.
T053 — Expone ``POST /search/semantic`` que embebe la consulta y consulta
       la colección ``destinations_text`` de Qdrant directamente.
T055 — Expone ``POST /search/hybrid`` que combina Booleano Extendido y
       semántico con peso ``alpha`` configurable.
"""
from __future__ import annotations

import json
import pickle
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select

from src.api import middleware
from src.api.schemas import (
    DestinationResult,
    HybridSearchRequest,
    SearchRequest,
    SearchResponse,
    SemanticSearchRequest,
)
from src.config import settings
from src.indexing.embed_destinations import DEFAULT_COLLECTION
from src.indexing.embedder import TextEmbedder
from src.indexing.inverted_index import InvertedIndex
from src.indexing.vector_store import VectorStore
from src.retrieval.extended_boolean import ExtendedBoolean
from src.retrieval.hybrid import HybridRetriever

app = FastAPI(
    title="Smart Tourism Engine API",
    description="API de recuperación de información turística.",
    version="0.1.0",
)
middleware.install(app)


# ── Dependencias ──────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_index_from_disk() -> InvertedIndex:
    index_path: Path = settings.DATA_DIR / "processed" / "index.pkl"
    if not index_path.exists():
        raise HTTPException(
            status_code=503,
            detail=f"Índice no disponible en {index_path}. Ejecuta `build-index` primero.",
        )
    with index_path.open("rb") as fh:
        return pickle.load(fh)


def get_index() -> InvertedIndex:
    """Provee el índice invertido.  Inyectable en tests."""
    return _load_index_from_disk()


def get_retriever_factory() -> Callable[[float], ExtendedBoolean]:
    """Fábrica de recuperadores p-norm parametrizada por ``p`` (T047).

    Devolver una fábrica (en vez de una instancia fija) permite que cada
    petición use el ``p`` enviado por el cliente sin perder el hook de
    inyección para los tests.
    """
    return lambda p: ExtendedBoolean(p=p)


@lru_cache(maxsize=1)
def _load_destinations_from_disk() -> dict[str, dict[str, object]]:
    """Lee metadatos de destinos desde ``destinations.db`` (T044).

    Devuelve un dict ``id → {name, country, description, image_urls}`` para
    enriquecer la respuesta de ``/search``. Si la tabla aún no existe o está
    vacía, devuelve ``{}`` y la API degrada a la respuesta mínima de T043.
    """
    from sqlalchemy.exc import SQLAlchemyError

    from src.ingestion.store import Session, destinations

    try:
        with Session() as session:
            rows = session.execute(select(destinations)).mappings().all()
    except SQLAlchemyError:
        return {}

    out: dict[str, dict[str, object]] = {}
    for row in rows:
        out[row["id"]] = {
            "name": row["name"],
            "country": row["country"],
            "description": row["description"] or "",
            "image_urls": json.loads(row["image_urls"] or "[]"),
        }
    return out


def get_destinations() -> dict[str, dict[str, object]]:
    """Provee el mapa de metadatos por id.  Inyectable en tests."""
    return _load_destinations_from_disk()


@lru_cache(maxsize=1)
def _default_vector_store() -> VectorStore:
    return VectorStore()


def get_vector_store() -> VectorStore:
    """Provee el cliente de Qdrant (T053).  Inyectable en tests."""
    return _default_vector_store()


@lru_cache(maxsize=1)
def _default_embedder() -> TextEmbedder:
    return TextEmbedder()


def get_embedder() -> TextEmbedder:
    """Provee el embedder de texto (T053).  Inyectable en tests."""
    return _default_embedder()


def get_semantic_collection() -> str:
    """Nombre de la colección Qdrant a consultar (T053)."""
    return DEFAULT_COLLECTION


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


IndexDep = Annotated[InvertedIndex, Depends(get_index)]
RetrieverFactoryDep = Annotated[
    Callable[[float], ExtendedBoolean], Depends(get_retriever_factory)
]
DestinationsDep = Annotated[dict[str, dict[str, object]], Depends(get_destinations)]


@app.post("/search", response_model=SearchResponse)
def search(
    request: SearchRequest,
    index: IndexDep,
    retriever_factory: RetrieverFactoryDep,
    destinations: DestinationsDep,
) -> SearchResponse:
    """Busca destinos con el Booleano Extendido (p-norm) y los devuelve rankeados."""
    retriever = retriever_factory(request.p)
    hits = retriever.search(request.query, index, top_k=request.top_k)
    results: list[DestinationResult] = []
    for doc_id, score in hits:
        meta = destinations.get(doc_id) or {}
        results.append(
            DestinationResult(
                id=doc_id,
                score=score,
                name=meta.get("name"),
                country=meta.get("country"),
                description=meta.get("description"),
                image_urls=list(meta.get("image_urls") or []),
            )
        )
    return SearchResponse(results=results)


VectorStoreDep = Annotated[VectorStore, Depends(get_vector_store)]
EmbedderDep = Annotated[TextEmbedder, Depends(get_embedder)]
SemanticCollectionDep = Annotated[str, Depends(get_semantic_collection)]


@app.post("/search/semantic", response_model=SearchResponse)
def search_semantic(
    request: SemanticSearchRequest,
    store: VectorStoreDep,
    embedder: EmbedderDep,
    collection: SemanticCollectionDep,
    destinations: DestinationsDep,
) -> SearchResponse:
    """Búsqueda semántica (T053): embebe la query y consulta Qdrant directamente."""
    try:
        query_vector = embedder.embed(request.query)
        hits = store.search(collection, query_vector, top_k=request.top_k)
    except Exception as exc:  # pragma: no cover - delegado a middleware
        raise HTTPException(
            status_code=503,
            detail=f"Búsqueda semántica no disponible: {exc}",
        ) from exc

    results: list[DestinationResult] = []
    for _point_id, score, payload in hits:
        slug = str(payload.get("slug") or _point_id)
        meta = destinations.get(slug) or {}
        results.append(
            DestinationResult(
                id=slug,
                score=max(0.0, min(1.0, float(score))),
                name=payload.get("name") or meta.get("name"),
                country=payload.get("country") or meta.get("country"),
                description=meta.get("description"),
                image_urls=list(payload.get("image_urls") or meta.get("image_urls") or []),
            )
        )
    return SearchResponse(results=results)


@app.post("/search/hybrid", response_model=SearchResponse)
def search_hybrid(
    request: HybridSearchRequest,
    index: IndexDep,
    store: VectorStoreDep,
    embedder: EmbedderDep,
    collection: SemanticCollectionDep,
    retriever_factory: RetrieverFactoryDep,
    destinations: DestinationsDep,
) -> SearchResponse:
    """Búsqueda híbrida (T055): Booleano Extendido + semántico con peso alpha."""
    extended = retriever_factory(request.p)
    hybrid = HybridRetriever(
        extended=extended,
        embedder=embedder,
        store=store,
        collection=collection,
        alpha=request.alpha,
    )
    hits = hybrid.search(request.query, index, top_k=request.top_k)
    results: list[DestinationResult] = []
    for doc_id, score in hits:
        meta = destinations.get(doc_id) or {}
        results.append(
            DestinationResult(
                id=doc_id,
                score=score,
                name=meta.get("name"),
                country=meta.get("country"),
                description=meta.get("description"),
                image_urls=list(meta.get("image_urls") or []),
            )
        )
    return SearchResponse(results=results)
