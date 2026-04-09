import json
import logging

import sys
from pathlib import Path
from src.config import settings

import httpx

# Configuración básica de logging para el script
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Lista de 250 destinos turísticos de múltiples países para el catálogo
INITIAL_DESTINATIONS = [
    # España (50)
    "Madrid", "Barcelona", "Seville", "Granada", "Valencia",
    "Bilbao", "San Sebastian", "Córdoba (Spain)", "Santiago de Compostela", "Malaga",
    "Toledo", "Segovia", "Salamanca", "Avila", "Caceres",
    "Cuenca", "Zaragoza", "Palma de Mallorca", "Ibiza", "Santa Cruz de Tenerife",
    "Las Palmas de Gran Canaria", "Alicante", "Cadiz", "Jerez de la Frontera", "Almeria",
    "Oviedo", "Gijon", "Santander", "Pamplona", "Logroño",
    "Murcia", "Cartagena (Spain)", "Huelva", "Burgos", "Leon",
    "Vitoria-Gasteiz", "Merida", "Tarragona", "Girona", "Lleida",
    "Alcalá de Henares", "Badajoz", "Teruel", "Soria", "Guadalajara (Spain)",
    "Ciudad Real", "Albacete", "Lugo", "Ourense", "Pontevedra",
    # Francia (20)
    "Paris", "Lyon", "Marseille", "Nice", "Bordeaux",
    "Toulouse", "Strasbourg", "Nantes", "Montpellier", "Rennes",
    "Lille", "Cannes", "Saint-Tropez", "Avignon", "Aix-en-Provence",
    "Biarritz", "Perpignan", "Grenoble", "Dijon", "Reims",
    # Italia (20)
    "Rome", "Venice", "Florence", "Milan", "Naples",
    "Turin", "Bologna", "Genoa", "Palermo", "Catania",
    "Verona", "Pisa", "Siena", "Amalfi", "Capri",
    "Cinque Terre", "Ravenna", "Bergamo", "Padua", "Trieste",
    # Alemania (15)
    "Berlin", "Munich", "Hamburg", "Cologne", "Frankfurt",
    "Dresden", "Heidelberg", "Rothenburg ob der Tauber", "Nuremberg", "Stuttgart",
    "Dusseldorf", "Leipzig", "Bremen", "Freiburg", "Potsdam",
    # Reino Unido (15)
    "London", "Edinburgh", "Oxford", "Cambridge", "Bath",
    "York", "Canterbury", "Stonehenge", "Liverpool", "Manchester",
    "Bristol", "Brighton", "Cardiff", "Glasgow", "Dublin",
    # América Latina (40)
    "Buenos Aires", "Mendoza", "Córdoba", "Salta",
    "Rio de Janeiro", "Sao Paulo", "Salvador", "Florianopolis",
    "Mexico City", "Cancun", "Oaxaca", "Guadalajara",
    "Havana", "Trinidad",
    "Cartagena", "Medellin", "Bogota",
    "Lima", "Cusco", "Arequipa", "Machu Picchu",
    "Santiago", "Valparaiso",
    "Quito", "Galapagos Islands",
    "Montevideo",
    "La Paz", "Sucre",
    "Asuncion",
    "Caracas",
    "San Jose", "Manuel Antonio",
    "Panama City",
    "Guatemala City", "Antigua Guatemala",
    "Varadero",
    "Santo Domingo", "Punta Cana",
    "San Juan",
    # Asia (25)
    "Tokyo", "Kyoto", "Osaka", "Hiroshima", "Nara",
    "Beijing", "Shanghai", "Hong Kong", "Xi'an", "Guilin",
    "Bangkok", "Chiang Mai", "Phuket", "Krabi",
    "Bali", "Yogyakarta",
    "Singapore",
    "Hanoi", "Ho Chi Minh City", "Hoi An",
    "Seoul", "Busan",
    "Mumbai", "New Delhi", "Jaipur",
    # África y Oriente Medio (15)
    "Marrakech", "Fez", "Casablanca",
    "Cairo", "Luxor",
    "Cape Town", "Nairobi",
    "Dubai", "Abu Dhabi", "Istanbul",
    "Tel Aviv", "Jerusalem",
    "Petra",
    "Zanzibar",
    "Tunis",
    # Norteamérica y Oceanía (10)
    "New York City", "San Francisco", "New Orleans", "Chicago",
    "Vancouver", "Quebec City",
    "Sydney", "Melbourne",
    "Auckland",
    "Honolulu",
]

