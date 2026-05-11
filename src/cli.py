
from pathlib import Path

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


@app.command("embed-images")
def embed_images_cmd(
    images_dir: str = typer.Option(
        None,
        "--images-dir",
        help="Directorio raíz de imágenes. Por defecto data/raw/images.",
    ),
    batch_size: int = typer.Option(
        32, "--batch-size", min=1, help="Tamaño del batch de upsert a Qdrant."
    ),
    collection: str = typer.Option(
        None, "--collection", help="Nombre de la colección Qdrant (default: destinations_image)."
    ),
    only_new: bool = typer.Option(
        False,
        "--only-new",
        help="Solo indexa imágenes que aún no tienen embedding en Qdrant.",
    ),
):
    """Genera embeddings CLIP de imágenes y los sube a Qdrant (T083)."""
    from src.indexing.vector_store import VectorStore
    from src.multimodal.clip_embedder import ClipEmbedder
    from src.multimodal.image_indexer import IMAGE_COLLECTION, embed_images

    dir_path = (
        settings.DATA_DIR / "raw" / "images"
        if images_dir is None
        else Path(images_dir)
    )
    coll = collection or IMAGE_COLLECTION

    total = embed_images(
        dir_path,
        VectorStore(),
        ClipEmbedder(),
        collection=coll,
        batch_size=batch_size,
        only_new=only_new,
    )
    mode = "nuevas" if only_new else "total"
    typer.echo(f"Embeddings de imágenes subidos a '{coll}': {total} puntos ({mode}).")


@app.command("evaluate")
def evaluate_cmd(
    queries_path: str = typer.Option(
        None,
        "--queries",
        help="Ruta al queries.json (default: data/eval/queries.json).",
    ),
    top_k: int = typer.Option(
        10, "--top-k", min=1, help="Cutoff k para las métricas P/R/F1/nDCG."
    ),
    p: float = typer.Option(
        2.0, "--p", min=1.0, help="Norma-p del Booleano Extendido."
    ),
    alpha: float = typer.Option(
        0.5, "--alpha", min=0.0, max=1.0, help="Peso léxico en modo híbrido."
    ),
    output: str = typer.Option(
        None,
        "--output",
        help="Ruta JSON para volcar el reporte completo (opcional).",
    ),
    modes: str = typer.Option(
        "boolean,semantic,hybrid",
        "--modes",
        help="Lista separada por coma de modos a evaluar.",
    ),
    plots_dir: str = typer.Option(
        None,
        "--plots-dir",
        help="Directorio donde renderizar PNGs comparativos (default: docs/figures/).",
    ),
    no_plots: bool = typer.Option(
        False,
        "--no-plots",
        help="Omitir la renderización de gráficas (útil en CI).",
    ),
):
    """Evalúa los recuperadores contra queries.json y produce una tabla comparativa (T108)."""
    import json as _json
    from pathlib import Path as _Path

    from src.evaluation.retrievers import (
        build_boolean_retriever,
        build_hybrid_retriever,
        build_semantic_retriever,
    )
    from src.evaluation.runner import (
        EvaluationConfig,
        ModeReport,
        evaluate,
        load_queries,
    )

    queries_file = (
        _Path(queries_path)
        if queries_path
        else settings.DATA_DIR / "eval" / "queries.json"
    )
    if not queries_file.exists():
        typer.echo(f"queries.json no encontrado en {queries_file}", err=True)
        raise typer.Exit(code=1)

    queries = load_queries(queries_file)
    index_file = settings.DATA_DIR / "processed" / "index.pkl"
    requested = [m.strip() for m in modes.split(",") if m.strip()]

    retrievers: dict = {}
    unavailable_reports: dict[str, ModeReport] = {}

    for mode in requested:
        try:
            if mode == "boolean":
                retrievers[mode] = build_boolean_retriever(index_file, p=p)
            elif mode == "semantic":
                retrievers[mode] = build_semantic_retriever()
            elif mode == "hybrid":
                retrievers[mode] = build_hybrid_retriever(
                    index_file, p=p, alpha=alpha
                )
            else:
                typer.echo(f"Modo desconocido: {mode}", err=True)
                raise typer.Exit(code=1) from None
        except Exception as exc:
            unavailable_reports[mode] = ModeReport(
                mode=mode, available=False, error=f"{type(exc).__name__}: {exc}"
            )
            typer.echo(
                f"Modo '{mode}' no disponible: {type(exc).__name__}: {exc}",
                err=True,
            )

    config = EvaluationConfig(top_k=top_k, queries_path=queries_file)
    report = evaluate(retrievers, queries, config)
    for mode, rep in unavailable_reports.items():
        report.modes[mode] = rep

    typer.echo("")
    typer.echo(f"Reporte de evaluación — top_k={top_k}, queries={len(queries)}")
    typer.echo("=" * 72)
    header = ["mode", "P@k", "R@k", "F1@k", "MAP", "MRR", "nDCG@k", "available"]
    typer.echo("\t".join(header))
    for mode, rep in report.modes.items():
        if not rep.available:
            typer.echo(f"{mode}\t-\t-\t-\t-\t-\t-\tFalse ({rep.error})")
            continue
        summary = rep.as_summary()
        row = [
            mode,
            f"{summary['P@k']:.4f}",
            f"{summary['R@k']:.4f}",
            f"{summary['F1@k']:.4f}",
            f"{summary['MAP']:.4f}",
            f"{summary['MRR']:.4f}",
            f"{summary['nDCG@k']:.4f}",
            "True",
        ]
        typer.echo("\t".join(row))

    if output:
        out_file = _Path(output)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with out_file.open("w") as fh:
            _json.dump(report.to_json(), fh, ensure_ascii=False, indent=2)
        typer.echo(f"\nReporte completo guardado en {out_file}")

    if not no_plots:
        from src.evaluation.plots import render_plots

        plots_target = _Path(plots_dir) if plots_dir else _Path("docs/figures")
        paths = render_plots(report, plots_target)
        typer.echo("Gráficas generadas:")
        for path in paths:
            typer.echo(f"  - {path}")


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
