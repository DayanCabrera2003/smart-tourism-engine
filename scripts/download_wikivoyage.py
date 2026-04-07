import json
import logging
import sys
from pathlib import Path

import httpx

# Configuración básica de logging para el script
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Lista de destinos iniciales para el MVP (España)
INITIAL_DESTINATIONS = [
    "Madrid",
    "Barcelona",
    "Seville",
    "Granada",
    "Valencia"
]

WIKIVOYAGE_API_URL = "https://en.wikivoyage.org/w/api.php"
USER_AGENT = "SmartTourismEngine/0.1 (dayancc@example.com)"


def download_pages(pages: list[str], output_dir: Path):
    """
    Descarga el contenido de las páginas de Wikivoyage en formato JSON.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with httpx.Client(headers={"User-Agent": USER_AGENT}) as client:
        for page_title in pages:
            logger.info(f"Descargando página: {page_title}")
            params = {
                "action": "query",
                "format": "json",
                "titles": page_title,
                "prop": "revisions",
                "rvprop": "content",
                "formatversion": "2"
            }
            
            try:
                response = client.get(WIKIVOYAGE_API_URL, params=params)
                response.raise_for_status()
                data = response.json()
                
                # Guardar el JSON crudo en data/raw
                file_path = output_dir / f"{page_title.lower().replace(' ', '_')}.json"
                with open(file_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                
                logger.info(f"Guardado en: {file_path}")
                
            except Exception as e:
                logger.error(f"Error al descargar {page_title}: {e}")


def main():
    raw_dir = Path("data/raw/wikivoyage")
    logger.info(f"Iniciando descarga de {len(INITIAL_DESTINATIONS)} destinos...")
    download_pages(INITIAL_DESTINATIONS, raw_dir)
    logger.info("Descarga completada.")


if __name__ == "__main__":
    main()
