import pytest

from src.indexing.inverted_index import InvertedIndex


@pytest.fixture
def index():
    return InvertedIndex()


def test_add_and_get_single_doc(index):
    index.add_document("doc1", ["playa", "sol", "playa"])
    postings = index.get_postings("playa")
    assert postings == [("doc1", 2)]


def test_get_postings_unknown_term(index):
    assert index.get_postings("inexistente") == []


def test_multiple_docs_same_term(index):
    index.add_document("doc1", ["turismo", "playa"])
    index.add_document("doc2", ["turismo", "montana"])
    index.add_document("doc3", ["playa", "playa", "turismo"])
    postings = index.get_postings("turismo")
    assert ("doc1", 1) in postings
    assert ("doc2", 1) in postings
    assert ("doc3", 1) in postings
    assert len(postings) == 3


def test_frequency_count(index):
    index.add_document("doc1", ["sol", "sol", "sol"])
    postings = index.get_postings("sol")
    assert postings == [("doc1", 3)]


def test_postings_sorted_by_doc_id(index):
    index.add_document("doc3", ["mar"])
    index.add_document("doc1", ["mar"])
    index.add_document("doc2", ["mar"])
    postings = index.get_postings("mar")
    doc_ids = [p[0] for p in postings]
    assert doc_ids == sorted(doc_ids)


def test_doc_count(index):
    assert index.doc_count == 0
    index.add_document("doc1", ["a"])
    index.add_document("doc2", ["b"])
    assert index.doc_count == 2


def test_vocabulary(index):
    index.add_document("doc1", ["playa", "sol"])
    index.add_document("doc2", ["montana", "sol"])
    assert index.vocabulary == {"playa", "sol", "montana"}


def test_len(index):
    assert len(index) == 0
    index.add_document("doc1", ["playa", "sol"])
    assert len(index) == 2


def test_contains(index):
    index.add_document("doc1", ["turismo"])
    assert "turismo" in index
    assert "playa" not in index


def test_empty_tokens(index):
    index.add_document("doc1", [])
    assert index.doc_count == 1
    assert len(index) == 0


def test_add_document_twice_same_id(index):
    index.add_document("doc1", ["playa"])
    index.add_document("doc1", ["playa", "sol"])
    # La segunda llamada sobreescribe la frecuencia del doc1 para "playa"
    postings = index.get_postings("playa")
    assert ("doc1", 1) in postings
    assert ("doc1", 2) not in postings
