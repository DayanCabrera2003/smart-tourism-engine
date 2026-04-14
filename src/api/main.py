"""Aplicación FastAPI del Smart Tourism Engine.

T039 — Expone el endpoint ``GET /health`` para verificación de disponibilidad.
T040 — Expone el endpoint ``POST /search`` que delega en el recuperador
       Booleano Extendido (p-norm) y devuelve los destinos rankeados.
T042 — Registra el middleware de logging y los handlers de errores unificados
       definidos en ``src/api/middleware.py``.
"""
from __future__ import annotations

import pickle
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException

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


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


IndexDep = Annotated[InvertedIndex, Depends(get_index)]
RetrieverDep = Annotated[ExtendedBoolean, Depends(get_retriever)]


@app.post("/search", response_model=SearchResponse)
def search(
    request: SearchRequest,
    index: IndexDep,
    retriever: RetrieverDep,
) -> SearchResponse:
    """Busca destinos con el Booleano Extendido (p-norm) y los devuelve rankeados."""
    hits = retriever.search(request.query, index, top_k=request.top_k)
    return SearchResponse(
        results=[DestinationResult(id=doc_id, score=score) for doc_id, score in hits]
    )
