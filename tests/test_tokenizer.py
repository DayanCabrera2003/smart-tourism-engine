from src.indexing.tokenizer import tokenize


def test_tokenize_basic():
    assert tokenize("hola mundo") == ["hola", "mundo"]


def test_tokenize_empty():
    assert tokenize("") == []
    assert tokenize("   ") == []


def test_tokenize_punctuation():
    assert tokenize("hola, mundo!") == ["hola", "mundo"]
    assert tokenize("¡España es bonita!") == ["espana", "es", "bonita"]
    # Single-character "y" is dropped as junk (it is also a Spanish
    # stopword, so removing it earlier saves work downstream).
    assert tokenize("un-guión y punto.final") == ["un", "guion", "punto", "final"]


def test_tokenize_accents():
    assert tokenize("España") == ["espana"]
    assert tokenize("árbol genealógico") == ["arbol", "genealogico"]
    assert tokenize("Ñoño") == ["nono"]
    # Single-character tokens are filtered out as junk.
    assert tokenize("ü ö ä") == []


def test_tokenize_uppercase():
    assert tokenize("HOLA MUNDO") == ["hola", "mundo"]
    assert tokenize("Madrid") == ["madrid"]


def test_tokenize_mixed_punctuation_and_accents():
    assert tokenize("¿Cómo está todo?") == ["como", "esta", "todo"]
    # "y" is dropped as a single-character token.
    assert tokenize("Café, té y más...") == ["cafe", "te", "mas"]


def test_tokenize_numbers():
    # Pure-digit tokens are dropped. They appear ~96 times in the legacy
    # vocabulary (years, hotel ratings, etc.) but never serve as content
    # signals for tourism retrieval.
    assert tokenize("hotel 5 estrellas") == ["hotel", "estrellas"]
    assert tokenize("año 2024") == ["ano"]


def test_tokenize_keeps_alphanumeric_tokens():
    # Tokens that mix letters and digits are not pure digits and stay.
    assert tokenize("siglo XXI ruta66 año2024") == ["siglo", "xxi", "ruta66", "ano2024"]


def test_tokenize_drops_single_char_tokens():
    assert tokenize("a b c d") == []
    assert tokenize("u-v-w") == []


def test_tokenize_multiple_spaces():
    assert tokenize("hola   mundo") == ["hola", "mundo"]
    assert tokenize("\thola\nmundo\r") == ["hola", "mundo"]


def test_tokenize_only_punctuation():
    assert tokenize("!!! ???") == []
    assert tokenize("...---...") == []


def test_tokenize_single_word():
    assert tokenize("turismo") == ["turismo"]
    assert tokenize("TURISMO") == ["turismo"]
