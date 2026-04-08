from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuración global de la aplicación.
    Utiliza Pydantic Settings para leer variables de entorno y archivos .env.
    """

    # URL de la base de datos vectorial Qdrant
    QDRANT_URL: str = "http://localhost:6333"

    # API Key para el LLM 
    LLM_API_KEY: Optional[str] = None

    # API Key para OpenTripMap
    OPENTRIPMAP_API_KEY: Optional[str] = None

    # Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    LOG_LEVEL: str = "INFO"

    # Directorio base para los datos del proyecto
    DATA_DIR: Path = Path("data")

    # Configuración de carga de variables de entorno
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )



# Instancia lazy de settings para facilitar testing y override
_settings: Optional[Settings] = None

def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings

# Para compatibilidad con imports existentes
settings = get_settings()
