"""T043-T098 — Streamlit UI para consultar los endpoints de búsqueda y recomendación.

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
- T097: onboarding de perfil sintético; selección persistida en
  ``st.session_state``.
- T098: pestaña "Recomendado para ti" que consume ``POST /recommend`` y
  renderiza los destinos sugeridos para el perfil activo.

La lógica de llamada HTTP y los helpers viven como funciones puras para poder
testearlos sin necesidad de levantar el runtime de Streamlit.
"""
from __future__ import annotations

import os

import httpx

from src.api.schemas import (
    AskResponse,
    DestinationResult,
    ImageSearchResponse,
    RecommendResponse,
    SearchResponse,
)
from src.recommendation.synthetic_profiles import (
    SYNTHETIC_PROFILE_DESCRIPTIONS,
    list_synthetic_profile_ids,
)
from src.retrieval.freshness import freshness_score
from src.retrieval.positioning import build_positioning_sections
from src.ui.i18n import DEFAULT_LOCALE, LOCALES, t

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

WEB_BADGE = "[Busqueda web]"

LOCALE_SESSION_KEY = "ui_locale"

PROFILE_SESSION_KEY = "user_profile_id"
PROFILE_LABELS: dict[str, str] = {
    "mochilero": "Mochilero",
    "familia": "Familia",
    "luna_de_miel": "Luna de miel",
    "aventurero": "Aventurero",
    "cultural": "Cultural",
    "lujo": "Lujo",
}
RECOMMEND_TOP_K_DEFAULT = 6
RECOMMEND_MODE_DEFAULT = "hybrid"
RECOMMEND_ALPHA_DEFAULT = 0.6

POSITIONING_SECTION_LABELS: dict[str, str] = {
    "relevantes": "Más relevantes",
    "populares": "Populares",
    "recientes": "Recientes",
    "variados": "Variados (por país)",
}
POSITIONING_SECTION_TOP_K = 5

MAP_ZOOM_DEFAULT = 4
MAP_HEIGHT_PX = 480


def results_with_coordinates(
    results: list[DestinationResult],
) -> list[DestinationResult]:
    """Filter ``results`` to those that have usable lat/lon (T104)."""
    return [
        r
        for r in results
        if r.latitude is not None and r.longitude is not None
    ]


def map_center(
    results: list[DestinationResult],
) -> tuple[float, float] | None:
    """Compute the center of the map as the centroid of geocoded results.

    Returns ``None`` when no result has coordinates so the caller can
    render an empty-state message instead of a default-centered map.
    """
    geocoded = results_with_coordinates(results)
    if not geocoded:
        return None
    avg_lat = sum(r.latitude for r in geocoded) / len(geocoded)
    avg_lon = sum(r.longitude for r in geocoded) / len(geocoded)
    return avg_lat, avg_lon


def build_marker_popup_html(result: DestinationResult) -> str:
    """Render a small HTML snippet for a marker popup (T104).

    Kept as a pure helper so the test suite can verify it without
    booting Streamlit. The HTML is escaped at boundary points to avoid
    breaking the popup with quotation marks in the destination name or
    description.
    """
    import html

    name = html.escape(result.name or result.id)
    country = html.escape(result.country or "")
    description = html.escape((result.description or "").strip())
    if len(description) > 200:
        description = description[:199].rstrip() + "…"
    parts = [f"<strong>{name}</strong>"]
    if country:
        parts.append(f"<br><em>{country}</em>")
    parts.append(f"<br><span>score: {result.score:.3f}</span>")
    if description:
        parts.append(f"<br><br>{description}")
    return "".join(parts)


def build_positioning_sections_from_results(
    results: list[DestinationResult],
    *,
    top_k: int = POSITIONING_SECTION_TOP_K,
) -> dict[str, list[DestinationResult]]:
    """Group ``DestinationResult`` items into the four UI sections (T103).

    Extracts popularity/freshness/country from the results themselves
    (the backend populates them when SQLite has the metadata) and
    delegates the ordering to :func:`build_positioning_sections`. The
    output reuses the same ``DestinationResult`` instances so the
    cards rendered for each section share metadata and images.
    """
    if not results:
        return {key: [] for key in POSITIONING_SECTION_LABELS}

    hits = [(r.id, float(r.score)) for r in results]
    by_id = {r.id: r for r in results}
    popularity = {
        r.id: float(r.popularity) for r in results if r.popularity is not None
    }
    freshness = {
        r.id: freshness_score(r.fetched_at) for r in results if r.fetched_at
    }
    country_by_id: dict[str, str | None] = {r.id: r.country for r in results}

    sections = build_positioning_sections(
        hits,
        popularity=popularity or None,
        freshness=freshness or None,
        country_by_id=country_by_id or None,
        top_k=top_k,
    )
    return {
        key: [by_id[doc_id] for doc_id, _ in section]
        for key, section in sections.items()
    }


