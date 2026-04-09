import nltk
from nltk.corpus import stopwords as nltk_stopwords

__all__ = ["STOPWORDS", "remove_stopwords"]

_NLTK_LANGUAGES = ("spanish", "english")


def _load_stopwords() -> frozenset[str]:
    """Carga stopwords de español e inglés desde NLTK."""
    try:
        words: set[str] = set()
        for lang in _NLTK_LANGUAGES:
            words.update(nltk_stopwords.words(lang))
        return frozenset(words)
    except LookupError:
        nltk.download("stopwords", quiet=True)
        words = set()
        for lang in _NLTK_LANGUAGES:
            words.update(nltk_stopwords.words(lang))
        return frozenset(words)


STOPWORDS: frozenset[str] = _load_stopwords()


def remove_stopwords(tokens: list[str]) -> list[str]:
    """
    Elimina stopwords de una lista de tokens.

    Compara contra el conjunto combinado de stopwords en español e inglés
    proveniente de NLTK. Los tokens ya deben estar en minúsculas (sin acentos).

    Args:
        tokens: Lista de tokens normalizados.

    Returns:
        Lista de tokens con las stopwords eliminadas.
    """
    return [t for t in tokens if t not in STOPWORDS]
