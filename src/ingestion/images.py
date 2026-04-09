"""
Descarga imágenes de destinos turísticos a data/raw/images/{destination_id}/
- Verifica formato (jpg/png/webp)
- Limita tamaño máximo (por defecto 2MB)
- Crea carpetas por destino
"""
import os
from typing import List
import httpx
from pathlib import Path
from src.ingestion.models import Destination

VALID_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_IMAGE_SIZE = 2 * 1024 * 1024  # 2MB

async def download_image(url: str, dest_folder: Path, max_size: int = MAX_IMAGE_SIZE) -> str:
    """
    Descarga una imagen y la guarda en dest_folder si cumple restricciones.
    Devuelve la ruta local o None si falla.
    """
    filename = url.split("/")[-1]
    ext = os.path.splitext(filename)[1].lower()
    if ext not in VALID_EXTENSIONS:
        return None
    dest_folder.mkdir(parents=True, exist_ok=True)
    local_path = dest_folder / filename
    async with httpx.AsyncClient(timeout=20) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            if len(resp.content) > max_size:
                return None
            with open(local_path, "wb") as f:
                f.write(resp.content)
            return str(local_path)
        except Exception:
            return None

async def download_images_for_destination(dest: Destination, base_folder: Path = Path("data/raw/images/")) -> List[str]:
    """
    Descarga todas las imágenes de un destino en una subcarpeta por id.
    Devuelve lista de rutas locales descargadas.
    """
    dest_folder = base_folder / dest.id
    results = []
    for url in dest.image_urls:
        path = await download_image(str(url), dest_folder)
        if path:
            results.append(path)
    return results
