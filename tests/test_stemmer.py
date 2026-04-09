import pytest
from src.indexing.stemmer import stem, stem_token


def test_stem_token_spanish_default():
    assert stem_token("turismo") == "turism"
    assert stem_token("corriendo") == "corr"
    assert stem_token("playas") == "play"


def test_stem_token_english():
    assert stem_token("tourism", language="english") == "tourism"
    assert stem_token("running", language="english") == "run"
    assert stem_token("beaches", language="english") == "beach"


def test_stem_token_preserves_already_stemmed():
    # Aplicar dos veces debe dar el mismo resultado (idempotente)
    token = "turismo"
    once = stem_token(token)
    twice = stem_token(once)
    assert once == twice


def test_stem_list_spanish():
    tokens = ["turismo", "playas", "hoteles", "restaurantes"]
    result = stem(tokens)
    assert result == ["turism", "play", "hotel", "restaur"]


def test_stem_list_english():
    tokens = ["tourism", "beaches", "hotels", "restaurants"]
    result = stem(tokens, language="english")
    assert result == ["tourism", "beach", "hotel", "restaur"]


def test_stem_empty_list():
    assert stem([]) == []


def test_stem_single_token():
    assert stem(["museo"]) == ["muse"]


def test_stem_invalid_language():
    with pytest.raises(Exception):
        stem_token("hola", language="klingon")


def test_stem_list_preserves_length():
    tokens = ["viaje", "aventura", "cultura", "gastronomia"]
    result = stem(tokens)
    assert len(result) == len(tokens)
