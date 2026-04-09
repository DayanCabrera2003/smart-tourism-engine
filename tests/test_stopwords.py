from src.indexing.stopwords import STOPWORDS, remove_stopwords


def test_stopwords_loaded():
    assert len(STOPWORDS) > 0


def test_stopwords_contains_spanish():
    # Palabras funcionales típicas del español
    assert "de" in STOPWORDS
    assert "la" in STOPWORDS
    assert "en" in STOPWORDS
    assert "que" in STOPWORDS
    assert "es" in STOPWORDS


def test_stopwords_contains_english():
    # Palabras funcionales típicas del inglés
    assert "the" in STOPWORDS
    assert "is" in STOPWORDS
    assert "in" in STOPWORDS
    assert "and" in STOPWORDS
    assert "of" in STOPWORDS


def test_remove_stopwords_basic():
    tokens = ["el", "turismo", "en", "espana", "es", "bonito"]
    result = remove_stopwords(tokens)
    assert "turismo" in result
    assert "espana" in result
    assert "bonito" in result
    assert "el" not in result
    assert "en" not in result
    assert "es" not in result


def test_remove_stopwords_english():
    tokens = ["the", "tourism", "in", "spain", "is", "great"]
    result = remove_stopwords(tokens)
    assert "tourism" in result
    assert "spain" in result
    assert "great" in result
    assert "the" not in result
    assert "in" not in result
    assert "is" not in result


def test_remove_stopwords_empty():
    assert remove_stopwords([]) == []


def test_remove_stopwords_all_stopwords():
    tokens = ["de", "la", "en", "the", "is", "and"]
    assert remove_stopwords(tokens) == []


def test_remove_stopwords_no_stopwords():
    tokens = ["turismo", "playa", "montagna", "hotel"]
    assert remove_stopwords(tokens) == tokens


def test_remove_stopwords_preserves_order():
    tokens = ["museo", "de", "arte", "moderno"]
    result = remove_stopwords(tokens)
    assert result == ["museo", "arte", "moderno"]
