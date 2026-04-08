import asyncio
import httpx
from typing import Dict, Any, List, Optional

from src.config import settings
from src.logging_config import logger

class OpenTripMapClient:
    """
    Cliente para interactuar con la API gratuita de OpenTripMap.
    Documentación API: https://opentripmap.com/en/developer/api
    """

    BASE_URL = "https://api.opentripmap.com/0.1/en/places/"
    DEFAULT_TIMEOUT = 10.0 # seconds
    DEFAULT_LIMIT = 50 # Max POIs per request

    def __init__(self, api_key: str, client: Optional[httpx.AsyncClient] = None):
        if not api_key:
            raise ValueError("OpenTripMap API key is required.")
        self.api_key = api_key
        self.client = client if client else httpx.AsyncClient(base_url=self.BASE_URL, timeout=self.DEFAULT_TIMEOUT)

    async def _request(self, endpoint: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Realiza una solicitud genérica a la API de OpenTripMap.
        """
        full_params = {"apikey": self.api_key, **params}
        
        try:
            response = await self.client.get(endpoint, params=full_params)
            response.raise_for_status()  # Lanza una excepción para códigos de estado HTTP 4xx/5xx
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"Error HTTP al consultar OpenTripMap {endpoint}: {e.response.status_code} - {e.response.text}")
            return None
        except httpx.RequestError as e:
            logger.error(f"Error de red/solicitud al consultar OpenTripMap {endpoint}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado al consultar OpenTripMap {endpoint}: {e}")
            return None

    async def get_pois_in_bbox(
        self,
        lon_min: float,
        lat_min: float,
        lon_max: float,
        lat_max: float,
        limit: int = DEFAULT_LIMIT,
        kinds: Optional[str] = None, # Comma-separated list of POI kinds (e.g., "natural,museums")
    ) -> List[Dict[str, Any]]:
        """
        Obtiene Puntos de Interés (POIs) dentro de un recuadro delimitador.
        API endpoint: /places/bbox
        """
        endpoint = "bbox"
        params = {
            "lon_min": lon_min,
            "lat_min": lat_min,
            "lon_max": lon_max,
            "lat_max": lat_max,
            "limit": limit,
        }
        if kinds:
            params["kinds"] = kinds
        
        data = await self._request(endpoint, params)
        if data and "features" in data:
            logger.info(f"Obtenidos {len(data['features'])} POIs de OpenTripMap en bbox.")
            return data["features"]
        return []

    async def get_poi_details(self, xid: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene detalles de un POI específico por su xid.
        API endpoint: /places/xid/{xid}
        """
        endpoint = f"xid/{xid}"
        data = await self._request(endpoint, {}) # No se requieren params adicionales para este endpoint
        if data:
            return data
        return None

# Ejemplo de uso (solo para pruebas locales, se eliminará o moverá a CLI/Tests)
async def main():
    if not settings.OPENTRIPMAP_API_KEY:
        logger.warning("OPENTRIPMAP_API_KEY no configurada. Saltando demo de OpenTripMap.")
        return

    client = OpenTripMapClient(api_key=settings.OPENTRIPMAP_API_KEY)

    # Ejemplo: POIs en Madrid (bounding box aproximada)
    madrid_pois = await client.get_pois_in_bbox(
        lon_min=-3.71, lat_min=40.40, lon_max=-3.67, lat_max=40.43, limit=10, kinds="churches,museums"
    )
    logger.info(f"POIs en Madrid: {madrid_pois}")

    if madrid_pois:
        first_poi_xid = madrid_pois[0]["properties"]["xid"]
        poi_details = await client.get_poi_details(first_poi_xid)
        logger.info(f"Detalles del primer POI ({first_poi_xid}): {poi_details}")

if __name__ == "__main__":
    asyncio.run(main())
