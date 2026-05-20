"""Aplicación FastAPI del Smart Tourism Engine.

T039 — Expone el endpoint ``GET /health`` para verificación de disponibilidad.
T040 — Expone el endpoint ``POST /search`` que delega en el recuperador
       Booleano Extendido (p-norm) y devuelve los destinos rankeados.
T042 — Registra el middleware de logging y los handlers de errores unificados
       definidos en ``src/api/middleware.py``.
T044 — Enriquece la respuesta con metadatos (nombre, país, descripción)
       leídos de ``destinations.db`` para alimentar las tarjetas de la UI.
T045 — Propaga ``image_urls`` (lista de URLs) para que la UI muestre la
       primera imagen disponible en cada tarjeta.
T047 — Acepta ``p`` en el body y construye el recuperador p-norm por
       petición, permitiendo a la UI exponer el parámetro en un slider.
T053 — Expone ``POST /search/semantic`` que embebe la consulta y consulta
       la colección ``destinations_text`` de Qdrant directamente.
T055 — Expone ``POST /search/hybrid`` que combina Booleano Extendido y
       semántico con peso ``alpha`` configurable.
T065 — Expone ``POST /ask`` que delega en ``RagPipeline`` para responder
       preguntas en lenguaje natural con contexto recuperado.
T069 — Expone ``POST /ask/stream`` con SSE para streaming en tiempo real.
"""
from __future__ import annotations

import json
import pickle
from collections.abc import Callable
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    from src.rag.pipeline import RagPipeline

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from src.api import middleware
from src.api.schemas import (
    AskRequest,
    AskResponse,
    DestinationResult,
    FeedbackRequest,
    FeedbackResponse,
    HybridSearchRequest,
    ImageByTextRequest,
    ImageSearchResponse,
    ImageSearchResult,
    MultimodalSearchRequest,
    RecommendRequest,
    RecommendResponse,
    SearchRequest,
    SearchResponse,
    SemanticSearchRequest,
)
from src.config import settings
from src.indexing.embed_destinations import DEFAULT_COLLECTION
from src.indexing.embedder import TextEmbedder
from src.indexing.inverted_index import InvertedIndex
from src.indexing.vector_store import VectorStore
from src.retrieval.extended_boolean import ExtendedBoolean
from src.retrieval.geo_filter import (
    apply_country_filter,
    detect_countries,
    filter_search_hits,
)
from src.retrieval.hybrid import HybridRetriever

app = FastAPI(
    title="Smart Tourism Engine API",
    description="API de recuperación de información turística.",
    version="0.1.0",
)
middleware.install(app)

# T121: Prometheus instrumentation. Registered after the error
# middleware so failed requests still contribute to the request
# counter with their final status code.
from src.api.metrics import install_metrics  # noqa: E402

install_metrics(app)


# ── Dependencias ──────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def _load_index_from_disk() -> InvertedIndex:
    index_path: Path = settings.DATA_DIR / "processed" / "index.pkl"
    if not index_path.exists():
        raise HTTPException(
            status_code=503,
            detail=f"Índice no disponible en {index_path}. Ejecuta `build-index` primero.",
        )
    with index_path.open("rb") as fh:
        return pickle.load(fh)


def get_index() -> InvertedIndex:
    """Provee el índice invertido.  Inyectable en tests."""
    return _load_index_from_disk()


def get_retriever_factory() -> Callable[[float], ExtendedBoolean]:
    """Fábrica de recuperadores p-norm parametrizada por ``p`` (T047).

    Devolver una fábrica (en vez de una instancia fija) permite que cada
    petición use el ``p`` enviado por el cliente sin perder el hook de
    inyección para los tests.
    """
    return lambda p: ExtendedBoolean(p=p)


