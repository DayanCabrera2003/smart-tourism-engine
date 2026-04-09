from nltk.stem import SnowballStemmer

__all__ = ["stem", "stem_token"]

Language = str  # "spanish" | "english"

_stemmers: dict[Language, SnowballStemmer] = {}


def _get_stemmer(language: Language) -> SnowballStemmer:
    if language not in _stemmers:
        _stemmers[language] = SnowballStemmer(language)
    return _stemmers[language]


def stem_token(token: str, language: Language = "spanish") -> str:
    """
    Aplica stemming a un único token.

    Args:
        token: Token ya normalizado (minúsculas, sin acentos).
        language: Idioma para el stemmer ("spanish" o "english").

    Returns:
        Raíz (stem) del token.
    """
    return _get_stemmer(language).stem(token)


def stem(tokens: list[str], language: Language = "spanish") -> list[str]:
    """
    Aplica stemming a una lista de tokens.

    Args:
        tokens: Lista de tokens normalizados.
        language: Idioma para el stemmer ("spanish" o "english").

    Returns:
        Lista con la raíz de cada token.
    """
    stemmer = _get_stemmer(language)
    return [stemmer.stem(t) for t in tokens]
