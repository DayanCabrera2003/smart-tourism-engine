"""T043/T044/T045/T047/T055/T066 — Streamlit UI para consultar los endpoints de búsqueda.

- T043: input de texto, botón de búsqueda y llamada HTTP a la API.
- T044: cada resultado se renderiza como una tarjeta con nombre, país,
  descripción truncada y score.
- T045: cuando el destino incluye ``image_urls``, la tarjeta muestra la
  primera imagen disponible y degrada con elegancia si la lista está vacía
  o la URL no es válida.
- T047: el sidebar expone sliders para ``top_k`` (1-50) y ``p`` (1-10) del
  Booleano Extendido, que se envían al backend en cada búsqueda.
- T055: radio buttons para seleccionar el modo de búsqueda (Booleano
  Extendido / Semántico / Híbrido) y slider para el peso ``alpha``.
- T066: añade el tab "Preguntar" con helpers ``ask_question`` y ``stream_ask``
  que consumen ``POST /ask`` y ``POST /ask/stream`` respectivamente.

La lógica de llamada HTTP y los helpers viven como funciones puras para poder
testearlos sin necesidad de levantar el runtime de Streamlit.
"""
from __future__ import annotations

import os

import httpx

from src.api.schemas import AskResponse, DestinationResult, SearchResponse

DEFAULT_API_URL = "http://localhost:8000"
API_URL = os.getenv("SMART_TOURISM_API_URL", DEFAULT_API_URL)
DESCRIPTION_MAX_CHARS = 220

DEFAULT_TOP_K = 10
TOP_K_MIN = 1
TOP_K_MAX = 50
DEFAULT_P = 2.0
P_MIN = 1.0
P_MAX = 10.0

SEARCH_MODE_BOOLEAN = "Booleano Extendido"
SEARCH_MODE_SEMANTIC = "Semantico"
SEARCH_MODE_HYBRID = "Hibrido"
SEARCH_MODES = [SEARCH_MODE_BOOLEAN, SEARCH_MODE_SEMANTIC, SEARCH_MODE_HYBRID]

DEFAULT_ALPHA = 0.5
ALPHA_MIN = 0.0
ALPHA_MAX = 1.0

_SEARCH_MODE_TO_API = {
    SEARCH_MODE_BOOLEAN: "boolean",
    SEARCH_MODE_SEMANTIC: "semantic",
    SEARCH_MODE_HYBRID: "hybrid",
}


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
    mode: str = SEARCH_MODE_BOOLEAN,
    top_k: int = DEFAULT_TOP_K,
    p: float = DEFAULT_P,
    alpha: float = DEFAULT_ALPHA,
    api_url: str = API_URL,
    client: httpx.Client | None = None,
) -> list[DestinationResult]:
    """Llama al endpoint de búsqueda adecuado y devuelve los destinos rankeados.

    Selecciona el endpoint según ``mode``:
    - ``SEARCH_MODE_BOOLEAN``  → ``POST /search`` (Booleano Extendido, T047)
    - ``SEARCH_MODE_SEMANTIC`` → ``POST /search/semantic`` (T053)
    - ``SEARCH_MODE_HYBRID``   → ``POST /search/hybrid`` (T055)

    El parámetro ``client`` permite inyectar un ``httpx.Client`` en tests.
    """
    if mode == SEARCH_MODE_SEMANTIC:
        endpoint = "/search/semantic"
        payload: dict = {"query": query, "top_k": top_k}
    elif mode == SEARCH_MODE_HYBRID:
        endpoint = "/search/hybrid"
        payload = {"query": query, "top_k": top_k, "alpha": alpha, "p": p}
    else:
        endpoint = "/search"
        payload = {"query": query, "top_k": top_k, "p": p}

    owns_client = client is None
    http = client or httpx.Client(base_url=api_url, timeout=10.0)
    try:
        response = http.post(endpoint, json=payload)
        response.raise_for_status()
        parsed = SearchResponse.model_validate(response.json())
        return parsed.results
    finally:
        if owns_client:
            http.close()


def ask_question(
    query: str,
    *,
    top_k: int = 5,
    mode: str = "hybrid",
    alpha: float = DEFAULT_ALPHA,
    api_url: str = API_URL,
    client: httpx.Client | None = None,
) -> AskResponse:
    """Llama a POST /ask y devuelve la respuesta RAG completa."""
    owns_client = client is None
    http = client or httpx.Client(base_url=api_url, timeout=30.0)
    try:
        response = http.post(
            "/ask",
            json={"query": query, "top_k": top_k, "mode": mode, "alpha": alpha},
        )
        response.raise_for_status()
        return AskResponse.model_validate(response.json())
    finally:
        if owns_client:
            http.close()