@lru_cache(maxsize=1)
def _load_destinations_from_disk() -> dict[str, dict[str, object]]:
    """Lee metadatos de destinos desde ``destinations.db`` (T044).

    Devuelve un dict ``id → {name, country, description, image_urls}`` para
    enriquecer la respuesta de ``/search``. Si la tabla aún no existe o está
    vacía, devuelve ``{}`` y la API degrada a la respuesta mínima de T043.
    """
    from sqlalchemy.exc import SQLAlchemyError

    from src.ingestion.store import Session, destinations

    try:
        with Session() as session:
            rows = session.execute(select(destinations)).mappings().all()
    except SQLAlchemyError:
        return {}

    out: dict[str, dict[str, object]] = {}
    for row in rows:
        out[row["id"]] = {
            "name": row["name"],
            "country": row["country"],
            "description": row["description"] or "",
            "image_urls": json.loads(row["image_urls"] or "[]"),
            "popularity": row["popularity"] if "popularity" in row.keys() else None,
            "fetched_at": (
                row["fetched_at"].isoformat()
                if row["fetched_at"] is not None
                else None
            ),
            "lat": row["lat"] if "lat" in row.keys() else None,
            "lon": row["lon"] if "lon" in row.keys() else None,
        }
    return out


def get_destinations() -> dict[str, dict[str, object]]:
    """Provee el mapa de metadatos por id.  Inyectable en tests."""
    return _load_destinations_from_disk()


@lru_cache(maxsize=1)
def _default_vector_store() -> VectorStore:
    return VectorStore()


def get_vector_store() -> VectorStore:
    """Provee el cliente de Qdrant (T053).  Inyectable en tests."""
    return _default_vector_store()


@lru_cache(maxsize=1)
def _default_embedder() -> TextEmbedder:
    return TextEmbedder()


def get_embedder() -> TextEmbedder:
    """Provee el embedder de texto (T053).  Inyectable en tests."""
    return _default_embedder()


@lru_cache(maxsize=1)
def _default_rag_pipeline() -> "RagPipeline":
    from src.rag.llm_client import LLMClient
    from src.rag.pipeline import RagPipeline

    llm = LLMClient(
        provider=settings.LLM_PROVIDER,
        api_key=settings.LLM_API_KEY,
        ollama_url=settings.OLLAMA_URL,
        ollama_model=settings.OLLAMA_MODEL,
    )

    web_client = None
    if settings.TAVILY_API_KEY:
        from src.web_search.tavily import TavilyClient
        web_client = TavilyClient(
            settings.TAVILY_API_KEY,
            max_calls_per_minute=settings.TAVILY_RATE_LIMIT_PER_MINUTE,
        )

    return RagPipeline(
        index=_load_index_from_disk(),
        embedder=_default_embedder(),
        store=_default_vector_store(),
        collection=DEFAULT_COLLECTION,
        destinations=_load_destinations_from_disk(),
        llm=llm,
        web_client=web_client,
    )


def get_rag_pipeline() -> "RagPipeline":
    """Provee el pipeline RAG. Inyectable en tests."""
    return _default_rag_pipeline()


def get_semantic_collection() -> str:
    """Nombre de la colección Qdrant a consultar (T053)."""
    return DEFAULT_COLLECTION


@lru_cache(maxsize=1)
def _default_clip_embedder():
    from src.multimodal.clip_embedder import ClipEmbedder

    return ClipEmbedder()


def get_clip_embedder():
    """Provee el embedder CLIP (T084/T085).  Inyectable en tests."""
    return _default_clip_embedder()


def get_image_collection() -> str:
    """Nombre de la colección Qdrant de imágenes CLIP (T084)."""
    from src.multimodal.image_indexer import IMAGE_COLLECTION

    return IMAGE_COLLECTION


@lru_cache(maxsize=1)
def _default_recommendation_service():
    """Build the singleton RecommendationService used by ``/recommend`` (T096)."""
    from src.recommendation.service import RecommendationService

    return RecommendationService(
        _default_embedder(),
        _default_vector_store(),
        collection=DEFAULT_COLLECTION,
    )


def get_recommendation_service():
    """Provee el RecommendationService. Inyectable en tests."""
    return _default_recommendation_service()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


IndexDep = Annotated[InvertedIndex, Depends(get_index)]
RetrieverFactoryDep = Annotated[
    Callable[[float], ExtendedBoolean], Depends(get_retriever_factory)
]
DestinationsDep = Annotated[dict[str, dict[str, object]], Depends(get_destinations)]


