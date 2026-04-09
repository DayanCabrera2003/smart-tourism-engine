"""
Descarga imágenes de destinos turísticos a data/raw/images/{destination_id}/
- Verifica formato (jpg/png/webp)
- Limita tamaño máximo (por defecto 2MB)
- Crea carpetas por destino
"""
from typing import List, Optional
import httpx
from pathlib import Path
from urllib.parse import urlparse, unquote
from src.ingestion.models import Destination

VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_SIZE = 2 * 1024 * 1024  # 2MB

async def download_image(
    url: str,
    dest_folder: Path,
    client: httpx.AsyncClient,
    max_size: int = MAX_IMAGE_SIZE,
) -> Optional[str]:
    """
    Descarga una imagen y la guarda en dest_folder si cumple restricciones.
    Recibe un cliente HTTP ya creado para reutilizar la conexión.
    Devuelve la ruta local o None si falla o no cumple las restricciones.
    """
    # Extraer filename limpio desde la URL (sin query string)
    parsed = urlparse(url)
    filename = unquote(parsed.path.split("/")[-1])
    ext = Path(filename).suffix.lower()
    if ext not in VALID_EXTENSIONS:
        return None
    dest_folder.mkdir(parents=True, exist_ok=True)
    local_path = dest_folder / filename
    try:
        # Verificar tamaño desde Content-Length antes de descargar
        resp = await client.head(url)
        content_length = int(resp.headers.get("content-length", 0))
        if content_length > max_size:
            return None
        resp = await client.get(url)
        resp.raise_for_status()
        # Verificar tamaño real por si Content-Length no estaba disponible
        if len(resp.content) > max_size:
            return None
        with open(local_path, "wb") as f:
            f.write(resp.content)
        return str(local_path)
    except Exception:
        return None


async def download_images_for_destination(
    dest: Destination,
    base_folder: Path = Path("data/raw/images/"),
) -> List[str]:
    """
    Descarga todas las imágenes de un destino en una subcarpeta por id.
    Reutiliza un único cliente HTTP para todas las imágenes del destino.
    Devuelve lista de rutas locales descargadas.
    """
    dest_folder = base_folder / dest.id
    results = []
    async with httpx.AsyncClient(timeout=20) as client:
        for url in dest.image_urls:
            path = await download_image(str(url), dest_folder, client)
            if path:
                results.append(path)
    return results
