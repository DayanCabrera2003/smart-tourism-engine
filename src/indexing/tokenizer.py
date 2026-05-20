import re
import unicodedata

__all__ = ["tokenize"]


def _strip_accents(text: str) -> str:
    """Elimina diacríticos de un texto."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return unicodedata.normalize("NFC", text)


def tokenize(text: str) -> list[str]:
    """
    Tokeniza el texto mediante split sobre caracteres no alfanuméricos y normalización.

    Pasos:
    1. Conversión a minúsculas.
    2. Eliminación de acentos/diacríticos.
    3. Split por caracteres no alfanuméricos.
    4. Filtrado de tokens vacíos, tokens de un solo carácter y tokens
       puramente numéricos (años, identificadores de poca utilidad para
       la recuperación de información turística).

    Args:
        text: Texto de entrada (puede contener texto normalizado o crudo).

    Returns:
        Lista de tokens en minúsculas, sin acentos, sin puntuación y
        sin tokens basura (cadenas de un solo carácter ni cadenas
        formadas únicamente por dígitos).
    """
    if not text:
        return []

    text = text.lower()
    text = _strip_accents(text)
    tokens = re.split(r"[^a-z0-9]+", text)
    return [t for t in tokens if len(t) >= 2 and not t.isdigit()]
