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
"""
from __future__ import annotations

import json
import pickle
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select

from src.api import middleware
from src.api.schemas import DestinationResult, SearchRequest, SearchResponse
from src.config import settings
from src.indexing.inverted_index import InvertedIndex
from src.retrieval.extended_boolean import ExtendedBoolean

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


def get_retriever() -> ExtendedBoolean:
    """Provee el recuperador p-norm.  Inyectable en tests."""
    return ExtendedBoolean(p=2.0)


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


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


IndexDep = Annotated[InvertedIndex, Depends(get_index)]
RetrieverDep = Annotated[ExtendedBoolean, Depends(get_retriever)]
DestinationsDep = Annotated[dict[str, dict[str, object]], Depends(get_destinations)]


@app.post("/search", response_model=SearchResponse)
def search(
    request: SearchRequest,
    index: IndexDep,
    retriever: RetrieverDep,
    destinations: DestinationsDep,
) -> SearchResponse:
    """Busca destinos con el Booleano Extendido (p-norm) y los devuelve rankeados."""
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
