from src.indexing.preprocess import preprocess


def test_preprocess_basic_spanish():
    result = preprocess("El turismo en España es bonito")
    assert "turism" in result
    assert "bonit" in result
    # stopwords eliminadas
    assert "el" not in result
    assert "en" not in result
    assert "es" not in result


def test_preprocess_basic_english():
    result = preprocess("The tourism in Spain is beautiful", language="english")
    assert "tourism" in result
    assert "spain" in result
    assert "beauti" in result
    # stopwords eliminadas
    assert "the" not in result
    assert "in" not in result
    assert "is" not in result


def test_preprocess_empty():
    assert preprocess("") == []
    assert preprocess("   ") == []


def test_preprocess_only_stopwords():
    assert preprocess("el de la en") == []


def test_preprocess_punctuation_and_accents():
    result = preprocess("¡Playas hermosas de España!")
    assert "play" in result
    assert "herm" in result  # stem de "hermosas"
    # "de" es stopword
    assert "de" not in result
    # "españa" → "espan" tras stemming
    assert "espan" in result


def test_preprocess_stemming_reduces_tokens():
    # "turismo" y "turista" reducen a stems distintos pero más cortos que el original
    result1 = preprocess("turismo")
    result2 = preprocess("turista")
    assert result1 == ["turism"]
    assert result2 == ["turist"]


def test_preprocess_pipeline_order():
    # Asegurar que stopwords se eliminan antes del stemming
    # "de" es stopword; si no se elimina antes del stem quedaría "de"
    result = preprocess("museo de arte")
    assert "de" not in result
    assert "muse" in result
    assert "arte" in result  # "arte" no cambia con Snowball español


def test_preprocess_numbers_preserved():
    result = preprocess("hotel 5 estrellas")
    assert "5" in result
