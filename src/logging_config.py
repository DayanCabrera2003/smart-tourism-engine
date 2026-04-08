import json
import logging
import sys
from datetime import datetime, timezone

from src.config import settings


class JsonFormatter(logging.Formatter):
    """
    Formateador de logs en formato JSON para logging estructurado.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "funcName": record.funcName,
            "lineno": record.lineno,
        }

        # Añadir información de excepción si existe
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_record)


def setup_logging():
    """
    Configura el sistema de logging global basado en settings.
    """
    # Obtener el nivel de log de la configuración
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    # Configurar el manejador para la salida estándar (stdout)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    # Configurar el logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Limpiar manejadores existentes (útil en recargas)
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    root_logger.addHandler(handler)

    # Desactivar logs ruidosos de librerías externas si es necesario
    # logging.getLogger("uvicorn").setLevel(logging.WARNING)



# Logger base para ser usado en el resto del proyecto
logger = logging.getLogger("smart_tourism")