WIKIVOYAGE_API_URL = "https://en.wikivoyage.org/w/api.php"
USER_AGENT = "SmartTourismEngine/0.1 (dayancc@example.com)"

# Mapeo título → país para asignar country correcto en el pipeline
COUNTRY_MAP = {
    # España
    "Madrid": "Spain", "Barcelona": "Spain", "Seville": "Spain", "Granada": "Spain",
    "Valencia": "Spain", "Bilbao": "Spain", "San Sebastian": "Spain", "Córdoba (Spain)": "Spain",
    "Santiago de Compostela": "Spain", "Malaga": "Spain", "Toledo": "Spain",
    "Segovia": "Spain", "Salamanca": "Spain", "Avila": "Spain", "Caceres": "Spain",
    "Cuenca": "Spain", "Zaragoza": "Spain", "Palma de Mallorca": "Spain", "Ibiza": "Spain",
    "Santa Cruz de Tenerife": "Spain", "Las Palmas de Gran Canaria": "Spain",
    "Alicante": "Spain", "Cadiz": "Spain", "Jerez de la Frontera": "Spain",
    "Almeria": "Spain", "Oviedo": "Spain", "Gijon": "Spain", "Santander": "Spain",
    "Pamplona": "Spain", "Logroño": "Spain", "Murcia": "Spain", "Cartagena (Spain)": "Spain",
    "Huelva": "Spain", "Burgos": "Spain", "Leon": "Spain", "Vitoria-Gasteiz": "Spain",
    "Merida": "Spain", "Tarragona": "Spain", "Girona": "Spain", "Lleida": "Spain",
    "Alcalá de Henares": "Spain", "Badajoz": "Spain", "Teruel": "Spain", "Soria": "Spain",
    "Guadalajara (Spain)": "Spain", "Ciudad Real": "Spain", "Albacete": "Spain", "Lugo": "Spain",
    "Ourense": "Spain", "Pontevedra": "Spain",
    # Francia
    "Paris": "France", "Lyon": "France", "Marseille": "France", "Nice": "France",
    "Bordeaux": "France", "Toulouse": "France", "Strasbourg": "France", "Nantes": "France",
    "Montpellier": "France", "Rennes": "France", "Lille": "France", "Cannes": "France",
    "Saint-Tropez": "France", "Avignon": "France", "Aix-en-Provence": "France",
    "Biarritz": "France", "Perpignan": "France", "Grenoble": "France", "Dijon": "France",
    "Reims": "France",
    # Italia
    "Rome": "Italy", "Venice": "Italy", "Florence": "Italy", "Milan": "Italy",
    "Naples": "Italy", "Turin": "Italy", "Bologna": "Italy", "Genoa": "Italy",
    "Palermo": "Italy", "Catania": "Italy", "Verona": "Italy", "Pisa": "Italy",
    "Siena": "Italy", "Amalfi": "Italy", "Capri": "Italy", "Cinque Terre": "Italy",
    "Ravenna": "Italy", "Bergamo": "Italy", "Padua": "Italy", "Trieste": "Italy",
    # Alemania
    "Berlin": "Germany", "Munich": "Germany", "Hamburg": "Germany", "Cologne": "Germany",
    "Frankfurt": "Germany", "Dresden": "Germany", "Heidelberg": "Germany",
    "Rothenburg ob der Tauber": "Germany", "Nuremberg": "Germany", "Stuttgart": "Germany",
    "Dusseldorf": "Germany", "Leipzig": "Germany", "Bremen": "Germany",
    "Freiburg": "Germany", "Potsdam": "Germany",
    # Reino Unido e Irlanda
    "London": "United Kingdom", "Edinburgh": "United Kingdom", "Oxford": "United Kingdom",
    "Cambridge": "United Kingdom", "Bath": "United Kingdom", "York": "United Kingdom",
    "Canterbury": "United Kingdom", "Stonehenge": "United Kingdom",
    "Liverpool": "United Kingdom", "Manchester": "United Kingdom",
    "Bristol": "United Kingdom", "Brighton": "United Kingdom", "Cardiff": "United Kingdom",
    "Glasgow": "United Kingdom", "Dublin": "Ireland",
    # América Latina
    "Buenos Aires": "Argentina", "Mendoza": "Argentina", "Córdoba": "Argentina", "Salta": "Argentina",
    "Rio de Janeiro": "Brazil", "Sao Paulo": "Brazil", "Salvador": "Brazil",
    "Florianopolis": "Brazil",
    "Mexico City": "Mexico", "Cancun": "Mexico", "Oaxaca": "Mexico",
    "Guadalajara": "Mexico",
    "Havana": "Cuba", "Trinidad": "Cuba", "Varadero": "Cuba",
    "Cartagena": "Colombia", "Medellin": "Colombia", "Bogota": "Colombia",
    "Lima": "Peru", "Cusco": "Peru", "Arequipa": "Peru", "Machu Picchu": "Peru",
    "Santiago": "Chile", "Valparaiso": "Chile",
    "Quito": "Ecuador", "Galapagos Islands": "Ecuador",
    "Montevideo": "Uruguay",
    "La Paz": "Bolivia", "Sucre": "Bolivia",
    "Asuncion": "Paraguay",
    "Caracas": "Venezuela",
    "San Jose": "Costa Rica", "Manuel Antonio": "Costa Rica",
    "Panama City": "Panama",
    "Guatemala City": "Guatemala", "Antigua Guatemala": "Guatemala",
    "Santo Domingo": "Dominican Republic", "Punta Cana": "Dominican Republic",
    "San Juan": "Puerto Rico",
    # Asia
    "Tokyo": "Japan", "Kyoto": "Japan", "Osaka": "Japan", "Hiroshima": "Japan",
    "Nara": "Japan",
    "Beijing": "China", "Shanghai": "China", "Hong Kong": "China", "Xi'an": "China",
    "Guilin": "China",
    "Bangkok": "Thailand", "Chiang Mai": "Thailand", "Phuket": "Thailand",
    "Krabi": "Thailand",
    "Bali": "Indonesia", "Yogyakarta": "Indonesia",
    "Singapore": "Singapore",
    "Hanoi": "Vietnam", "Ho Chi Minh City": "Vietnam", "Hoi An": "Vietnam",
    "Seoul": "South Korea", "Busan": "South Korea",
    "Mumbai": "India", "New Delhi": "India", "Jaipur": "India",
    # África y Oriente Medio
    "Marrakech": "Morocco", "Fez": "Morocco", "Casablanca": "Morocco",
    "Cairo": "Egypt", "Luxor": "Egypt",
    "Cape Town": "South Africa", "Nairobi": "Kenya",
    "Dubai": "United Arab Emirates", "Abu Dhabi": "United Arab Emirates",
    "Istanbul": "Turkey",
    "Tel Aviv": "Israel", "Jerusalem": "Israel",
    "Petra": "Jordan",
    "Zanzibar": "Tanzania",
    "Tunis": "Tunisia",
    # Norteamérica y Oceanía
    "New York City": "United States", "San Francisco": "United States",
    "New Orleans": "United States", "Chicago": "United States",
    "Vancouver": "Canada", "Quebec City": "Canada",
    "Sydney": "Australia", "Melbourne": "Australia",
    "Auckland": "New Zealand",
    "Honolulu": "United States",
}


def save_country_map(output_dir: Path):
    """Guarda el mapeo título→país en un archivo JSON para uso del pipeline."""
    map_path = output_dir / "country_map.json"
    with open(map_path, "w", encoding="utf-8") as f:
        json.dump(COUNTRY_MAP, f, ensure_ascii=False, indent=2)
    logger.info(f"country_map.json guardado en {map_path}")


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
    raw_dir = settings.DATA_DIR / "raw" / "wikivoyage"
    logger.info(f"Iniciando descarga de {len(INITIAL_DESTINATIONS)} destinos...")
    download_pages(INITIAL_DESTINATIONS, raw_dir)
    save_country_map(raw_dir)
    logger.info("Descarga completada.")


if __name__ == "__main__":
    main()
