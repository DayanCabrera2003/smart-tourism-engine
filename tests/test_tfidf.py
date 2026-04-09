import math

import pytest

from src.indexing.inverted_index import InvertedIndex


@pytest.fixture
def index_two_docs():
    idx = InvertedIndex()
    idx.add_document("doc1", ["playa", "sol", "playa"])   # playa×2, sol×1
    idx.add_document("doc2", ["sol", "montana", "sol"])   # sol×2, montana×1
    idx.compute_tf_idf()
    return idx


def test_compute_tfidf_populates_weights(index_two_docs):
    postings = index_two_docs.get_tfidf_postings("sol")
    assert len(postings) == 2
    doc_ids = [p[0] for p in postings]
    assert "doc1" in doc_ids
    assert "doc2" in doc_ids


def test_tfidf_weights_are_positive(index_two_docs):
    for term in index_two_docs.vocabulary:
        for _, weight in index_two_docs.get_tfidf_postings(term):
            assert weight > 0


def test_tfidf_higher_tf_gives_higher_weight(index_two_docs):
    # En doc2, sol aparece 2 veces (TF=1.0) vs playa en doc1 (TF=1.0 también)
    # En doc1, sol aparece 1 vez (max=2) → TF=0.5
    postings = dict(index_two_docs.get_tfidf_postings("sol"))
    # doc2: TF(sol)=2/2=1.0 > doc1: TF(sol)=1/2=0.5
    assert postings["doc2"] > postings["doc1"]


def test_tfidf_term_in_all_docs_has_lower_idf():
    # "sol" aparece en ambos docs → IDF bajo
    # "playa" aparece solo en doc1 → IDF más alto
    idx = InvertedIndex()
    idx.add_document("doc1", ["playa", "sol"])
    idx.add_document("doc2", ["sol", "montana"])
    idx.compute_tf_idf()

    idf_sol = math.log(2 / 2) + 1      # log(1) + 1 = 1.0
    idf_playa = math.log(2 / 1) + 1    # log(2) + 1 ≈ 1.693

    postings_sol = dict(idx.get_tfidf_postings("sol"))
    postings_playa = dict(idx.get_tfidf_postings("playa"))

    # Con TF=1.0 para ambos: w = TF * IDF
    assert postings_playa["doc1"] == pytest.approx(1.0 * idf_playa)
    assert postings_sol["doc1"] == pytest.approx(1.0 * idf_sol)


def test_norms_are_positive(index_two_docs):
    assert index_two_docs.get_norm("doc1") > 0
    assert index_two_docs.get_norm("doc2") > 0


def test_norm_unknown_doc(index_two_docs):
    assert index_two_docs.get_norm("inexistente") == 0.0


def test_norm_is_l2(index_two_docs):
    # Verificar manualmente la norma de doc1
    weights = [w for _, w in index_two_docs.get_tfidf_postings("playa") if _ == "doc1"]
    weights += [w for _, w in index_two_docs.get_tfidf_postings("sol") if _ == "doc1"]
    expected = math.sqrt(sum(w**2 for w in weights))
    assert index_two_docs.get_norm("doc1") == pytest.approx(expected)


def test_get_tfidf_postings_unknown_term(index_two_docs):
    assert index_two_docs.get_tfidf_postings("inexistente") == []


def test_compute_tfidf_empty_index():
    idx = InvertedIndex()
    idx.compute_tf_idf()  # no debe lanzar excepción
    assert idx.get_tfidf_postings("sol") == []


def test_raw_postings_unchanged_after_tfidf(index_two_docs):
    # get_postings sigue devolviendo TF crudo
    postings = dict(index_two_docs.get_postings("playa"))
    assert postings["doc1"] == 2