def _build_destination_result(
    doc_id: str,
    score: float,
    destinations: dict[str, dict[str, object]],
    *,
    payload: dict[str, object] | None = None,
) -> DestinationResult:
    """Compose a ``DestinationResult`` merging SQLite metadata and an
    optional payload from Qdrant.

    Centralized so every endpoint surfaces popularity (T099) and
    fetched_at (T100) consistently without forgetting to wire one of
    them per branch.
    """
    meta = destinations.get(doc_id) or {}
    payload = payload or {}
    image_urls = list(payload.get("image_urls") or meta.get("image_urls") or [])
    return DestinationResult(
        id=doc_id,
        score=max(0.0, min(1.0, float(score))),
        name=payload.get("name") or meta.get("name"),
        country=payload.get("country") or meta.get("country"),
        description=meta.get("description"),
        image_urls=image_urls,
        popularity=meta.get("popularity"),
        fetched_at=meta.get("fetched_at"),
        latitude=meta.get("lat"),
        longitude=meta.get("lon"),
    )


@app.post("/search", response_model=SearchResponse)
def search(
    request: SearchRequest,
    index: IndexDep,
    retriever_factory: RetrieverFactoryDep,
    destinations: DestinationsDep,
) -> SearchResponse:
    """Busca destinos con el Booleano Extendido (p-norm) y los devuelve rankeados."""
    retriever = retriever_factory(request.p)
    # T127.2: when the query implies a location, over-fetch aggressively
    # (up to 200) so the geo filter has enough material to find the
    # correct destinations even when the lexical retriever ranks them
    # far down. Otherwise the default 3x over-fetch is enough.
    fetch_k = 200 if detect_countries(request.query) else max(request.top_k * 3, 30)
    hits = retriever.search(request.query, index, top_k=fetch_k)
    hits_with_country = [
        (doc_id, score, (destinations.get(doc_id) or {}).get("country"))
        for doc_id, score in hits
    ]
    filtered = apply_country_filter(
        hits_with_country, request.query, country_getter=lambda h: h[2]
    )
    results = [
        _build_destination_result(doc_id, score, destinations)
        for doc_id, score, _ in filtered[: request.top_k]
    ]
    return SearchResponse(results=results)


VectorStoreDep = Annotated[VectorStore, Depends(get_vector_store)]
EmbedderDep = Annotated[TextEmbedder, Depends(get_embedder)]
SemanticCollectionDep = Annotated[str, Depends(get_semantic_collection)]


@app.post("/search/semantic", response_model=SearchResponse)
def search_semantic(
    request: SemanticSearchRequest,
    store: VectorStoreDep,
    embedder: EmbedderDep,
    collection: SemanticCollectionDep,
    destinations: DestinationsDep,
) -> SearchResponse:
    """Búsqueda semántica (T053): embebe la query y consulta Qdrant directamente.

    T127: cuando la query menciona un país conocido del corpus
    ('playas en cuba'), filtra post-recuperación a destinos de ese país
    para evitar que un embedding con descripción rica de otro país
    domine el ranking.
    """
    # T127.2: when the query implies a location, over-fetch
    # aggressively (up to 200) because the dense retriever ranks short
    # destination descriptions (e.g. Varadero) far below long ones
    # with rich beach prose. Without a deep fetch, the geo filter has
    # nothing matching to keep.
    fetch_k = 200 if detect_countries(request.query) else max(request.top_k * 3, 30)
    try:
        # Explicit "query" mode prepends the prefix multilingual-e5-small
        # expects for short user input; matches how the corpus was
        # embedded with mode="passage".
        query_vector = embedder.embed(request.query, mode="query")
        raw_hits = store.search(collection, query_vector, top_k=fetch_k)
    except Exception as exc:  # pragma: no cover - delegado a middleware
        raise HTTPException(
            status_code=503,
            detail=f"Búsqueda semántica no disponible: {exc}",
        ) from exc

    filtered = filter_search_hits(raw_hits, request.query)
    results = [
        _build_destination_result(
            str(payload.get("slug") or point_id),
            float(score),
            destinations,
            payload=payload,
        )
        for point_id, score, payload in filtered[: request.top_k]
    ]
    return SearchResponse(results=results)


