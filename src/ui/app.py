"""T043 — Streamlit MVP para consultar el endpoint ``POST /search``.

Scope mínimo (T043): input de texto, botón de búsqueda y lista de resultados.
Las tarjetas visuales, imágenes y sliders se añaden en T044-T047.

La lógica de llamada HTTP vive en :func:`search_destinations` para poder
testearse sin necesidad de levantar el runtime de Streamlit.
"""
from __future__ import annotations

import os

import httpx

from src.api.schemas import DestinationResult, SearchResponse

DEFAULT_API_URL = "http://localhost:8000"
API_URL = os.getenv("SMART_TOURISM_API_URL", DEFAULT_API_URL)


def search_destinations(
    query: str,
    *,
    top_k: int = 10,
    api_url: str = API_URL,
    client: httpx.Client | None = None,
) -> list[DestinationResult]:
    """Llama a ``POST {api_url}/search`` y devuelve los destinos rankeados.

    El parámetro ``client`` permite inyectar un ``httpx.Client`` en tests
    (p.ej. uno montado sobre la app FastAPI).
    """
    payload = {"query": query, "top_k": top_k}
    owns_client = client is None
    http = client or httpx.Client(base_url=api_url, timeout=10.0)
    try:
        response = http.post("/search", json=payload)
        response.raise_for_status()
        parsed = SearchResponse.model_validate(response.json())
        return parsed.results
    finally:
        if owns_client:
            http.close()


def _render() -> None:  # pragma: no cover - depende del runtime de Streamlit
    import streamlit as st

    st.set_page_config(page_title="Smart Tourism Engine", page_icon=":mag:")
    st.title("Smart Tourism Engine")
    st.caption("MVP — Booleano Extendido (p-norm)")

    query = st.text_input(
        "Consulta",
        placeholder="playa AND España",
        help="Usa AND/OR en mayúsculas para combinar términos.",
    )
    search_clicked = st.button("Buscar", type="primary")

    if search_clicked:
        if not query.strip():
            st.warning("Escribe una consulta antes de buscar.")
            return
        try:
            results = search_destinations(query)
        except httpx.HTTPError as exc:
            st.error(f"Error al consultar la API ({API_URL}): {exc}")
            return

        if not results:
            st.info("Sin resultados para esta consulta.")
            return

        st.subheader(f"{len(results)} resultado(s)")
        for rank, hit in enumerate(results, start=1):
            st.write(f"**{rank}. {hit.id}** — score `{hit.score:.4f}`")


if __name__ == "__main__":  # pragma: no cover
    _render()