def current_locale(session_state: dict) -> str:
    """Return the locale stored in session state, or the default (T116)."""
    locale = session_state.get(LOCALE_SESSION_KEY)
    if locale in LOCALES:
        return locale
    return DEFAULT_LOCALE


def store_selected_locale(session_state: dict, locale: str) -> None:
    """Persist the locale choice in ``st.session_state`` (T116)."""
    if locale not in LOCALES:
        raise ValueError(f"Unknown locale: {locale!r}; expected one of {LOCALES}")
    session_state[LOCALE_SESSION_KEY] = locale


def synthetic_profile_label(profile_id: str) -> str:
    """Map a synthetic profile id to a human-readable label for the UI."""
    return PROFILE_LABELS.get(profile_id, profile_id)


def synthetic_profile_description(profile_id: str) -> str:
    """Map a synthetic profile id to its Spanish description (T092)."""
    return SYNTHETIC_PROFILE_DESCRIPTIONS.get(profile_id, "")


def is_onboarding_complete(session_state: dict) -> bool:
    """True when the user already picked a synthetic profile (T097)."""
    return bool(session_state.get(PROFILE_SESSION_KEY))


def store_selected_profile(session_state: dict, profile_id: str) -> None:
    """Persist the chosen profile id into the Streamlit session state.

    The id is stored without the ``synthetic:`` prefix so we can render it
    by label, and added back to the prefix when calling ``/recommend``.
    """
    if profile_id not in PROFILE_LABELS:
        raise ValueError(f"Unknown synthetic profile: {profile_id!r}")
    session_state[PROFILE_SESSION_KEY] = profile_id


def selected_profile_user_id(session_state: dict) -> str | None:
    """Return the ``user_id`` (with synthetic: prefix) to send to the API."""
    raw = session_state.get(PROFILE_SESSION_KEY)
    if not raw:
        return None
    return f"synthetic:{raw}"


def fetch_recommendations(
    user_id: str | None,
    *,
    interests: list[str] | None = None,
    history: list[str] | None = None,
    top_k: int = RECOMMEND_TOP_K_DEFAULT,
    mode: str = RECOMMEND_MODE_DEFAULT,
    alpha: float = RECOMMEND_ALPHA_DEFAULT,
    api_url: str = API_URL,
    client: httpx.Client | None = None,
) -> RecommendResponse:
    """Call ``POST /recommend`` and return the parsed response (T098)."""
    payload: dict = {
        "user_id": user_id,
        "interests": list(interests or []),
        "history": list(history or []),
        "top_k": top_k,
        "mode": mode,
        "alpha": alpha,
    }
    owns_client = client is None
    http = client or httpx.Client(base_url=api_url, timeout=15.0)
    try:
        response = http.post("/recommend", json=payload)
        response.raise_for_status()
        return RecommendResponse.model_validate(response.json())
    finally:
        if owns_client:
            http.close()

_SEARCH_MODE_TO_API = {
    SEARCH_MODE_BOOLEAN: "boolean",
    SEARCH_MODE_SEMANTIC: "semantic",
    SEARCH_MODE_HYBRID: "hybrid",
}


def format_result_header(result: DestinationResult) -> str:
    """Devuelve el titulo de la tarjeta con badge si el resultado es web (T078)."""
    name = result.name or result.id
    if result.from_web:
        return f"{name} {WEB_BADGE}"
    return name


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


def search_by_image_upload(
    image_bytes: bytes,
    *,
    top_k: int = DEFAULT_TOP_K,
    api_url: str = API_URL,
    client: httpx.Client | None = None,
) -> ImageSearchResponse:
    """Envía una imagen al endpoint POST /search/by-image y devuelve los resultados."""
    owns_client = client is None
    http = client or httpx.Client(base_url=api_url, timeout=30.0)
    try:
        response = http.post(
            "/search/by-image",
            files={"file": ("image.jpg", image_bytes, "image/jpeg")},
            params={"top_k": top_k},
        )
        response.raise_for_status()
        return ImageSearchResponse.model_validate(response.json())
    finally:
        if owns_client:
            http.close()


