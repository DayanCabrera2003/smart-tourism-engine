from datetime import datetime, timezone
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field, HttpUrl


class Destination(BaseModel):
    """
    Modelo de datos para un destino turístico.
    Representa la información consolidada de diversas fuentes (Wikivoyage, OpenTripMap, etc.).
    """

    id: str = Field(..., description="Identificador único del destino (ej. hash o slug)")
    name: str = Field(..., description="Nombre del destino")
    country: str = Field(..., description="País al que pertenece el destino")
    region: Optional[str] = Field(None, description="Región o estado dentro del país")
    description: str = Field(..., description="Descripción textual del destino (con acentos)")
    description_normalized: Optional[str] = Field(
        None,
        description="Descripción normalizada (sin acentos, minúsculas) para matching/indexación",
    )
    tags: List[str] = Field(default_factory=list, description="Lista de etiquetas o categorías")
    image_urls: List[HttpUrl] = Field(default_factory=list, description="URLs de imágenes")
    coordinates: Optional[Tuple[float, float]] = Field(
        None, description="Coordenadas geográficas (latitud, longitud)"
    )
    source: str = Field(..., description="Fuente de donde se obtuvo la información")
    fetched_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Fecha de adquisición",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": "madrid-es",
                "name": "Madrid",
                "country": "España",
                "region": "Comunidad de Madrid",
                "description": "Capital de España, conocida por sus museos y vida nocturna.",
                "description_normalized": "capital de espana conocida por sus museos",
                "tags": ["ciudad", "cultura", "museos"],
                "image_urls": ["https://example.com/madrid.jpg"],
                "coordinates": (40.416775, -3.703790),
                "source": "wikivoyage",
                "fetched_at": "2026-04-07T12:00:00Z",
            }
        }
    }
