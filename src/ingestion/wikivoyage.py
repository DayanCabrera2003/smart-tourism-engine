import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.ingestion.models import Destination
from src.logging_config import logger


class WikivoyageParser:
    """
    Parser para convertir el contenido de Wikivoyage (JSON de la API)
    en objetos del modelo Destination.
    """

    # Caracteres no permitidos en IDs (mantener solo letras, dígitos y guiones)
    _id_unsafe_re = re.compile(r"[^a-z0-9-]")

    def __init__(self, default_country: str = "Spain"):
        self.default_country = default_country
        # Regex para extraer coordenadas {{Geo|lat|long|...}} o {{geo|...}}
        # Soporta enteros y decimales: {{Geo|48|2}}, {{Geo|48.5|-3}}, {{geo|-34|-58.5}}
        self.geo_re = re.compile(r"{{[Gg]eo\|(-?\d+(?:\.\d+)?)\|(-?\d+(?:\.\d+)?)")
        # Regex para limpiar wikitext básico (enlaces [[Page|Text]] -> Text)
        self.link_re = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]+)\]\]")
        # Regex para plantillas {{...}}
        self.template_re = re.compile(r"{{.*?}}", re.DOTALL)

    def _make_id(self, title: str) -> str:
        """Genera un ID seguro para URLs y sistemas de archivos a partir del título."""
        # Eliminar diacríticos (ñ→n, á→a, etc.)
        nfd = unicodedata.normalize("NFD", title.lower())
        ascii_title = "".join(c for c in nfd if unicodedata.category(c) != "Mn")
        # Espacios y paréntesis → guiones
        slug = ascii_title.replace(" ", "-").replace("(", "").replace(")", "")
        # Eliminar cualquier carácter restante no seguro
        slug = self._id_unsafe_re.sub("", slug)
        # Colapsar guiones múltiples
        slug = re.sub(r"-{2,}", "-", slug).strip("-")
        return f"wikivoyage-{slug}"

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
                id=self._make_id(title),
                name=title,
                country=self.default_country,  # Ahora configurable
                description=self.clean_text(content),
                coordinates=coords,
                tags=["city", "wikivoyage"],  # Tags base
                source="wikivoyage",
                fetched_at=datetime.now(timezone.utc),
            )
            return dest

        except Exception as e:
            logger.error(f"Error parseando {file_path}: {e}")
            return None


