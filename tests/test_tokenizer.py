from src.indexing.tokenizer import tokenize


def test_tokenize_basic():
    assert tokenize("hola mundo") == ["hola", "mundo"]


def test_tokenize_empty():
    assert tokenize("") == []
    assert tokenize("   ") == []


def test_tokenize_punctuation():
    assert tokenize("hola, mundo!") == ["hola", "mundo"]
    assert tokenize("¡España es bonita!") == ["espana", "es", "bonita"]
    assert tokenize("un-guión y punto.final") == ["un", "guion", "y", "punto", "final"]


def test_tokenize_accents():
    assert tokenize("España") == ["espana"]
    assert tokenize("árbol genealógico") == ["arbol", "genealogico"]
    assert tokenize("Ñoño") == ["nono"]
    assert tokenize("ü ö ä") == ["u", "o", "a"]


def test_tokenize_uppercase():
    assert tokenize("HOLA MUNDO") == ["hola", "mundo"]
    assert tokenize("Madrid") == ["madrid"]


def test_tokenize_mixed_punctuation_and_accents():
    assert tokenize("¿Cómo está todo?") == ["como", "esta", "todo"]
    assert tokenize("Café, té y más...") == ["cafe", "te", "y", "mas"]


def test_tokenize_numbers():
    assert tokenize("hotel 5 estrellas") == ["hotel", "5", "estrellas"]
    assert tokenize("año 2024") == ["ano", "2024"]


def test_tokenize_multiple_spaces():
    assert tokenize("hola   mundo") == ["hola", "mundo"]
    assert tokenize("\thola\nmundo\r") == ["hola", "mundo"]


def test_tokenize_only_punctuation():
    assert tokenize("!!! ???") == []
    assert tokenize("...---...") == []


def test_tokenize_single_word():
    assert tokenize("turismo") == ["turismo"]
    assert tokenize("TURISMO") == ["turismo"]
