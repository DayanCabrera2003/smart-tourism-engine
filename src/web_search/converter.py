"""T076 — Convierte WebResult de Tavily a Destination parcial."""
from __future__ import annotations

import hashlib

from src.ingestion.models import Destination
from src.web_search.tavily import WebResult

__all__ = ["web_result_to_destination"]


def web_result_to_destination(result: WebResult) -> Destination:
    """Convierte un resultado web en un Destination best-effort.

    Campos no disponibles desde la web (coordenadas, region, tags)
    quedan en None/vacio. El id se deriva del hash de la URL para
    garantizar idempotencia en la persistencia.
    """
    dest_id = "web-" + hashlib.sha256(result.url.encode()).hexdigest()[:12]
    description = result.snippet.strip() or result.title

    return Destination(
        id=dest_id,
        name=result.title.strip() or result.url,
        country="web",
        description=description,
        source="tavily",
        image_urls=[],
    )
