# 10. Adquisición y gestión de imágenes

## Descarga de imágenes de destinos turísticos

Las imágenes asociadas a cada destino se descargan automáticamente a la carpeta `data/raw/images/{destination_id}/`.

- **Extensiones permitidas:** `.jpg`, `.jpeg`, `.png`, `.webp`
- **Tamaño máximo:** 2MB por imagen
- **Estrategia:**
    - Se crea una subcarpeta por cada destino usando su `id`.
    - Solo se descargan imágenes cuyo formato es válido y cuyo tamaño no excede el límite.
    - Si la descarga falla, la imagen se ignora.
- **Implementación:**
    - Función principal: `download_images_for_destination(dest: Destination, base_folder: Path)` en `src/ingestion/images.py`.
    - Descarga asíncrona con `httpx`.
    - El test unitario `tests/test_images.py` valida que solo se guarden imágenes válidas y pequeñas.

## Ejemplo de uso

```python
from src.ingestion.images import download_images_for_destination
from src.ingestion.models import Destination
import asyncio

dest = Destination(
    id="madrid-es",
    name="Madrid",
    country="España",
    description="Capital de España",
    source="wikivoyage",
    coordinates=(40.416775, -3.703790),
    tags=["ciudad"],
    image_urls=["https://example.com/madrid.jpg"],
    fetched_at=None,
)

asyncio.run(download_images_for_destination(dest))
```

## Consideraciones éticas y legales
- Solo se descargan imágenes de URLs públicas proporcionadas por las fuentes originales (Wikivoyage, OpenTripMap, etc.).
- No se realiza scraping masivo ni hotlinking.
- El sistema respeta el tamaño y formato para evitar abuso de ancho de banda.
