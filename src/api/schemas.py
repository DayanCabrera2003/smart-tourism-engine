"""Schemas Pydantic de request/response de la API (T041, T055).

Centraliza los modelos que consume ``src/api/main.py`` para los endpoints
``POST /search``, ``POST /search/semantic`` y ``POST /search/hybrid``.
Mantenerlos aislados facilita su reutilización desde la UI y los tests, y
evita mezclar definiciones de datos con el wiring de FastAPI.
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
    p: float = Field(
        2.0,
        ge=1.0,
        le=10.0,
        description=(
            "Parámetro de la norma-p del Booleano Extendido (T047). "
            "p=1 → vectorial (operadores blandos); p→∞ → Booleano puro "
            "(operadores estrictos). Valores típicos para turismo: 2-5."
        ),
    )


class SemanticSearchRequest(BaseModel):
    """Cuerpo del ``POST /search/semantic`` (T053)."""

    query: str = Field(
        ...,
        min_length=1,
        description="Consulta en lenguaje natural; se embebe con TextEmbedder.",
    )
    top_k: int = Field(
        10,
        ge=1,
        le=100,
        description="Número máximo de vecinos a devolver desde Qdrant.",
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
    from_web: bool = Field(
        False,
        description="True si el resultado proviene de la busqueda web (Tavily, T078).",
    )


class HybridSearchRequest(BaseModel):
    """Cuerpo del ``POST /search/hybrid`` (T055)."""

    query: str = Field(
        ...,
        min_length=1,
        description="Consulta; la rama léxica parsea AND/OR, la semántica la embebe.",
    )
    top_k: int = Field(
        10,
        ge=1,
        le=100,
        description="Número máximo de resultados a devolver.",
    )
    alpha: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description=(
            "Peso de la rama léxica en [0, 1]. "
            "alpha=1.0 → solo Booleano Extendido; alpha=0.0 → solo semántico."
        ),
    )
    p: float = Field(
        2.0,
        ge=1.0,
        le=10.0,
        description="Norma-p de la rama Booleana Extendida.",
    )


class SearchResponse(BaseModel):
    """Respuesta del ``POST /search`` con los destinos rankeados."""

    results: list[DestinationResult] = Field(
        default_factory=list,
        description="Destinos ordenados de mayor a menor score.",
    )


class AskResponse(BaseModel):
    """Respuesta del pipeline RAG (T064)."""

    answer: str = Field(..., description="Texto generado por el LLM.")
    sources: list[DestinationResult] = Field(
        default_factory=list,
        description="Destinos recuperados usados como contexto.",
    )
    cached: bool = Field(False, description="True si la respuesta proviene del cache.")
    low_confidence: bool = Field(
        False,
        description="True si el LLM no encontro informacion suficiente en el contexto.",
    )


class AskRequest(BaseModel):
    """Cuerpo del ``POST /ask`` y ``POST /ask/stream``."""

    query: str = Field(..., min_length=1, description="Pregunta en lenguaje natural.")
    top_k: int = Field(5, ge=1, le=50, description="Destinos a recuperar como contexto.")
    mode: str = Field(
        "hybrid",
        pattern="^(boolean|semantic|hybrid)$",
        description="Modo de recuperación: boolean, semantic o hybrid.",
    )
    alpha: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Peso de la rama léxica en modo hybrid.",
    )
