"""T064 — Tests del pipeline RAG basico."""
from __future__ import annotations

import math

from src.api.schemas import DestinationResult
from src.indexing.embed_destinations import slug_to_uuid
from src.indexing.inverted_index import InvertedIndex
from src.indexing.vector_store import VectorStore
from src.rag.pipeline import RagPipeline

DIM = 4
COLLECTION = "test_rag_col"


class _StubEmbedder:
    VECTORS = {
        "playa": [1.0, 0.0, 0.0, 0.0],
        "museo": [0.0, 1.0, 0.0, 0.0],
        "montana": [0.0, 0.0, 1.0, 0.0],
    }

    def embed(self, text: str) -> list[float]:
        key = text.strip().lower()
        vec = self.VECTORS.get(key)
        if vec:
            return list(vec)
        raw = [float((ord(c) % 7) + 1) for c in (key or "x")[:DIM]]
        raw.extend([0.0] * (DIM - len(raw)))
        norm = math.sqrt(sum(v * v for v in raw)) or 1.0
        return [v / norm for v in raw]


class _StubLLM:
    def __init__(self, response: str = "Respuesta de prueba [1].") -> None:
        self._response = response

    def generate(self, prompt: str) -> str:
        return self._response

    def generate_stream(self, prompt: str):
        yield self._response


def _build_index() -> InvertedIndex:
    index = InvertedIndex()
    index.add_document("doc-playa", ["playa", "arena", "mar"])
    index.add_document("doc-museo", ["museo", "arte", "ciudad"])
    index.add_document("doc-montana", ["montana", "nieve", "senderismo"])
    index.compute_tf_idf()
    return index


def _build_store() -> VectorStore:
    store = VectorStore(url=":memory:")
    store.create_collection(COLLECTION, vector_size=DIM)
    emb = _StubEmbedder()
    points = [
        (slug_to_uuid("doc-playa"), emb.embed("playa"), {"slug": "doc-playa"}),
        (slug_to_uuid("doc-museo"), emb.embed("museo"), {"slug": "doc-museo"}),
        (slug_to_uuid("doc-montana"), emb.embed("montana"), {"slug": "doc-montana"}),
    ]
    store.upsert(COLLECTION, points)
    return store


_DESTINATIONS = {
    "doc-playa": {
        "name": "Ibiza",
        "country": "Espana",
        "description": "Isla con playas.",
        "image_urls": [],
    },
    "doc-museo": {
        "name": "Madrid",
        "country": "Espana",
        "description": "Ciudad con museos.",
        "image_urls": [],
    },
    "doc-montana": {
        "name": "Picos de Europa",
        "country": "Espana",
        "description": "Montana y naturaleza.",
        "image_urls": [],
    },
}


def _make_pipeline(llm_response: str = "Respuesta [1].") -> RagPipeline:
    return RagPipeline(
        index=_build_index(),
        embedder=_StubEmbedder(),
        store=_build_store(),
        collection=COLLECTION,
        destinations=_DESTINATIONS,
        llm=_StubLLM(llm_response),
    )


def test_answer_returns_answer_string():
    pipeline = _make_pipeline()
    result = pipeline.answer("playa", top_k=3)
    assert isinstance(result.answer, str)
    assert len(result.answer) > 0


def test_answer_returns_sources():
    pipeline = _make_pipeline()
    result = pipeline.answer("playa", top_k=3)
    assert len(result.sources) > 0


def test_sources_are_destination_results():
    pipeline = _make_pipeline()
    result = pipeline.answer("museo", top_k=3)
    for src in result.sources:
        assert isinstance(src, DestinationResult)
        assert 0.0 <= src.score <= 1.0


def test_answer_cached_false_on_first_call():
    pipeline = _make_pipeline()
    result = pipeline.answer("playa", top_k=3)
    assert result.cached is False