@app.post("/search/hybrid", response_model=SearchResponse)
def search_hybrid(
    request: HybridSearchRequest,
    index: IndexDep,
    store: VectorStoreDep,
    embedder: EmbedderDep,
    collection: SemanticCollectionDep,
    retriever_factory: RetrieverFactoryDep,
    destinations: DestinationsDep,
) -> SearchResponse:
    """Búsqueda híbrida (T055): Booleano Extendido + semántico con peso alpha.

    T127: aplica el geo filter post-merge para descartar destinos
    cuyo país no coincida con la query.
    """
    extended = retriever_factory(request.p)
    hybrid = HybridRetriever(
        extended=extended,
        embedder=embedder,
        store=store,
        collection=collection,
        alpha=request.alpha,
    )
    # T127.2: same aggressive over-fetch when the query has a location.
    fetch_k = 200 if detect_countries(request.query) else max(request.top_k * 3, 30)
    hits = hybrid.search(request.query, index, top_k=fetch_k)
    hits_with_country = [
        (doc_id, score, (destinations.get(doc_id) or {}).get("country"))
        for doc_id, score in hits
    ]
    filtered = apply_country_filter(
        hits_with_country, request.query, country_getter=lambda h: h[2]
    )
    results = [
        _build_destination_result(doc_id, score, destinations)
        for doc_id, score, _ in filtered[: request.top_k]
    ]
    return SearchResponse(results=results)


ClipEmbedderDep = Annotated[object, Depends(get_clip_embedder)]
ImageCollectionDep = Annotated[str, Depends(get_image_collection)]


@app.post("/search/image-by-text", response_model=ImageSearchResponse)
def search_image_by_text(
    request: ImageByTextRequest,
    clip: ClipEmbedderDep,
    store: VectorStoreDep,
    collection: ImageCollectionDep,
) -> ImageSearchResponse:
    """Búsqueda texto → imagen con CLIP (T084).

    Embebe la query con CLIP y recupera las imágenes más similares
    de la colección ``destinations_image``.
    """
    try:
        query_vector = clip.embed_text(request.query)
        hits = store.search(collection, query_vector, top_k=request.top_k)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Búsqueda imagen-por-texto no disponible: {exc}",
        ) from exc

    results = [
        ImageSearchResult(
            destination_id=str(payload.get("destination_id") or point_id),
            image_path=str(payload.get("image_path", "")),
            score=max(0.0, min(1.0, float(score))),
        )
        for point_id, score, payload in hits
    ]
    return ImageSearchResponse(results=results)


@app.post("/search/by-image", response_model=ImageSearchResponse)
async def search_by_image(
    clip: ClipEmbedderDep,
    store: VectorStoreDep,
    collection: ImageCollectionDep,
    file: Annotated[UploadFile, File(description="Imagen JPEG/PNG para buscar similares.")],
    top_k: int = 10,
) -> ImageSearchResponse:
    """Búsqueda imagen → destinos similares con CLIP (T085).

    Recibe una imagen subida, la embebe con CLIP y busca los destinos
    visualmente más similares en la colección ``destinations_image``.
    """
    import io
    import tempfile

    from PIL import Image

    data = await file.read()
    try:
        img = Image.open(io.BytesIO(data)).convert("RGB")
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Imagen inválida: {exc}") from exc

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        img.save(tmp.name, format="JPEG")
        tmp_path = tmp.name

    try:
        query_vector = clip.embed_image(tmp_path)
        hits = store.search(collection, query_vector, top_k=top_k)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Búsqueda por imagen no disponible: {exc}",
        ) from exc
    finally:
        import os

        os.unlink(tmp_path)

    results = [
        ImageSearchResult(
            destination_id=str(payload.get("destination_id") or point_id),
            image_path=str(payload.get("image_path", "")),
            score=max(0.0, min(1.0, float(score))),
        )
        for point_id, score, payload in hits
    ]
    return ImageSearchResponse(results=results)


