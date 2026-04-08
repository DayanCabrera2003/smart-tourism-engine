
from src.logging_config import setup_logging, logger
setup_logging()


def main():
    """
    Punto de entrada mínimo para verificar la inicialización del sistema.
    """
    logger.info("Sistema de Recuperación de Información de Turismo iniciado")
    logger.debug("Configuración de logging verificada")


if __name__ == "__main__":
    main()