def stream_ask(
    query: str,
    *,
    top_k: int = 5,
    mode: str = "hybrid",
    alpha: float = DEFAULT_ALPHA,
    api_url: str = API_URL,
):
    """Generador que consume /ask/stream SSE y hace yield de tokens o JSON final.

    Yields text tokens until a chunk starting with '{' (JSON with sources/low_confidence).
    """
    with httpx.stream(
        "POST",
        f"{api_url}/ask/stream",
        json={"query": query, "top_k": top_k, "mode": mode, "alpha": alpha},
        timeout=60.0,
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line.startswith("data:"):
                continue
            payload = line[len("data:"):].strip()
            if payload == "[DONE]":
                break
            if payload.startswith("{"):
                yield payload
                break
            if payload:
                yield payload


def _render() -> None:  # pragma: no cover - depende del runtime de Streamlit
    import streamlit as st

    st.set_page_config(page_title="Smart Tourism Engine", page_icon=":mag:")
    st.title("Smart Tourism Engine")
    st.caption("Booleano Extendido · Semantico · Hibrido")

    with st.sidebar:
        st.header("Modo de busqueda")
        mode = st.radio(
            "Modo",
            options=SEARCH_MODES,
            index=0,
            help=(
                "Booleano Extendido: rankeo lexico p-norm. "
                "Semantico: embeddings en Qdrant. "
                "Hibrido: combinacion de ambos con peso alpha."
            ),
        )

        st.header("Parametros")
        top_k = st.slider(
            "top_k",
            min_value=TOP_K_MIN,
            max_value=TOP_K_MAX,
            value=DEFAULT_TOP_K,
            step=1,
            help="Numero maximo de destinos a devolver.",
        )

        p = DEFAULT_P
        alpha = DEFAULT_ALPHA

        if mode in (SEARCH_MODE_BOOLEAN, SEARCH_MODE_HYBRID):
            p = st.slider(
                "p (norma)",
                min_value=P_MIN,
                max_value=P_MAX,
                value=DEFAULT_P,
                step=0.5,
                help=(
                    "Norma-p del Booleano Extendido. p=1 → vectorial (AND/OR "
                    "blandos); p→inf → Booleano puro (AND/OR estrictos)."
                ),
            )

        if mode == SEARCH_MODE_HYBRID:
            alpha = st.slider(
                "alpha",
                min_value=ALPHA_MIN,
                max_value=ALPHA_MAX,
                value=DEFAULT_ALPHA,
                step=0.05,
                help=(
                    "Peso de la rama lexica. alpha=1.0 → solo Booleano "
                    "Extendido; alpha=0.0 → solo semantico."
                ),
            )

    tab_search, tab_ask = st.tabs(["Buscar destinos", "Preguntar"])

    with tab_search:
        query = st.text_input(
            "Consulta",
            placeholder="playa AND España" if mode == SEARCH_MODE_BOOLEAN else "playas del caribe",
            help=(
                "Usa AND/OR en mayusculas para el modo Booleano. "
                "En modo Semantico o Hibrido escribe en lenguaje natural."
            ),
        )
        search_clicked = st.button("Buscar", type="primary")

        if search_clicked:
            if not query.strip():
                st.warning("Escribe una consulta antes de buscar.")
            else:
                try:
                    results = search_destinations(query, mode=mode, top_k=top_k, p=p, alpha=alpha)
                except httpx.HTTPError as exc:
                    st.error(f"Error al consultar la API ({API_URL}): {exc}")
                else:
                    if not results:
                        st.info("Sin resultados para esta consulta.")
                    else:
                        st.subheader(f"{len(results)} resultado(s) — modo: {mode}")
                        for rank, hit in enumerate(results, start=1):
                            _render_card(st, rank, hit)

    with tab_ask:
        api_mode = _SEARCH_MODE_TO_API.get(mode, "hybrid")
        _render_ask_tab(st, top_k=top_k, mode=api_mode, alpha=alpha)


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


def _render_ask_tab(st, *, top_k: int, mode: str, alpha: float) -> None:  # pragma: no cover
    """Renderiza el tab de preguntas con streaming (T066/T069)."""
    import json

    st.subheader("Pregunta al asistente turistico")
    question = st.text_input(
        "Pregunta",
        placeholder="¿Qué destino de playa en España es bueno para familias?",
        key="ask_input",
    )
    ask_clicked = st.button("Preguntar", type="primary", key="ask_btn")

    if not ask_clicked:
        return

    if not question.strip():
        st.warning("Escribe una pregunta antes de continuar.")
        return

    sources_json: str | None = None

    def _token_gen():
        nonlocal sources_json
        for chunk in stream_ask(question, top_k=top_k, mode=mode, alpha=alpha):
            if chunk.startswith("{"):
                sources_json = chunk
            else:
                yield chunk

    try:
        st.write_stream(_token_gen())
    except httpx.HTTPError as exc:
        st.error(f"Error al consultar la API ({API_URL}): {exc}")
        return

    if not sources_json:
        return

    try:
        data = json.loads(sources_json)
        if data.get("low_confidence"):
            st.warning("Informacion insuficiente en el corpus. Considera ampliar la busqueda.")
        sources_raw = data.get("sources", [])
        if sources_raw:
            st.divider()
            st.caption("Fuentes utilizadas:")
            for i, raw in enumerate(sources_raw, start=1):
                src = DestinationResult.model_validate(raw)
                label = f"[{i}] {src.name or src.id}"
                if src.country:
                    label += f" — {src.country}"
                with st.expander(label):
                    if src.description:
                        st.write(src.description[:300])
    except Exception:
        pass


if __name__ == "__main__":  # pragma: no cover
    _render()