@app.post("/search/multimodal", response_model=ImageSearchResponse)
def search_multimodal(
    request: MultimodalSearchRequest,
    clip: ClipEmbedderDep,
    store: VectorStoreDep,
    collection: ImageCollectionDep,
) -> ImageSearchResponse:
    """Búsqueda multimodal combinada: texto + imagen opcional (T088).

    Si se proporciona ``image_b64``, combina el embedding de texto y el de
    imagen con peso ``alpha`` antes de consultar Qdrant.
    Si no hay imagen, usa solo el embedding de texto (equivalente a T084).
    """
    import base64
    import io
    import tempfile

    from PIL import Image

    try:
        text_vector = clip.embed_text(request.query)

        if request.image_b64:
            img_bytes = base64.b64decode(request.image_b64)
            img = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                img.save(tmp.name, format="JPEG")
                tmp_path = tmp.name
            try:
                image_vector = clip.embed_image(tmp_path)
            finally:
                import os

                os.unlink(tmp_path)

            from src.multimodal.fusion import combine_vectors

            query_vector = combine_vectors(text_vector, image_vector, request.alpha)
        else:
            query_vector = text_vector

        hits = store.search(collection, query_vector, top_k=request.top_k)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Búsqueda multimodal no disponible: {exc}",
        ) from exc

    results = [
        ImageSearchResult(
            destination_id=str(payload.get("destination_id") or point_id),
            image_path=str(payload.get("image_path", "")),
            score=max(0.0, min(1.0, float(score))),
        )
        for point_id, score, payload in hits
    ]
    return ImageSearchResponse(results=results)


RagPipelineDep = Annotated["RagPipeline", Depends(get_rag_pipeline)]


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest, pipeline: RagPipelineDep) -> AskResponse:
    """Responde una pregunta en lenguaje natural usando RAG (T065)."""
    return pipeline.answer(
        request.query,
        top_k=request.top_k,
        mode=request.mode,
        alpha=request.alpha,
    )


RecommendationServiceDep = Annotated[object, Depends(get_recommendation_service)]


@app.post("/recommend", response_model=RecommendResponse)
def recommend(
    request: RecommendRequest,
    service: RecommendationServiceDep,
    destinations: DestinationsDep,
) -> RecommendResponse:
    """Recomienda destinos según el perfil del usuario (T096).

    Resuelve el perfil con :func:`build_request_profile` (combina
    perfiles sintéticos, intereses libres e historial) y dispara la
    estrategia seleccionada (`content`, `collaborative` o `hybrid`).
    """
    from src.recommendation.service import build_request_profile

    profile = build_request_profile(
        request.user_id,
        request.interests,
        request.history,
    )
    outcome = service.recommend(
        profile,
        top_k=request.top_k,
        mode=request.mode,
        alpha=request.alpha,
    )
    results = [
        _build_destination_result(doc_id, score, destinations, payload=payload)
        for doc_id, score, payload in outcome.hits
    ]
    return RecommendResponse(
        results=results, persona=outcome.persona, empty=outcome.empty
    )


@app.post("/feedback", response_model=FeedbackResponse)
def feedback(request: FeedbackRequest) -> FeedbackResponse:
    """Registra un voto de relevancia thumbs up/down (T118).

    Persiste tal cual en SQLite; los agregadores deciden cómo combinar
    los votos. El payload duplicado para el mismo (usuario, query,
    destino) está permitido para que el usuario pueda cambiar de opinión.
    """
    from fastapi import HTTPException

    from src.ingestion.feedback import VALID_VOTES, record_feedback

    if request.vote not in VALID_VOTES:
        raise HTTPException(
            status_code=422,
            detail=f"vote must be one of {VALID_VOTES}; got {request.vote}",
        )
    new_id = record_feedback(
        request.user_id,
        request.query,
        request.destination_id,
        request.vote,
    )
    return FeedbackResponse(id=new_id)


@app.post("/ask/stream")
def ask_stream(request: AskRequest, pipeline: RagPipelineDep) -> StreamingResponse:
    """Respuesta RAG en streaming SSE (T069).

    Emite eventos en el formato:
        data: <token>\\n\\n
        data: [DONE]\\n\\n
        data: {"sources": [...], "low_confidence": bool}\\n\\n
    """

    def _event_generator():
        for chunk in pipeline.answer_stream(
            request.query,
            top_k=request.top_k,
            mode=request.mode,
            alpha=request.alpha,
        ):
            yield f"data: {chunk}\n\n"

    return StreamingResponse(_event_generator(), media_type="text/event-stream")
