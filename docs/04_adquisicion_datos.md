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

## Fuentes de Datos

### 1. Wikivoyage
[Wikivoyage](https://en.wikivoyage.org/) es una guía de viajes libre, escrita de forma colaborativa por voluntarios. Es una fuente ideal para este proyecto debido a:
- **Estructura del Dominio**: Los artículos están organizados por destinos (ciudades, regiones), facilitando la creación del catálogo.
- **Multimodalidad**: Contiene referencias a imágenes de alta calidad de Wikimedia Commons.
- **Licencia**: Publicado bajo **CC BY-SA 3.0**, permitiendo su uso y transformación siempre que se atribuya y se comparta bajo la misma licencia.

#### Adquisición de Wikivoyage (MVP)
Para el desarrollo inicial, se ha implementado un pipeline de adquisición ligero:
1. **Descarga (`scripts/download_wikivoyage.py`)**: Utiliza la API de MediaWiki para obtener el contenido crudo (wikitext) de destinos seleccionados de España en formato JSON.
2. **Parsing (`src/ingestion/wikivoyage.py`)**: Procesa el wikitext, extrae coordenadas geográficas, limpia etiquetas y genera objetos `Destination` unificados en `data/raw/destinations_raw.jsonl`.

#### Diagrama del Pipeline

```mermaid
graph LR
    WV[Wikivoyage API] -->|Download| Raw[JSON Crudo]
    Raw -->|Parser| Parse[Modelo Destination Raw]
    Parse -->|Normalización| Norm[Texto Limpio y Normalizado]
    Norm -->|Guardar| Proc[destinations.jsonl]
    
    subgraph Adquisición
    WV
    Raw
    end
    
    subgraph Preprocesamiento
    Parse
    Norm
    end
    
    subgraph Salida
    Proc
    end
```

La implementación coordinada se encuentra en `src/ingestion/pipeline.py`.
