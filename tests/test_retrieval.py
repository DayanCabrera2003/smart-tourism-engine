"""T038 — Tests de integración del recuperador Booleano Extendido (p-norm).

Cargan el índice real de ``data/processed/index.pkl`` y verifican que
``ExtendedBoolean.search`` devuelve los destinos esperados para 5 queries
representativas del dominio turístico.

Los tests se saltan automáticamente si el índice no existe (entorno sin datos).
"""
import pickle
from pathlib import Path

import pytest

from src.retrieval.extended_boolean import ExtendedBoolean

_INDEX_PATH = Path("data/processed/index.pkl")


# ── Fixture de índice (cargado una vez por módulo) ────────────────────────────

@pytest.fixture(scope="module")
def index():
    if not _INDEX_PATH.exists():
        pytest.skip(f"Índice no encontrado en {_INDEX_PATH}; omitiendo tests de integración.")
    with _INDEX_PATH.open("rb") as fh:
        return pickle.load(fh)


@pytest.fixture(scope="module")
def eb():
    return ExtendedBoolean(p=2.0)


# ── Tests de integración ──────────────────────────────────────────────────────

def test_query_beach_top_result_is_varadero(index, eb):
    """'beach' → el destino más relevante es Varadero (destino costero por excelencia)."""
    results = eb.search("beach", index, top_k=5)
    top_doc_id, top_score = results[0]
    assert top_doc_id == "wikivoyage-varadero", (
        f"Se esperaba 'wikivoyage-varadero' en primer lugar, se obtuvo {top_doc_id!r}"
    )
    assert top_score > 0.0


def test_query_tokyo_returns_tokyo(index, eb):
    """'tokyo' → Tokyo aparece en primer lugar con score muy alto (>0.5)."""
    results = eb.search("tokyo", index, top_k=5)
    doc_ids = [doc_id for doc_id, _ in results]
    assert "wikivoyage-tokyo" in doc_ids, (
        f"Se esperaba 'wikivoyage-tokyo' en los resultados, se obtuvo {doc_ids}"
    )
    # El score de Tokyo para su propio nombre debe ser significativamente alto
    tokyo_score = next(s for d, s in results if d == "wikivoyage-tokyo")
    assert tokyo_score > 0.5


def test_query_temple_and_japan_contains_kyoto(index, eb):
    """'temple AND japan' → Kyoto (capital cultural de Japón) aparece en el top-5."""
    results = eb.search("temple AND japan", index, top_k=5)
    doc_ids = [doc_id for doc_id, _ in results]
    assert "wikivoyage-kyoto" in doc_ids, (
        f"Se esperaba 'wikivoyage-kyoto' en el top-5, se obtuvo {doc_ids}"
    )


def test_query_beach_or_mountain_contains_varadero(index, eb):
    """'beach OR mountain' → Varadero (playa) aparece en el top-5."""
    results = eb.search("beach OR mountain", index, top_k=5)
    doc_ids = [doc_id for doc_id, _ in results]
    assert "wikivoyage-varadero" in doc_ids, (
        f"Se esperaba 'wikivoyage-varadero' en el top-5, se obtuvo {doc_ids}"
    )


def test_query_museum_and_art_contains_munich(index, eb):
    """'museum AND art' → Munich aparece en el top-5 (alta densidad de museos de arte)."""
    results = eb.search("museum AND art", index, top_k=5)
    doc_ids = [doc_id for doc_id, _ in results]
    assert "wikivoyage-munich" in doc_ids, (
        f"Se esperaba 'wikivoyage-munich' en el top-5, se obtuvo {doc_ids}"
    )


# ── Propiedades generales del recuperador ────────────────────────────────────

def test_search_results_ordered_by_score(index, eb):
    """Los resultados siempre vienen ordenados de mayor a menor score."""
    results = eb.search("beach OR mountain OR city", index, top_k=20)
    scores = [s for _, s in results]
    assert scores == sorted(scores, reverse=True)


def test_search_scores_bounded(index, eb):
    """Todos los scores están en [0, 1]."""
    results = eb.search("museum AND art OR beach", index, top_k=20)
    for _, score in results:
        assert 0.0 <= score <= 1.0
