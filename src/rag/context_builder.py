"""T063 — Construye el contexto numerado para el prompt RAG."""
from __future__ import annotations

from src.api.schemas import DestinationResult

__all__ = ["build_context"]

_MAX_DESCRIPTION_CHARS = 400


def build_context(destinations: list[DestinationResult]) -> str:
    """Formatea la lista de destinos como contexto numerado para el LLM.

    Cada entrada tiene el formato:
        [N] Nombre (Pais)
            Descripcion truncada a 400 caracteres...
    """
    if not destinations:
        return ""

    parts: list[str] = []
    for i, dest in enumerate(destinations, start=1):
        name = dest.name or dest.id
        country = dest.country or ""
        header = f"[{i}] {name} ({country})" if country else f"[{i}] {name}"

        description = (dest.description or "").strip()
        if len(description) > _MAX_DESCRIPTION_CHARS:
            description = description[:_MAX_DESCRIPTION_CHARS].rstrip() + "..."

        body = description if description else header
        parts.append(f"{header}\n    {body}")

    return "\n\n".join(parts)
