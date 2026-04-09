"""T031 — Modelo Booleano clásico: AND, OR, NOT."""
import pytest

from src.indexing.inverted_index import InvertedIndex
from src.indexing.preprocess import preprocess
from src.retrieval.boolean import boolean_query


@pytest.fixture
def index():
    """
    Índice de prueba con 4 documentos en inglés (mismo pipeline que producción).

    doc1: beach sun tourism
    doc2: mountain snow tourism
    doc3: beach mountain hiking
    doc4: city museum tourism art
    """
    idx = InvertedIndex()
    idx.add_document("doc1", preprocess("beach sun tourism", language="english"))
    idx.add_document("doc2", preprocess("mountain snow tourism", language="english"))
    idx.add_document("doc3", preprocess("beach mountain hiking", language="english"))
    idx.add_document("doc4", preprocess("city museum tourism art", language="english"))
    return idx


# ── Single term ──────────────────────────────────────────────────────────────

def test_single_term_match(index):
    result = boolean_query("beach", index)
    assert set(result) == {"doc1", "doc3"}


def test_single_term_no_match(index):
    result = boolean_query("desert", index)
    assert result == []


# ── OR ───────────────────────────────────────────────────────────────────────

def test_or_returns_union(index):
    result = boolean_query("sun OR snow", index)
    assert set(result) == {"doc1", "doc2"}


def test_or_with_common_term(index):
    result = boolean_query("beach OR mountain", index)
    assert set(result) == {"doc1", "doc2", "doc3"}


# ── AND ──────────────────────────────────────────────────────────────────────

def test_and_returns_intersection(index):
    result = boolean_query("beach AND tourism", index)
    assert set(result) == {"doc1"}


def test_and_empty_intersection(index):
    result = boolean_query("sun AND snow", index)
    assert result == []


def test_and_three_terms(index):
    result = boolean_query("beach AND mountain AND hiking", index)
    assert set(result) == {"doc3"}


# ── NOT ──────────────────────────────────────────────────────────────────────

def test_not_excludes_term(index):
    result = boolean_query("tourism AND NOT beach", index)
    assert set(result) == {"doc2", "doc4"}


def test_not_single_excludes_from_all(index):
    result = boolean_query("NOT tourism", index)
    assert set(result) == {"doc3"}


# ── Preprocessing ─────────────────────────────────────────────────────────────

def test_query_terms_are_preprocessed(index):
    """Palabras en plural/variante se stemizán al mismo token que el índice."""
    # "beaches" → stem inglés → "beach" → debe encontrar doc1 y doc3
    result = boolean_query("beaches", index)
    assert set(result) == {"doc1", "doc3"}


# ── Edge cases ────────────────────────────────────────────────────────────────

def test_result_is_sorted(index):
    result = boolean_query("tourism", index)
    assert result == sorted(result)


def test_empty_query_returns_empty(index):
    result = boolean_query("", index)
    assert result == []
