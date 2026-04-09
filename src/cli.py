
import typer

from src.config import settings
from src.ingestion.pipeline import ingest_wikivoyage
from src.logging_config import logger, setup_logging

setup_logging()

app = typer.Typer(help="CLI para el Smart Tourism Engine")
ingest_app = typer.Typer(help="Comandos de ingestión de datos")
app.add_typer(ingest_app, name="ingest")


@ingest_app.command("wikivoyage")
def ingest_wikivoyage_cmd():
    """
    Ejecuta el pipeline de ingestión para Wikivoyage.
    Descarga (si es necesario) y procesa destinos de España.
    """
    logger.info("Iniciando comando ingest wikivoyage")
    
    raw_input = settings.DATA_DIR / "raw" / "wikivoyage"
    processed_output = settings.DATA_DIR / "processed" / "destinations.jsonl"
    
    # Por ahora asume que los archivos ya están descargados por el script previo
    # En tareas futuras podríamos integrar la descarga aquí también
    results = ingest_wikivoyage(raw_input, processed_output)
    
    if results:
        typer.echo(f"Ingestión completada con éxito: {len(results)} destinos procesados.")
    else:
        typer.echo("Error en la ingestión o no se encontraron destinos.", err=True)


if __name__ == "__main__":
    app()
