# 04 - Adquisición de Datos

Este documento detalla las fuentes de datos, el esquema de información y los procesos de limpieza y normalización aplicados a los destinos turísticos.

## Modelo de Datos `Destination`

Toda la información recolectada de diversas fuentes se unifica bajo el modelo `Destination`, implementado mediante Pydantic en `src/ingestion/models.py`.

### Esquema de Datos

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | `str` | Identificador único del destino (slug o hash). |
| `name` | `str` | Nombre oficial del destino. |
| `country` | `str` | País al que pertenece el destino. |
| `region` | `str` (opcional) | Región, estado o provincia. |
| `description` | `str` | Descripción textual extensa del destino. |
| `tags` | `List[str]` | Etiquetas o categorías (ej. playa, museos). |
| `image_urls` | `List[HttpUrl]` | URLs de imágenes representativas. |
| `coordinates` | `Tuple[float, float]` (opcional) | Latitud y longitud geográfica. |
| `source` | `str` | Nombre de la fuente de datos (ej. wikivoyage). |
| `fetched_at` | `datetime` | Marca de tiempo de adquisición de los datos. |

### Validación
El modelo utiliza validación estricta de tipos (incluyendo la validez de las URLs) y asegura que los campos críticos no estén vacíos. Se pueden encontrar las pruebas correspondientes en `tests/test_ingestion.py`.
