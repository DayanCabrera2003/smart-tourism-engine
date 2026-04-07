import re
import unicodedata


def clean_html(text: str) -> str:
    """
    Elimina etiquetas HTML de una cadena de texto.
    """
    if not text:
        return ""
    # Regex para etiquetas HTML
    clean_re = re.compile("<.*?>")
    return re.sub(clean_re, "", text)


def lowercase(text: str) -> str:
    """
    Convierte el texto a minúsculas.
    """
    return text.lower() if text else ""


def strip_accents(text: str) -> str:
    """
    Elimina los acentos y diacríticos de una cadena de texto (ej: España -> Espana).
    """
    if not text:
        return ""
    # Normalizar a forma NFD (Descomposición de caracteres)
    text = unicodedata.normalize("NFD", text)
    # Filtrar solo los caracteres que no sean diacríticos
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return unicodedata.normalize("NFC", text)


def remove_extra_whitespace(text: str) -> str:
    """
    Elimina espacios en blanco adicionales, saltos de línea y tabulaciones.
    """
    if not text:
        return ""
    # Reemplaza múltiples espacios por uno solo y elimina espacios en los extremos
    return " ".join(text.split())


def normalize_text(text: str) -> str:
    """
    Aplica una normalización completa: HTML -> Minúsculas -> Acentos -> Espacios.
    """
    text = clean_html(text)
    text = lowercase(text)
    text = strip_accents(text)
    text = remove_extra_whitespace(text)
    return text
