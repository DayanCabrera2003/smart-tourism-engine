"""T029 — Persistencia del índice invertido (save / load)."""
import pytest

from src.indexing.inverted_index import InvertedIndex


@pytest.fixture
def populated_index():
    idx = InvertedIndex()
    idx.add_document("doc1", ["playa", "sol", "playa"])
    idx.add_document("doc2", ["sol", "montana", "sol"])
    idx.compute_tf_idf()
    return idx


def test_save_creates_file(tmp_path, populated_index):
    path = tmp_path / "index.pkl"
    populated_index.save(path)
    assert path.exists()


def test_load_restores_doc_count(tmp_path, populated_index):
    path = tmp_path / "index.pkl"
    populated_index.save(path)
    loaded = InvertedIndex.load(path)
    assert loaded.doc_count == populated_index.doc_count


def test_load_restores_raw_postings(tmp_path, populated_index):
    path = tmp_path / "index.pkl"
    populated_index.save(path)
    loaded = InvertedIndex.load(path)
    assert loaded.get_postings("playa") == populated_index.get_postings("playa")
    assert loaded.get_postings("sol") == populated_index.get_postings("sol")


def test_load_restores_tfidf_postings(tmp_path, populated_index):
    path = tmp_path / "index.pkl"
    populated_index.save(path)
    loaded = InvertedIndex.load(path)
    assert loaded.get_tfidf_postings("sol") == pytest.approx(
        populated_index.get_tfidf_postings("sol")
    )


def test_load_restores_norms(tmp_path, populated_index):
    path = tmp_path / "index.pkl"
    populated_index.save(path)
    loaded = InvertedIndex.load(path)
    assert loaded.get_norm("doc1") == pytest.approx(populated_index.get_norm("doc1"))
    assert loaded.get_norm("doc2") == pytest.approx(populated_index.get_norm("doc2"))


def test_load_restores_vocabulary(tmp_path, populated_index):
    path = tmp_path / "index.pkl"
    populated_index.save(path)
    loaded = InvertedIndex.load(path)
    assert loaded.vocabulary == populated_index.vocabulary


def test_load_nonexistent_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        InvertedIndex.load(tmp_path / "no_existe.pkl")


def test_save_index_without_tfidf(tmp_path):
    """Un índice sin compute_tf_idf() también debe persistir correctamente."""
    idx = InvertedIndex()
    idx.add_document("doc1", ["turismo"])
    path = tmp_path / "index.pkl"
    idx.save(path)
    loaded = InvertedIndex.load(path)
    assert loaded.get_postings("turismo") == [("doc1", 1)]
    assert loaded.get_tfidf_postings("turismo") == []
