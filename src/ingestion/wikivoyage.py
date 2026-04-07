import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from src.ingestion.models import Destination
from src.logging_config import logger


class WikivoyageParser:
    """
    Parser para convertir el contenido de Wikivoyage (JSON de la API)
    en objetos del modelo Destination.
    """

    def __init__(self):
        # Regex para extraer coordenadas {{Geo|lat|long|...}}
        self.geo_re = re.compile(r"{{Geo\|(-?\d+\.\d+)\|(-?\d+\.\d+)")
        # Regex para limpiar wikitext básico (enlaces [[Page|Text]] -> Text)
        self.link_re = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]")
        # Regex para plantillas {{...}}
        self.template_re = re.compile(r"{{.*?}}", re.DOTALL)

    def clean_text(self, text: str) -> str:
        """Limpia el wikitext para obtener una descripción más legible."""
        # Eliminar plantillas al inicio (banners, etc.)
        text = self.template_re.sub("", text)
        # Limpiar enlaces
        text = self.link_re.sub(r"\1", text)
        # Eliminar marcas de negrita/cursiva
        text = text.replace("'''", "").replace("''", "")
        # Tomar solo el primer párrafo significativo o los primeros 500 caracteres
        paragraphs = [p.strip() for p in text.split("\n") if p.strip() and not p.startswith("==")]
        if paragraphs:
            return " ".join(paragraphs[:3])  # Unimos los primeros 3 párrafos para el MVP
        return text[:500]

    def parse_file(self, file_path: Path) -> Optional[Destination]:
        """Procesa un archivo JSON de la API de Wikivoyage."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            page = data["query"]["pages"][0]
            if "revisions" not in page:
                logger.warning(f"No hay revisiones para {file_path}")
                return None

            title = page["title"]
            content = page["revisions"][0]["content"]

            # Extraer coordenadas
            geo_match = self.geo_re.search(content)
            coords = None
            if geo_match:
                coords = (float(geo_match.group(1)), float(geo_match.group(2)))

            # Construir objeto Destination
            dest = Destination(
                id=title.lower().replace(" ", "-"),
                name=title,
                country="Spain",  # Sabemos que son de España por el script de descarga
                description=self.clean_text(content),
                coordinates=coords,
                tags=["city", "wikivoyage"],  # Tags base
                source="wikivoyage",
                fetched_at=datetime.now()
            )
            return dest

        except Exception as e:
            logger.error(f"Error parseando {file_path}: {e}")
            return None


def run_parser():
    """Ejecuta el parser sobre los archivos descargados."""
    input_dir = Path("data/raw/wikivoyage")
    output_path = Path("data/raw/destinations_raw.jsonl")
    
    parser = WikivoyageParser()
    destinations = []

    if not input_dir.exists():
        logger.error(f"No existe el directorio de entrada: {input_dir}")
        return

    for file_path in input_dir.glob("*.json"):
        dest = parser.parse_file(file_path)
        if dest:
            destinations.append(dest)

    if destinations:
        with open(output_path, "w", encoding="utf-8") as f:
            for dest in destinations:
                f.write(dest.model_dump_json() + "\n")
        logger.info(f"Parseados {len(destinations)} destinos y guardados en {output_path}")
    else:
        logger.warning("No se pudieron parsear destinos.")


if __name__ == "__main__":
    run_parser()
