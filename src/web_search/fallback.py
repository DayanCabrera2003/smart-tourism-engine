"""Helper compartido para el fallback web (Tavily).

Centraliza la logica que antes vivia solo en RagPipeline._web_fallback
para que tanto /ask como los endpoints de busqueda la reutilicen sin
duplicar el flujo convertir -> persistir -> registrar -> ampliar hits.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.web_search.converter import web_result_to_destination
from src.web_search.persister import persist_web_destination

if TYPE_CHECKING:
    from src.indexing.embedder import TextEmbedder
    from src.indexing.vector_store import VectorStore

__all__ = ["run_web_fallback"]

_WEB_HIT_SCORE = 0.5


def run_web_fallback(
    query: str,
    existing_hits: list[tuple[str, float]],
    *,
    web_client: Any,
    embedder: "TextEmbedder",
    store: "VectorStore",
    collection: str,
    destinations: dict[str, dict[str, Any]],
    max_results: int = 5,
) -> list[tuple[str, float]]:
    """Consulta Tavily y devuelve los hits web seguidos de los locales.

    Cada resultado web se convierte a Destination, se persiste en SQLite y
    Qdrant, y se registra en ``destinations`` con ``from_web=True`` para que
    la capa de presentacion lo distinga. Si el rate limit esta agotado
    (RuntimeError) se devuelven los hits locales intactos.

    Los web van primero porque esta funcion solo se invoca cuando ya se
    decidio que los resultados locales son insuficientes: en ese escenario el
    web es la respuesta principal. Asi, aun sin re-ranking activado, los web
    encabezan el top_k en lugar de quedar al final de la lista local.
    """
    try:
        web_results = web_client.search(query, max_results=max_results)
    except RuntimeError:
        return existing_hits

    extra_hits: list[tuple[str, float]] = []
    for web_result in web_results:
        dest = web_result_to_destination(web_result)
        persist_web_destination(
            dest, embedder=embedder, store=store, collection=collection
        )
        destinations[dest.id] = {
            "name": dest.name,
            "country": dest.country,
            "description": dest.description,
            "image_urls": [],
            "from_web": True,
        }
        extra_hits.append((dest.id, _WEB_HIT_SCORE))

    return extra_hits + existing_hits
