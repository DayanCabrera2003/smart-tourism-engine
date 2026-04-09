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
        2. Preprocesa el texto concatenado (nombre + descripción normalizada)
           con el pipeline tokenize → stopwords → stem.
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
            tokens = preprocess(text, language="english")
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
