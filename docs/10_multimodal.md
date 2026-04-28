# 10. Módulo Multimodal (CLIP)

## Justificación

El turismo es una experiencia profundamente visual. Un usuario que busca
"playa con aguas cristalinas" espera ver imágenes que validen esa promesa,
no solo texto que la describa. La búsqueda multimodal cierra esa brecha:

- **Búsqueda texto → imagen**: el usuario escribe "montañas con nieve" y
  recupera imágenes de destinos que coincidan visualmente, aunque las
  descripciones textuales usen términos distintos.
- **Búsqueda imagen → destinos**: el usuario sube una foto de un lugar que
  le gustó y el sistema encuentra destinos visualmente similares.
- **Búsqueda combinada**: texto + imagen guían juntos la consulta, ideal
  cuando el usuario tiene una referencia visual y quiere refinarla con palabras.

CLIP (Contrastive Language-Image Pretraining, Radford et al. 2021) resuelve
esto al entrenar un codificador de texto y uno de imagen para que las
representaciones de descripciones e imágenes coincidentes queden próximas en
el mismo espacio vectorial de 512 dimensiones.

---

## Adquisición de imágenes

Las imágenes se descargan con `src/ingestion/images.py` a:

```
data/raw/images/{destination_id}/{filename}.jpg
```

- **Extensiones permitidas:** `.jpg`, `.jpeg`, `.png`, `.webp`
- **Tamaño máximo:** 2 MB por imagen
- Solo se almacenan imágenes de URLs públicas proporcionadas por las fuentes
  originales (Wikivoyage, OpenTripMap).

**Implementación de descarga:** `src/ingestion/images.py`

```python
from src.ingestion.images import download_images_for_destination
from src.ingestion.models import Destination
import asyncio

dest = Destination(
    id="cancun-mx",
    name="Cancún",
    country="México",
    description="Destino de playa en el Caribe mexicano",
    source="wikivoyage",
    coordinates=(21.161908, -86.851528),
    tags=["playa", "caribe"],
    image_urls=["https://example.com/cancun.jpg"],
    fetched_at=None,
)

asyncio.run(download_images_for_destination(dest))
```

**Consideraciones:**
- No se realiza scraping masivo ni hotlinking.
- El sistema respeta límite de tamaño y formato.

---

## Modelo CLIP

| Parámetro       | Valor                        |
|----------------|------------------------------|
| Modelo          | `clip-ViT-B-32`              |
| Librería        | `sentence-transformers 5.x`  |
| Dimensión       | 512                          |
| Métrica         | Coseno                       |
| Tamaño en disco | ~340 MB                      |

Se eligió `clip-ViT-B-32` por su equilibrio entre velocidad, tamaño y calidad.
La variante B/32 procesa imágenes de 224x224 px en parches de 32x32, lo que
lo hace significativamente más rápido que B/16 o L/14 sin sacrificar calidad
perceptible para búsqueda de destinos turísticos.

**Implementación:** `src/multimodal/clip_embedder.py`

```python
from src.multimodal.clip_embedder import ClipEmbedder

embedder = ClipEmbedder()

# Embedding de texto
text_vec = embedder.embed_text("playa tropical con palmeras")

# Embedding de imagen
image_vec = embedder.embed_image("data/raw/images/cancun-mx/foto1.jpg")
```

---

## Colección Qdrant para imágenes

| Campo     | Valor                |
|----------|---------------------|
| Nombre    | `destinations_image` |
| Dimensión | 512                  |
| Métrica   | Coseno               |

**Payload por punto:**

| Campo            | Tipo | Descripción                         |
|-----------------|------|-------------------------------------|
| `destination_id` | str  | ID del destino en `destinations.db` |
| `image_path`     | str  | Ruta a `data/raw/images/`           |

**Inicializar la colección:**

```bash
python scripts/init_qdrant_images.py            # crea si no existe
python scripts/init_qdrant_images.py --recreate # borra y recrea
```

---

## Pipeline de indexación de imágenes

1. Recorrer `data/raw/images/{destination_id}/`
2. Por cada imagen válida (`.jpg/.jpeg/.png/.webp`):
   a. Abrir con Pillow y convertir a RGB
   b. Codificar con CLIP → vector de 512 dims
   c. Generar ID estable con MD5(`{destination_id}:{filename}`)
   d. Subir a Qdrant con payload `{destination_id, image_path}`

**Comando CLI:**

```bash
python -m src.cli embed-images                      # indexa todas
python -m src.cli embed-images --only-new           # solo nuevas
python -m src.cli embed-images --collection mi_col  # colección custom
```

**Implementación:** `src/multimodal/image_indexer.py`

---

## Endpoints de búsqueda multimodal

### `POST /search/image-by-text` (T084)

Embebe la consulta de texto con CLIP y busca las imágenes más similares
en `destinations_image`.

**Request:**
```json
{"query": "playa tropical con palmeras", "top_k": 10}
```

**Response:**
```json
{
  "results": [
    {
      "destination_id": "cancun-mx",
      "image_path": "data/raw/images/cancun-mx/foto1.jpg",
      "score": 0.87
    }
  ]
}
```

---

### `POST /search/by-image` (T085)

Recibe una imagen (multipart/form-data), la embebe con CLIP y devuelve los
destinos visualmente más similares.

**Request:** `multipart/form-data` con campo `file` (JPEG/PNG) y query param `top_k`.

---

### `POST /search/multimodal` (T088)

Combina texto + imagen opcional con peso `alpha`.

Estrategia de fusión:

```
query_vector = alpha * text_vector + (1 - alpha) * image_vector
query_vector = L2_normalize(query_vector)
```

El vector combinado se normaliza a L2 antes de consultar Qdrant.

**Request:**
```json
{
  "query": "playa tranquila",
  "image_b64": "<base64 de la imagen, opcional>",
  "top_k": 10,
  "alpha": 0.6
}
```

`alpha=1.0` equivale a solo texto (T084); `alpha=0.0` equivale a solo imagen.

**Implementación de fusión:** `src/multimodal/fusion.py`

---

## Interfaz de usuario (T086/T087)

El tab **"Buscar por imagen"** en la UI Streamlit ofrece dos modos:

1. **Subir imagen:** file uploader, muestra la imagen y los resultados similares.
2. **Descripción de texto:** input de texto que usa CLIP para recuperar imágenes.

Las tarjetas de destinos en el tab "Buscar destinos" (T087) muestran una
**galería de imágenes** en grid de hasta 3 columnas cuando el destino tiene
múltiples imágenes disponibles.

---

## Casos de prueba

| Query / Input              | Resultado esperado                  |
|---------------------------|-------------------------------------|
| "playa tropical"           | Imágenes de destinos de playa caribe |
| "montana con nieve"        | Imágenes de Alpes, Pirineos, etc.   |
| "ciudad historica europea" | Imágenes de Roma, Praga, Sevilla... |
| Imagen de playa            | Otros destinos de playa similares   |

Los tests automatizados se encuentran en `tests/test_multimodal.py`.

---

## Estadísticas (actualizar tras indexar)

| Métrica                          | Valor         |
|---------------------------------|---------------|
| Imágenes indexadas en Qdrant     | —             |
| Destinos con al menos 1 imagen   | —             |
| Dimensión de la colección        | 512           |
| Modelo CLIP                      | clip-ViT-B-32 |
