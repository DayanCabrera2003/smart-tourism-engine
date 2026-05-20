from src.indexing.stemmer import stem
from src.indexing.stopwords import remove_stopwords
from src.indexing.tokenizer import tokenize

__all__ = ["preprocess", "snowball_language_for"]


# Map from short language codes (as returned by detect_language) to the
# Snowball stemmer names that nltk expects. Both short codes and the
# Snowball names themselves are accepted by preprocess so existing
# callers that pass "spanish" or "english" keep working.
_LANGUAGE_ALIASES: dict[str, str] = {
    "es": "spanish",
    "en": "english",
    "spanish": "spanish",
    "english": "english",
}


def snowball_language_for(language: str) -> str:
    """Resolve any supported language label to the Snowball string.

    Raises :class:`ValueError` for unsupported labels so callers fail
    loudly instead of silently stemming with the wrong language.
    """
    try:
        return _LANGUAGE_ALIASES[language.lower()]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported language {language!r}; expected one of "
            f"{sorted(_LANGUAGE_ALIASES)}"
        ) from exc


def preprocess(text: str, language: str = "spanish") -> list[str]:
    """
    Pipeline completo de preprocesamiento de texto para indexación.

    Encadena los pasos:
    1. Tokenización: minúsculas + eliminación de acentos + split por no-alfanuméricos.
    2. Eliminación de stopwords (español + inglés).
    3. Stemming con SnowballStemmer para el idioma indicado.

    Args:
        text: Texto de entrada (crudo o pre-normalizado).
        language: Idioma del stemmer. Acepta los códigos cortos
            ``"es"`` / ``"en"`` (los que devuelve
            :func:`src.indexing.language.detect_language`) o los nombres
            largos de Snowball ``"spanish"`` / ``"english"``.

    Returns:
        Lista de stems listos para indexar.
    """
    snowball = snowball_language_for(language)
    tokens = tokenize(text)
    tokens = remove_stopwords(tokens)
    tokens = stem(tokens, language=snowball)
    return tokens
