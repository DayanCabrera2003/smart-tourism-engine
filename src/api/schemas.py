"""Schemas Pydantic de request/response de la API (T041).

Centraliza los modelos que consume ``src/api/main.py`` para el endpoint
``POST /search``.  Mantenerlos aislados facilita su reutilización desde la UI
y los tests, y evita mezclar definiciones de datos con el wiring de FastAPI.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Cuerpo del ``POST /search``."""

    query: str = Field(
        ...,
        min_length=1,
        description="Consulta con operadores AND/OR en mayúsculas.",
    )
    top_k: int = Field(
        10,
        ge=1,
        le=100,
        description="Número máximo de resultados a devolver.",
    )


class DestinationResult(BaseModel):
    """Destino rankeado devuelto por el recuperador p-norm."""

    id: str = Field(..., description="Identificador del destino en el corpus.")
    score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Score del Booleano Extendido, en el rango [0, 1].",
    )
    name: str | None = Field(
        None, description="Nombre del destino (T044). Ausente si no hay metadatos."
    )
    country: str | None = Field(
        None, description="País del destino (T044). Ausente si no hay metadatos."
    )
    description: str | None = Field(
        None,
        description="Descripción completa del destino (T044). La UI la trunca al renderizar.",
    )
    image_urls: list[str] = Field(
        default_factory=list,
        description=(
            "URLs de imágenes del destino (T045). La UI muestra la primera; "
            "lista vacía indica que no hay imágenes disponibles."
        ),
    )


class SearchResponse(BaseModel):
    """Respuesta del ``POST /search`` con los destinos rankeados."""

    results: list[DestinationResult] = Field(
        default_factory=list,
        description="Destinos ordenados de mayor a menor score.",
    )
