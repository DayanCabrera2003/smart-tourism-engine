from src.ingestion.normalize import (
    clean_html,
    lowercase,
    normalize_text,
    remove_extra_whitespace,
    strip_accents,
)


def test_clean_html():
    assert clean_html("<p>Hola <b>Mundo</b></p>") == "Hola Mundo"
    assert clean_html("Texto sin HTML") == "Texto sin HTML"
    assert clean_html("") == ""


def test_lowercase():
    assert lowercase("HOLA Mundo") == "hola mundo"
    assert lowercase("madrid") == "madrid"
    assert lowercase("") == ""


def test_strip_accents():
    assert strip_accents("España") == "Espana"
    assert strip_accents("Árbol genealógico") == "Arbol genealogico"
    assert strip_accents("ñ y Ñ") == "n y N"
    assert strip_accents("") == ""


def test_remove_extra_whitespace():
    assert remove_extra_whitespace("  Hola    mundo  \n con saltos  ") == "Hola mundo con saltos"
    assert remove_extra_whitespace("\tTabulaciones y   espacios") == "Tabulaciones y espacios"
    assert remove_extra_whitespace("") == ""


def test_normalize_text_full():
    input_text = "  <p>¡Hola <b>España</b>!  </p> \n ¿Cómo está todo?  "
    # HTML -> ¡Hola España! ¿Cómo está todo?
    # Lower -> ¡hola españa! ¿cómo está todo?
    # Accents -> ¡hola espana! ¿como esta todo?
    # Whitespace -> ¡hola espana! ¿como esta todo?
    expected = "¡hola espana! ¿como esta todo?"
    assert normalize_text(input_text) == expected
