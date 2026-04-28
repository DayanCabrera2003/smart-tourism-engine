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

    # Proveedor del LLM: "gemini" o "ollama"
    LLM_PROVIDER: str = "gemini"

    # URL base de Ollama (solo si LLM_PROVIDER=ollama)
    OLLAMA_URL: str = "http://localhost:11434"

    # Modelo de Ollama
    OLLAMA_MODEL: str = "llama3"

    # API Key para OpenTripMap
    OPENTRIPMAP_API_KEY: Optional[str] = None

    # API Key para Tavily (busqueda web fallback, T073)
    TAVILY_API_KEY: Optional[str] = None

    # Umbral de score por debajo del cual se activa el fallback web (T074)
    TAVILY_FALLBACK_SCORE_THRESHOLD: float = 0.30

    # Maximo de llamadas a Tavily por minuto (T079)
    TAVILY_RATE_LIMIT_PER_MINUTE: int = 20

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
