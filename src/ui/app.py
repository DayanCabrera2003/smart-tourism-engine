"""T043/T044/T045/T047 — Streamlit UI para consultar el endpoint ``POST /search``.

- T043: input de texto, botón de búsqueda y llamada HTTP a la API.
- T044: cada resultado se renderiza como una tarjeta con nombre, país,
  descripción truncada y score.
- T045: cuando el destino incluye ``image_urls``, la tarjeta muestra la
  primera imagen disponible y degrada con elegancia si la lista está vacía
  o la URL no es válida.
- T047: el sidebar expone sliders para ``top_k`` (1-50) y ``p`` (1-10) del
  Booleano Extendido, que se envían al backend en cada búsqueda.

La lógica de llamada HTTP y el helper de truncado viven como funciones puras
para poder testearlos sin necesidad de levantar el runtime de Streamlit.
"""
from __future__ import annotations

import os

import httpx

from src.api.schemas import DestinationResult, SearchResponse

DEFAULT_API_URL = "http://localhost:8000"
API_URL = os.getenv("SMART_TOURISM_API_URL", DEFAULT_API_URL)
DESCRIPTION_MAX_CHARS = 220

DEFAULT_TOP_K = 10
TOP_K_MIN = 1
TOP_K_MAX = 50
DEFAULT_P = 2.0
P_MIN = 1.0
P_MAX = 10.0


def pick_cover_image(image_urls: list[str] | None) -> str | None:
    """Devuelve la primera URL utilizable de ``image_urls`` (T045).

    Ignora entradas vacías o no-strings para que la card no intente cargar
    una imagen rota cuando el corpus tiene URLs inválidas.
    """
    if not image_urls:
        return None
    for url in image_urls:
        if isinstance(url, str) and url.strip():
            return url.strip()
    return None


def truncate_description(text: str | None, max_chars: int = DESCRIPTION_MAX_CHARS) -> str:
    """Trunca la descripción a ``max_chars`` cortando en el último espacio (T044)."""
    if not text:
        return ""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    cut = text[: max_chars - 1]
    space = cut.rfind(" ")
    if space > max_chars // 2:
        cut = cut[:space]
    return cut.rstrip() + "…"


def search_destinations(
    query: str,
    *,
    top_k: int = DEFAULT_TOP_K,
    p: float = DEFAULT_P,
    api_url: str = API_URL,
    client: httpx.Client | None = None,
) -> list[DestinationResult]:
    """Llama a ``POST {api_url}/search`` y devuelve los destinos rankeados.

    El parámetro ``client`` permite inyectar un ``httpx.Client`` en tests
    (p.ej. uno montado sobre la app FastAPI). ``p`` es la norma-p del
    Booleano Extendido (T047).
    """
    payload = {"query": query, "top_k": top_k, "p": p}
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

    with st.sidebar:
        st.header("Parámetros")
        top_k = st.slider(
            "top_k",
            min_value=TOP_K_MIN,
            max_value=TOP_K_MAX,
            value=DEFAULT_TOP_K,
            step=1,
            help="Número máximo de destinos a devolver.",
        )
        p = st.slider(
            "p (norma)",
            min_value=P_MIN,
            max_value=P_MAX,
            value=DEFAULT_P,
            step=0.5,
            help=(
                "Norma-p del Booleano Extendido. p=1 → vectorial (AND/OR "
                "blandos); p→∞ → Booleano puro (AND/OR estrictos)."
            ),
        )

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
            results = search_destinations(query, top_k=top_k, p=p)
        except httpx.HTTPError as exc:
            st.error(f"Error al consultar la API ({API_URL}): {exc}")
            return

        if not results:
            st.info("Sin resultados para esta consulta.")
            return

        st.subheader(f"{len(results)} resultado(s)")
        for rank, hit in enumerate(results, start=1):
            _render_card(st, rank, hit)


def _render_card(st, rank: int, hit: DestinationResult) -> None:  # pragma: no cover - Streamlit
    """Renderiza un destino como tarjeta con nombre, país, descripción y score (T044)."""
    with st.container(border=True):
        header, score_col = st.columns([6, 1])
        title = hit.name or hit.id
        header.markdown(f"### {rank}. {title}")
        score_col.metric(label="score", value=f"{hit.score:.3f}")
        meta_bits: list[str] = []
        if hit.country:
            meta_bits.append(f":earth_americas: {hit.country}")
        meta_bits.append(f"`{hit.id}`")
        header.caption(" · ".join(meta_bits))
        cover = pick_cover_image(hit.image_urls)
        if cover:
            try:
                st.image(cover, use_container_width=True)
            except Exception:
                st.caption(":frame_with_picture: Imagen no disponible.")
        description = truncate_description(hit.description)
        if description:
            st.write(description)


if __name__ == "__main__":  # pragma: no cover
    _render()
