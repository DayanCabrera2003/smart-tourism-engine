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

# Lista de 50 destinos clave de España para el catálogo
INITIAL_DESTINATIONS = [
    "Madrid", "Barcelona", "Seville", "Granada", "Valencia",
    "Bilbao", "San Sebastian", "Cordoba", "Santiago de Compostela", "Malaga",
    "Toledo", "Segovia", "Salamanca", "Avila", "Caceres",
    "Cuenca", "Zaragoza", "Palma de Mallorca", "Ibiza", "Santa Cruz de Tenerife",
    "Las Palmas de Gran Canaria", "Alicante", "Cadiz", "Jerez de la Frontera", "Almeria",
    "Oviedo", "Gijon", "Santander", "Pamplona", "Logroño",
    "Murcia", "Cartagena", "Huelva", "Burgos", "Leon",
    "Vitoria-Gasteiz", "Merida", "Tarragona", "Girona", "Lleida",
    "Alcalá de Henares", "Badajoz", "Teruel", "Soria", "Guadalajara",
    "Ciudad Real", "Albacete", "Lugo", "Ourense", "Pontevedra"
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
