from pathlib import Path

from src.config import settings


def test_settings_load():
    """
    Verifica que las configuraciones base se carguen correctamente.
    """
    assert settings.QDRANT_URL is not None
    assert isinstance(settings.DATA_DIR, Path)
    assert settings.LOG_LEVEL in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

def test_project_structure():
    """
    Verifica que el directorio de datos base esté definido.
    """
    assert settings.DATA_DIR.name == "data"
