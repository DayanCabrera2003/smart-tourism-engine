from pathlib import Path
from typing import List

from src.config import settings
from src.ingestion.models import Destination
from src.ingestion.normalize import normalize_text
from src.ingestion.wikivoyage import WikivoyageParser
from src.logging_config import logger


def ingest_wikivoyage(input_dir: Path, output_file: Path) -> List[Destination]:
    """
    Ejecuta el pipeline completo para Wikivoyage:
    Parser -> Normalización -> Persistencia en data/processed/
    """
    logger.info(f"Iniciando pipeline de ingestión desde {input_dir}")
    
    parser = WikivoyageParser()
    processed_destinations = []

    if not input_dir.exists():
        logger.error(f"El directorio de entrada no existe: {input_dir}")
        return []

    # 1. Parsing de archivos raw
    for file_path in input_dir.glob("*.json"):
        dest = parser.parse_file(file_path)
        if dest:
            # Guardar la descripción original (con acentos)
            original_desc = dest.description
            # Guardar versión normalizada solo para matching/indexación
            dest.description_normalized = normalize_text(original_desc)
            processed_destinations.append(dest)

    # 3. Guardar en data/processed/
    if processed_destinations:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            for dest in processed_destinations:
                f.write(dest.model_dump_json() + "\n")
        
        logger.info(
            f"Pipeline completado: {len(processed_destinations)} destinos en {output_file}"
        )
    else:
        logger.warning("No se procesaron destinos en el pipeline.")

    return processed_destinations


if __name__ == "__main__":
    # Configuración por defecto para ejecución manual
    raw_input = settings.DATA_DIR / "raw" / "wikivoyage"
    processed_output = settings.DATA_DIR / "processed" / "destinations.jsonl"
    
    ingest_wikivoyage(raw_input, processed_output)
