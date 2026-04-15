"""T054 — Tests del recuperador híbrido (Booleano Extendido + semántico)."""
from __future__ import annotations

import math

import pytest

from src.indexing.embed_destinations import slug_to_uuid
from src.indexing.inverted_index import InvertedIndex
from src.indexing.vector_store import VectorStore
from src.retrieval.extended_boolean import ExtendedBoolean
from src.retrieval.hybrid import HybridRetriever

COLLECTION = "destinations_text_test"
DIM = 4


class _StubEmbedder:
    """Embedder determinista: vector unitario por slug conocido."""

    VECTORS: dict[str, list[float]] = {
        "beach": [1.0, 0.0, 0.0, 0.0],
        "mountain": [0.0, 1.0, 0.0, 0.0],
        "city": [0.0, 0.0, 1.0, 0.0],
        "temple": [0.0, 0.0, 0.0, 1.0],
    }

    def embed(self, text: str) -> list[float]:
        key = text.strip().lower()
        if key in self.VECTORS:
            return list(self.VECTORS[key])
        raw = [float((ord(c) % 7) + 1) for c in (key or "x")[:DIM]]
        raw.extend([0.0] * (DIM - len(raw)))
        norm = math.sqrt(sum(v * v for v in raw)) or 1.0
        return [v / norm for v in raw]


def _build_index() -> InvertedIndex:
    """Índice invertido con 4 documentos, tokens pre-stemizados."""
    index = InvertedIndex()
    # beach solo en doc-beach; mountain solo en doc-mountain; etc.
    index.add_document("doc-beach", ["beach", "sand", "sea"])
    index.add_document("doc-mountain", ["mountain", "snow", "hike"])
    index.add_document("doc-city", ["city", "museum", "art"])
    # doc-extra solo aparece en el índice léxico (no en el store semántico)
    index.add_document("doc-extra", ["beach", "resort"])
    index.compute_tf_idf()
    return index


def _build_store() -> VectorStore:
    """Store Qdrant en memoria con 4 puntos.  doc-orphan NO está en el índice."""
    store = VectorStore(url=":memory:")
    store.create_collection(COLLECTION, vector_size=DIM)
    embedder = _StubEmbedder()
    points = [
        (slug_to_uuid("doc-beach"), embedder.embed("beach"), {"slug": "doc-beach"}),
        (slug_to_uuid("doc-mountain"), embedder.embed("mountain"), {"slug": "doc-mountain"}),
        (slug_to_uuid("doc-city"), embedder.embed("city"), {"slug": "doc-city"}),
        # Este documento aparece solo en la rama semántica
        (slug_to_uuid("doc-orphan"), embedder.embed("temple"), {"slug": "doc-orphan"}),
    ]
    store.upsert(COLLECTION, points)
    return store


def _make_hybrid(alpha: float = 0.5) -> HybridRetriever:
    return HybridRetriever(
        extended=ExtendedBoolean(p=2.0),
        embedder=_StubEmbedder(),
        store=_build_store(),
        collection=COLLECTION,
        alpha=alpha,
    )


# ── Validación de alpha ────────────────────────────────────────────────────────

def test_alpha_default_is_half():
    h = HybridRetriever(
        extended=ExtendedBoolean(),
        embedder=_StubEmbedder(),
        store=_build_store(),
        collection=COLLECTION,
    )
    assert h.alpha == 0.5


def test_alpha_below_zero_raises():
    with pytest.raises(ValueError):
        _make_hybrid(alpha=-0.01)


def test_alpha_above_one_raises():
    with pytest.raises(ValueError):
        _make_hybrid(alpha=1.01)


def test_alpha_zero_and_one_are_valid():
    _make_hybrid(alpha=0.0)
    _make_hybrid(alpha=1.0)


# ── Fusión de rankings ────────────────────────────────────────────────────────

def test_alpha_one_matches_extended_boolean_only():
    """α=1.0 → ignora la rama semántica; el orden coincide con el léxico."""
    index = _build_index()
    hybrid = _make_hybrid(alpha=1.0)
    bool_ranking = ExtendedBoolean(p=2.0).search("beach", index, top_k=10)
    hybrid_ranking = hybrid.search("beach", index, top_k=10)

    bool_ids = [d for d, _ in bool_ranking]
    hybrid_ids = [d for d, _ in hybrid_ranking]
    # doc-orphan NO debe aparecer: solo vive en el store semántico.
    assert "doc-orphan" not in hybrid_ids
    # Los docs léxicos deben estar presentes en el mismo orden.
    assert [d for d in hybrid_ids if d in bool_ids] == bool_ids


def test_alpha_zero_matches_semantic_only():
    """α=0.0 → ignora la rama léxica; el top-1 es el más cercano semánticamente."""
    index = _build_index()
    hybrid = _make_hybrid(alpha=0.0)
    results = hybrid.search("mountain", index, top_k=3)
    assert results[0][0] == "doc-mountain"
    assert results[0][1] > 0.99


def test_hybrid_combines_both_rankings():
    """α intermedio mezcla ambos: doc-beach gana por aparecer en las dos ramas."""
    index = _build_index()
    hybrid = _make_hybrid(alpha=0.5)
    results = hybrid.search("beach", index, top_k=10)
    assert results[0][0] == "doc-beach"
    # doc-beach debe superar a doc-orphan (que solo vive en la rama semántica).
    scores = dict(results)
    assert "doc-beach" in scores
    if "doc-orphan" in scores:
        assert scores["doc-beach"] > scores["doc-orphan"]


def test_hybrid_includes_docs_only_in_semantic_branch():
    """Un doc presente solo en el store semántico contribuye con (1-α)*score."""
    index = _build_index()
    hybrid = _make_hybrid(alpha=0.5)
    results = hybrid.search("temple", index, top_k=5)
    ids = [d for d, _ in results]
    assert "doc-orphan" in ids


def test_hybrid_includes_docs_only_in_lexical_branch():
    """Un doc presente solo en el índice léxico contribuye con α*score."""
    index = _build_index()
    hybrid = _make_hybrid(alpha=1.0)  # ignorar semántica para aislar la rama léxica
    results = hybrid.search("resort", index, top_k=5)
    ids = [d for d, _ in results]
    assert "doc-extra" in ids


# ── Forma de la salida ────────────────────────────────────────────────────────

def test_results_ordered_by_score_desc():
    index = _build_index()
    hybrid = _make_hybrid(alpha=0.5)
    results = hybrid.search("beach", index, top_k=10)
    scores = [s for _, s in results]
    assert scores == sorted(scores, reverse=True)


def test_respects_top_k():
    index = _build_index()
    hybrid = _make_hybrid(alpha=0.5)
    results = hybrid.search("beach", index, top_k=2)
    assert len(results) == 2


def test_scores_clamped_to_unit_interval():
    index = _build_index()
    hybrid = _make_hybrid(alpha=0.5)
    results = hybrid.search("beach", index, top_k=10)
    for _doc_id, score in results:
        assert 0.0 <= score <= 1.0
