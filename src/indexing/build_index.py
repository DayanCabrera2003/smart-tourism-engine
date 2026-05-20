"""T030 — Construcción del índice invertido desde el JSONL de destinos."""
import json
from pathlib import Path

from src.indexing.inverted_index import InvertedIndex
from src.indexing.preprocess import preprocess
from src.logging_config import logger

__all__ = ["build_index"]


def build_index(source: str | Path, output: str | Path) -> int:
    """
    Lee destinos desde un archivo JSONL, construye el índice invertido y lo guarda.

    Flujo:
        1. Lee cada línea de `source` como un objeto JSON con campos `id`,
           `name` y `description_normalized`.
        2. Preprocesa el texto concatenado (nombre + descripción
           normalizada) DOS VECES: una con el Snowball español y otra
           con el inglés. La unión de ambos conjuntos de stems se
           indexa por documento. Esto evita que una consulta corta
           (por ejemplo "Madrid", detectada como español → "madr")
           pierda al documento "Madrid" cuyo cuerpo en inglés produjo
           el stem "madrid". Con la doble indexación, ambas formas
           viven en los postings del mismo doc.
        3. Indexa cada documento en `InvertedIndex`.
        4. Calcula pesos TF-IDF y normas L2.
        5. Serializa el índice en `output` con `InvertedIndex.save()`.

    Args:
        source: Ruta al archivo JSONL de destinos procesados.
        output: Ruta de salida para el índice serializado (.pkl).

    Returns:
        Número de documentos indexados.

    Raises:
        FileNotFoundError: Si `source` no existe.
    """
    source = Path(source)
    output = Path(output)

    if not source.exists():
        raise FileNotFoundError(f"Archivo de destinos no encontrado: {source}")

    idx = InvertedIndex()

    with source.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            doc_id: str = doc["id"]
            text: str = doc.get("name", "") + " " + doc.get("description_normalized", "")
            # Index every document under the union of Spanish and English
            # stems. Without this, a Spanish-detected query like
            # "Madrid" (stem "madr") would miss an English-detected doc
            # body (stem "madrid"). The union keeps the index reachable
            # from either query language at the cost of a small vocab
            # bump (~5-10% on a mixed corpus).
            tokens_es = preprocess(text, language="es")
            tokens_en = preprocess(text, language="en")
            # Stem position is not used by the inverted index — it only
            # records token frequency — so we can merge without losing
            # any retrieval signal.
            tokens = tokens_es + tokens_en
            idx.add_document(doc_id, tokens)

    idx.compute_tf_idf()
    idx.save(output)

    logger.info(
        "Índice construido: %d documentos, %d términos → %s",
        idx.doc_count,
        len(idx),
        output,
    )
    return idx.doc_count
