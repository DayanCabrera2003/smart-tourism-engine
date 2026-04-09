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
    4. Filtrado de tokens vacíos.

    Args:
        text: Texto de entrada (puede contener texto normalizado o crudo).

    Returns:
        Lista de tokens en minúsculas, sin acentos y sin puntuación.
    """
    if not text:
        return []

    text = text.lower()
    text = _strip_accents(text)
    tokens = re.split(r"[^a-z0-9]+", text)
    return [t for t in tokens if t]
