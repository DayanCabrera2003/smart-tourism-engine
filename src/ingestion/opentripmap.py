
import asyncio
from typing import Any, Dict, List, Optional

import httpx

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
        self._owns_client = client is None  # Track if we created the client
        self.client = client if client else httpx.AsyncClient(
            base_url=self.BASE_URL, timeout=self.DEFAULT_TIMEOUT
        )

    async def close(self):
        """
        Cierra la conexión HTTP del cliente.
        Solo cierra el cliente si fue creado internamente por esta instancia.
        """
        if self._owns_client:
            await self.client.aclose()

    async def __aenter__(self):
        """
        Implementa el protocolo async context manager (entrada).
        """
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """
        Implementa el protocolo async context manager (salida).
        Cierra la conexión HTTP al salir del contexto.
        """
        await self.close()
        return False  # No suprime excepciones

    MAX_RETRIES = 3

    # Códigos HTTP que justifican reintento (transitorios)
    _RETRYABLE_STATUS = {429, 500, 502, 503, 504}

    async def _request(self, endpoint: str, params: Dict[str, Any]) -> Optional[Any]:
        """
        Realiza una solicitud genérica a la API de OpenTripMap con reintentos
        para rate limiting (429), errores de servidor 5xx y errores de red.
        """
        full_params = {"apikey": self.api_key, **params}
        for attempt in range(self.MAX_RETRIES):
            try:
                response = await self.client.get(endpoint, params=full_params)
                if response.status_code in self._RETRYABLE_STATUS:
                    wait = 2 ** attempt
                    logger.warning(
                        f"HTTP {response.status_code} en {endpoint}, "
                        f"reintento {attempt + 1}/{self.MAX_RETRIES} en {wait}s..."
                    )
                    await asyncio.sleep(wait)
                    continue
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                # Error no retriable (4xx excepto 429): fallo definitivo
                logger.error(
                    f"Error HTTP al consultar OpenTripMap {endpoint}: "
                    f"{e.response.status_code} - {e.response.text}"
                )
                return None
            except httpx.RequestError as e:
                # Error de red/timeout: reintentable
                wait = 2 ** attempt
                logger.warning(
                    f"Error de red en {endpoint}: {e}. "
                    f"Reintento {attempt + 1}/{self.MAX_RETRIES} en {wait}s..."
                )
                await asyncio.sleep(wait)
            except Exception as e:
                logger.error(f"Error inesperado al consultar OpenTripMap {endpoint}: {e}")
                return None
        logger.error(f"Se agotaron los {self.MAX_RETRIES} reintentos para {endpoint}")
        return None

    async def get_pois_in_bbox(
        self,
        lon_min: float,
        lat_min: float,
        lon_max: float,
        lat_max: float,
        limit: int = DEFAULT_LIMIT,
        kinds: Optional[str] = None,
        # Comma-separated list of POI kinds (e.g., "natural,museums")
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
        # data puede ser dict (con "features") o lista
        if isinstance(data, dict) and "features" in data:
            logger.info(f"Obtenidos {len(data['features'])} POIs de OpenTripMap en bbox.")
            return data["features"]
        elif isinstance(data, list):
            logger.info(f"Obtenidos {len(data)} POIs de OpenTripMap en bbox (lista).")
            return data
        return []

    async def get_poi_details(self, xid: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene detalles de un POI específico por su xid.
        API endpoint: /places/xid/{xid}
        """
        endpoint = f"xid/{xid}"
        data = await self._request(endpoint, {})
        if data:
            return data
        return None


