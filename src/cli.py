
import typer

from src.config import settings
from src.ingestion.pipeline import ingest_wikivoyage
from src.logging_config import logger, setup_logging

setup_logging()

app = typer.Typer(help="CLI para el Smart Tourism Engine")
ingest_app = typer.Typer(help="Comandos de ingestión de datos")
app.add_typer(ingest_app, name="ingest")


@app.command("build-index")
def build_index_cmd():
    """
    Construye el índice invertido desde destinations.jsonl y lo guarda en index.pkl.

    Lee de data/processed/destinations.jsonl y escribe en data/processed/index.pkl.
    """
    from src.indexing.build_index import build_index

    source = settings.DATA_DIR / "processed" / "destinations.jsonl"
    output = settings.DATA_DIR / "processed" / "index.pkl"

    try:
        count = build_index(source, output)
        typer.echo(f"Índice construido: {count} documentos → {output}")
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


@app.command("embed")
def embed_cmd(
    source: str = typer.Option(
        None,
        "--source",
        help="Ruta al JSONL de destinos. Por defecto data/processed/destinations.jsonl.",
    ),
    batch_size: int = typer.Option(
        64, "--batch-size", min=1, help="Tamaño del batch de upsert a Qdrant."
    ),
    collection: str = typer.Option(
        None, "--collection", help="Nombre de la colección Qdrant (default: destinations_text)."
    ),
    only_new: bool = typer.Option(
        False,
        "--only-new",
        help="Solo indexa destinos que aún no tienen embedding en Qdrant (T057).",
    ),
):
    """Genera embeddings de los destinos y los sube a Qdrant (T052/T057)."""
    from src.indexing.embed_destinations import DEFAULT_COLLECTION, embed_destinations
    from src.indexing.embedder import TextEmbedder
    from src.indexing.vector_store import VectorStore

    src_path = (
        settings.DATA_DIR / "processed" / "destinations.jsonl"
        if source is None
        else source
    )
    coll = collection or DEFAULT_COLLECTION

    try:
        total = embed_destinations(
            src_path,
            VectorStore(),
            TextEmbedder(),
            collection=coll,
            batch_size=batch_size,
            only_new=only_new,
        )
        mode = "nuevos" if only_new else "total"
        typer.echo(f"Embeddings subidos a '{coll}': {total} puntos ({mode}).")
    except FileNotFoundError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


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
