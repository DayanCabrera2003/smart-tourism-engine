"""T080 — Tests de integracion del fallback web en RagPipeline."""
from __future__ import annotations

import math

from src.indexing.embed_destinations import slug_to_uuid
from src.indexing.inverted_index import InvertedIndex
from src.indexing.vector_store import VectorStore
from src.rag.pipeline import RagPipeline
from src.web_search.tavily import WebResult

DIM = 4
COLLECTION = "test_fallback_col"


class _StubEmbedder:
    def embed(self, text: str) -> list[float]:
        raw = [float((ord(c) % 7) + 1) for c in (text or "x")[:DIM]]
        raw.extend([0.0] * (DIM - len(raw)))
        norm = math.sqrt(sum(v * v for v in raw)) or 1.0
        return [v / norm for v in raw]


class _StubLLM:
    def generate(self, prompt: str) -> str:
        return "Respuesta de prueba."

    def generate_stream(self, prompt: str):
        yield "Respuesta de prueba."


class _StubTavilyOk:
    """Tavily que siempre devuelve un resultado valido."""

    def search(self, query: str, *, max_results: int = 5) -> list[WebResult]:
        return [
            WebResult(
                title="Destino Web",
                snippet="Descripcion desde la web.",
                url="https://example.com/destino-web",
            )
        ]


class _StubTavilyRateLimited:
    """Tavily que simula rate limit agotado."""

    def search(self, query: str, *, max_results: int = 5) -> list[WebResult]:
        raise RuntimeError("Tavily rate limit alcanzado. Intenta de nuevo en un minuto.")


def _build_index_empty() -> InvertedIndex:
    index = InvertedIndex()
    index.compute_tf_idf()
    return index


def _build_store_empty() -> VectorStore:
    store = VectorStore(url=":memory:")
    store.create_collection(COLLECTION, vector_size=DIM)
    return store


def _make_pipeline(tavily) -> RagPipeline:
    return RagPipeline(
        index=_build_index_empty(),
        embedder=_StubEmbedder(),
        store=_build_store_empty(),
        collection=COLLECTION,
        destinations={},
        llm=_StubLLM(),
        web_client=tavily,
    )


def test_fallback_triggered_when_no_local_results():
    """Con indice vacio, el pipeline activa el fallback y devuelve fuentes web."""
    pipeline = _make_pipeline(_StubTavilyOk())
    result = pipeline.answer("query rara que no existe", top_k=3)
    assert len(result.sources) > 0


def test_fallback_source_has_from_web_true():
    """Los resultados venidos de Tavily tienen from_web=True."""
    pipeline = _make_pipeline(_StubTavilyOk())
    result = pipeline.answer("query web", top_k=3)
    web_sources = [s for s in result.sources if s.from_web]
    assert len(web_sources) > 0


def test_fallback_not_triggered_without_web_client():
    """Sin web_client configurado, no se activa fallback."""
    pipeline = RagPipeline(
        index=_build_index_empty(),
        embedder=_StubEmbedder(),
        store=_build_store_empty(),
        collection=COLLECTION,
        destinations={},
        llm=_StubLLM(),
        web_client=None,
    )
    result = pipeline.answer("query", top_k=3)
    assert all(not s.from_web for s in result.sources)


def test_fallback_rate_limited_graceful_degradation():
    """Si el rate limit esta agotado, el pipeline responde sin fuentes web."""
    pipeline = _make_pipeline(_StubTavilyRateLimited())
    result = pipeline.answer("query", top_k=3)
    assert result.answer != ""


def test_fallback_result_name_is_tavily_title():
    """El nombre del resultado web es el titulo de Tavily."""
    pipeline = _make_pipeline(_StubTavilyOk())
    result = pipeline.answer("query web", top_k=3)
    web_src = next((s for s in result.sources if s.from_web), None)
    assert web_src is not None
    assert web_src.name == "Destino Web"


def test_fallback_does_not_trigger_when_scores_are_high():
    """Con hits de score alto, no se llama a Tavily (score por encima del umbral)."""

    class _SpyTavily:
        called = False

        def search(self, query: str, *, max_results: int = 5) -> list[WebResult]:
            _SpyTavily.called = True
            return []

    index = InvertedIndex()
    index.add_document("doc-playa", ["playa", "arena"])
    index.compute_tf_idf()

    store = VectorStore(url=":memory:")
    store.create_collection(COLLECTION, vector_size=DIM)
    emb = _StubEmbedder()
    store.upsert(
        COLLECTION,
        [(slug_to_uuid("doc-playa"), emb.embed("playa"), {"slug": "doc-playa"})],
    )

    pipeline = RagPipeline(
        index=index,
        embedder=emb,
        store=store,
        collection=COLLECTION,
        destinations={
            "doc-playa": {
                "name": "Ibiza",
                "country": "Espana",
                "description": "Isla",
                "image_urls": [],
            }
        },
        llm=_StubLLM(),
        web_client=_SpyTavily(),
    )

    pipeline.answer("playa", top_k=3)
    assert _SpyTavily.called is False