def search_image_by_text_query(
    query: str,
    *,
    top_k: int = DEFAULT_TOP_K,
    api_url: str = API_URL,
    client: httpx.Client | None = None,
) -> ImageSearchResponse:
    """Envía una consulta de texto al endpoint POST /search/image-by-text."""
    owns_client = client is None
    http = client or httpx.Client(base_url=api_url, timeout=30.0)
    try:
        response = http.post(
            "/search/image-by-text",
            json={"query": query, "top_k": top_k},
        )
        response.raise_for_status()
        return ImageSearchResponse.model_validate(response.json())
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

    locale = current_locale(st.session_state)

    st.set_page_config(page_title=t("app_title", locale), page_icon=":mag:")
    st.title(t("app_title", locale))
    st.caption(t("app_caption", locale))

    with st.sidebar:
        new_locale = st.radio(
            t("language_label", locale),
            options=list(LOCALES),
            index=list(LOCALES).index(locale),
            horizontal=True,
            key="locale_radio",
        )
        if new_locale != locale:
            store_selected_locale(st.session_state, new_locale)
            st.rerun()

    if not is_onboarding_complete(st.session_state):
        _render_onboarding(st)
        return

    with st.sidebar:
        _render_profile_sidebar(st)
        st.divider()
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

    tab_search, tab_ask, tab_image, tab_reco = st.tabs(
        ["Buscar destinos", "Preguntar", "Buscar por imagen", "Recomendado para ti"]
    )

    with tab_search:
        query = st.text_input(
            "Consulta",
            placeholder="playa AND España" if mode == SEARCH_MODE_BOOLEAN else "playas del caribe",
            help=(
                "Usa AND/OR en mayusculas para el modo Booleano. "
                "En modo Semantico o Hibrido escribe en lenguaje natural."
            ),
        )
        show_sections = st.checkbox(
            "Agrupar por estrategia de posicionamiento (T103)",
            value=False,
            help=(
                "Muestra los resultados en cuatro secciones: Más relevantes, "
                "Populares, Recientes y Variados por país."
            ),
        )
        show_map = st.checkbox(
            "Mostrar mapa interactivo (T104)",
            value=False,
            help=(
                "Renderiza los resultados con coordenadas en un mapa con "
                "marcadores. Click en un marcador para ver el detalle."
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
                        if show_map:
                            _render_results_map(st, results)
                        if show_sections:
                            _render_positioning_sections(st, results)
                        else:
                            st.subheader(f"{len(results)} resultado(s) — modo: {mode}")
                            for rank, hit in enumerate(results, start=1):
                                _render_card(st, rank, hit)

    with tab_ask:
        api_mode = _SEARCH_MODE_TO_API.get(mode, "hybrid")
        _render_ask_tab(st, top_k=top_k, mode=api_mode, alpha=alpha)

    with tab_image:
        _render_image_tab(st, top_k=top_k)

    with tab_reco:
        _render_recommend_tab(st)


IMAGE_GALLERY_THRESHOLD = 3


def _render_card(st, rank: int, hit: DestinationResult) -> None:  # pragma: no cover - Streamlit
    """Renderiza un destino como tarjeta con nombre, país, descripción y score (T044/T087)."""
    with st.container(border=True):
        header, score_col = st.columns([6, 1])
        title = format_result_header(hit)
        header.markdown(f"### {rank}. {title}")
        score_col.metric(label="score", value=f"{hit.score:.3f}")
        meta_bits: list[str] = []
        if hit.country:
            meta_bits.append(f":earth_americas: {hit.country}")
        meta_bits.append(f"`{hit.id}`")
        header.caption(" · ".join(meta_bits))
        _render_image_gallery(st, hit.image_urls)
        description = truncate_description(hit.description)
        if description:
            st.write(description)


def _render_image_gallery(st, image_urls: list[str] | None) -> None:  # pragma: no cover
    """Muestra las imágenes del destino (T087).

    Si hay 1 imagen, la muestra a ancho completo.
    Si hay varias, las muestra en un grid de hasta 3 columnas.
    """
    valid_urls = [u for u in (image_urls or []) if isinstance(u, str) and u.strip()]
    if not valid_urls:
        return
    if len(valid_urls) == 1:
        try:
            st.image(valid_urls[0], use_container_width=True)
        except Exception:
            st.caption("Imagen no disponible.")
        return
    cols = st.columns(min(len(valid_urls), IMAGE_GALLERY_THRESHOLD))
    for idx, url in enumerate(valid_urls[: IMAGE_GALLERY_THRESHOLD * 2]):
        col = cols[idx % IMAGE_GALLERY_THRESHOLD]
        try:
            col.image(url, use_container_width=True)
        except Exception:
            col.caption("N/D")


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
                label = f"[{i}] {format_result_header(src)}"
                if src.country:
                    label += f" — {src.country}"
                with st.expander(label):
                    if src.description:
                        st.write(src.description[:300])
    except Exception:
        pass


def _render_image_tab(st, *, top_k: int) -> None:  # pragma: no cover
    """Renderiza el tab de búsqueda multimodal (T086).

    Ofrece dos modos:
    - Subir imagen: envía la imagen a /search/by-image.
    - Consulta de texto: envía la query a /search/image-by-text.
    Los resultados muestran destination_id y ruta de imagen con su score CLIP.
    """
    st.subheader("Buscar por imagen")
    st.caption("Busca destinos visualmente similares o describe lo que buscas con texto.")

    mode_image = st.radio(
        "Modo de entrada",
        options=["Subir imagen", "Descripcion de texto"],
        horizontal=True,
        key="image_tab_mode",
    )

    if mode_image == "Subir imagen":
        uploaded = st.file_uploader(
            "Sube una imagen (JPEG o PNG)",
            type=["jpg", "jpeg", "png"],
            key="image_uploader",
        )
        search_clicked = st.button("Buscar similares", type="primary", key="img_search_btn")

        if search_clicked:
            if uploaded is None:
                st.warning("Sube una imagen primero.")
            else:
                st.image(uploaded, caption="Imagen subida", use_container_width=True)
                try:
                    resp = search_by_image_upload(uploaded.read(), top_k=top_k)
                except httpx.HTTPError as exc:
                    st.error(f"Error al consultar la API ({API_URL}): {exc}")
                    return
                if not resp.results:
                    st.info("Sin resultados. Asegúrate de que las imágenes están indexadas.")
                else:
                    st.subheader(f"{len(resp.results)} imagen(es) similar(es)")
                    _render_image_results(st, resp)

    else:
        query = st.text_input(
            "Descripcion visual",
            placeholder="playa tropical con palmeras",
            key="img_text_query",
        )
        search_clicked = st.button("Buscar imágenes", type="primary", key="img_text_btn")

        if search_clicked:
            if not query.strip():
                st.warning("Escribe una descripción antes de buscar.")
            else:
                try:
                    resp = search_image_by_text_query(query, top_k=top_k)
                except httpx.HTTPError as exc:
                    st.error(f"Error al consultar la API ({API_URL}): {exc}")
                    return
                if not resp.results:
                    st.info("Sin resultados. Asegúrate de que las imágenes están indexadas.")
                else:
                    st.subheader(f"{len(resp.results)} imagen(es) encontrada(s)")
                    _render_image_results(st, resp)


def _render_image_results(st, resp: ImageSearchResponse) -> None:  # pragma: no cover
    """Renderiza los resultados de búsqueda multimodal (T086)."""
    for hit in resp.results:
        with st.container(border=True):
            col_info, col_score = st.columns([5, 1])
            col_info.markdown(f"**{hit.destination_id}**")
            col_score.metric("score", f"{hit.score:.3f}")
            if hit.image_path:
                try:
                    st.image(hit.image_path, use_container_width=True)
                except Exception:
                    st.caption(f"`{hit.image_path}`")


def _render_onboarding(st) -> None:  # pragma: no cover - Streamlit
    """Initial profile picker (T097).

    Presents the six synthetic personas as radio buttons. The choice is
    persisted into ``st.session_state`` so the rest of the UI can read
    it without re-asking the user.
    """
    st.subheader("¿Qué tipo de viajero eres?")
    st.caption(
        "Elige el perfil que más se parezca a ti. "
        "Lo usaremos para personalizar la sección 'Recomendado para ti'."
    )

    options = list_synthetic_profile_ids()
    selection = st.radio(
        "Perfil",
        options=options,
        index=0,
        key="onboarding_radio",
        format_func=synthetic_profile_label,
    )
    st.write(synthetic_profile_description(selection))

    if st.button("Continuar", type="primary"):
        store_selected_profile(st.session_state, selection)
        st.rerun()


def _render_profile_sidebar(st) -> None:  # pragma: no cover - Streamlit
    """Show the active synthetic profile in the sidebar (T097)."""
    raw = st.session_state.get(PROFILE_SESSION_KEY)
    st.header("Tu perfil")
    if raw:
        st.markdown(f"**{synthetic_profile_label(raw)}**")
        st.caption(synthetic_profile_description(raw))
    if st.button("Cambiar perfil", key="reset_profile_btn"):
        st.session_state.pop(PROFILE_SESSION_KEY, None)
        st.rerun()


def _render_recommend_tab(st) -> None:  # pragma: no cover - Streamlit
    """Render the 'Recomendado para ti' tab (T098).

    Reads the synthetic profile from session state, calls ``/recommend``
    and renders each destination as a card consistent with the other
    tabs. The persona returned by the API is shown as a caption so the
    user can see which segment drove the ranking.
    """
    st.subheader("Recomendado para ti")
    user_id = selected_profile_user_id(st.session_state)
    if not user_id:
        st.info("Configura tu perfil en el onboarding para ver recomendaciones.")
        return

    top_k = st.slider(
        "Cuántas recomendaciones",
        min_value=1,
        max_value=20,
        value=RECOMMEND_TOP_K_DEFAULT,
        step=1,
        key="reco_top_k",
    )

    if not st.button("Cargar recomendaciones", type="primary", key="reco_btn"):
        return

    try:
        response = fetch_recommendations(user_id, top_k=top_k)
    except httpx.HTTPError as exc:
        st.error(f"Error al consultar la API ({API_URL}): {exc}")
        return

    if response.empty or not response.results:
        st.info("No hay recomendaciones disponibles todavía.")
        return

    if response.persona:
        st.caption(f"Anclado al perfil: {response.persona}")

    st.subheader(f"{len(response.results)} destino(s) sugerido(s)")
    for rank, hit in enumerate(response.results, start=1):
        _render_card(st, rank, hit)


def _render_results_map(  # pragma: no cover - Streamlit
    st, results: list[DestinationResult]
) -> None:
    """Render the interactive Folium map of geocoded results (T104).

    Imports are lazy so the rest of the app keeps booting on systems
    without streamlit-folium installed (e.g. CI doing lint only).
    """
    import folium
    from streamlit_folium import st_folium

    geocoded = results_with_coordinates(results)
    if not geocoded:
        st.info(
            "Ninguno de los resultados tiene coordenadas para mostrar en el mapa."
        )
        return

    center = map_center(geocoded)
    fmap = folium.Map(location=list(center), zoom_start=MAP_ZOOM_DEFAULT)
    for rank, result in enumerate(geocoded, start=1):
        popup_html = build_marker_popup_html(result)
        folium.Marker(
            location=[result.latitude, result.longitude],
            tooltip=f"{rank}. {result.name or result.id}",
            popup=folium.Popup(popup_html, max_width=320),
        ).add_to(fmap)

    st.caption(
        f"{len(geocoded)} de {len(results)} resultados tienen coordenadas."
    )
    st_folium(fmap, height=MAP_HEIGHT_PX, use_container_width=True)


def _render_positioning_sections(  # pragma: no cover - Streamlit
    st, results: list[DestinationResult]
) -> None:
    """Render the four positioning sections inside expanders (T103).

    Each section reuses ``_render_card`` so the visual layout matches
    the regular search tab. The first section ("Más relevantes") is
    open by default; the rest collapse to keep the page compact on
    small screens.
    """
    sections = build_positioning_sections_from_results(results)
    for key, label in POSITIONING_SECTION_LABELS.items():
        section_results = sections.get(key, [])
        if not section_results:
            continue
        is_first = key == "relevantes"
        with st.expander(
            f"{label} ({len(section_results)})",
            expanded=is_first,
        ):
            for rank, hit in enumerate(section_results, start=1):
                _render_card(st, rank, hit)


if __name__ == "__main__":  # pragma: no cover
    _render()
