from src.indexing.stemmer import stem
from src.indexing.stopwords import remove_stopwords
from src.indexing.tokenizer import tokenize

__all__ = ["preprocess"]


def preprocess(text: str, language: str = "spanish") -> list[str]:
    """
    Pipeline completo de preprocesamiento de texto para indexación.

    Encadena los pasos:
    1. Tokenización: minúsculas + eliminación de acentos + split por no-alfanuméricos.
    2. Eliminación de stopwords (español + inglés).
    3. Stemming con SnowballStemmer para el idioma indicado.

    Args:
        text: Texto de entrada (crudo o pre-normalizado).
        language: Idioma del stemmer ("spanish" o "english").

    Returns:
        Lista de stems listos para indexar.
    """
    tokens = tokenize(text)
    tokens = remove_stopwords(tokens)
    tokens = stem(tokens, language=language)
    return tokens
