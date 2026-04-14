# 02 - Arquitectura del Sistema

Esta sección describe la arquitectura técnica del Smart Tourism Engine, los módulos que lo componen y sus responsabilidades.



## Estructura de Módulos (src/)

- **ingestion/**: Adquisición de datos desde fuentes externas (Wikivoyage, OpenTripMap), normalización y almacenamiento inicial.
- **indexing/**: Preprocesamiento de texto (tokenización, stemming) y construcción del índice invertido y embeddings.
- **retrieval/**: Lógica de búsqueda principal (Booleano Extendido, semántica e híbrida).
- **rag/**: Integración con LLM para generación de respuestas contextualizadas basadas en los resultados de búsqueda.
- **web_search/**: Módulo de fallback para búsquedas en la web cuando la información local es insuficiente.
- **multimodal/**: Soporte para búsqueda por imágenes y embeddings CLIP.
- **recommendation/**: Algoritmos de recomendación personalizados para los usuarios.
- **api/**: Definición de rutas FastAPI, esquemas y lógica de servidor.
- **ui/**: Implementación de la interfaz de usuario con Streamlit.

## Persistencia: SQLite vs Qdrant

El sistema utiliza dos mecanismos de persistencia con responsabilidades distintas y complementarias:

### SQLite — Metadatos del catálogo

SQLite (via SQLAlchemy) almacena el catálogo estructurado de destinos turísticos en `data/processed/destinations.db`. Se eligió SQLite porque:

- **Sin servidor**: no requiere infraestructura adicional; el archivo `.db` es portátil y reproducible.
- **Datos estructurados**: los metadatos (nombre, país, región, coordenadas, tags, fuente) encajan naturalmente en un esquema relacional con tipado estático.
- **Upsert nativo**: SQLite soporta `INSERT OR REPLACE` (expuesto via `on_conflict_do_update` en SQLAlchemy), lo que simplifica la ingesta incremental de destinos.
- **Consultas SQL**: filtrado por país, región o fuente se expresa de forma directa y eficiente sin necesidad de un ORM pesado.
- **Escala suficiente**: para un corpus de miles a decenas de miles de destinos, SQLite ofrece rendimiento adecuado sin operaciones de mantenimiento.

La tabla `destinations` en `src/ingestion/store.py` espeja el modelo Pydantic `Destination`, con listas (tags, image_urls) serializadas como JSON en columnas `TEXT`.

### Qdrant — Índice vectorial semántico

Qdrant gestiona los embeddings de texto (y en fases posteriores, imágenes CLIP). Se eligió Qdrant porque:

- **Búsqueda por similitud**: la recuperación semántica requiere distancias en espacios de alta dimensión (cosine, dot product), operación no soportada eficientemente por SQL.
- **ANN indexing**: Qdrant implementa HNSW para búsqueda aproximada de vecinos más cercanos con latencia sub-segundo.
- **Filtrado combinado**: permite combinar filtros de metadatos (país, región) con búsqueda vectorial en una sola consulta, optimizando la fase de recuperación híbrida.
- **Persistencia propia**: los vectores y payloads se almacenan en `data/processed/qdrant/`, desacoplados del catálogo relacional.

### Relación entre ambos

El `id` de cada destino es la clave primaria en SQLite y el `id` del punto en Qdrant, permitiendo joins lógicos en la capa de recuperación: Qdrant retorna IDs relevantes y SQLite provee los metadatos completos para la respuesta final.

## Gestión de Datos (data/)

- **raw/**: Datos crudos obtenidos de los crawlers y scrapers (ignorado por Git).
- **processed/**: Índices construidos, caché de embeddings y datos limpios listos para el sistema.

## Otros Directorios

- **tests/**: Pruebas unitarias e integración para asegurar la robustez del sistema.
- **docs/**: Documentación técnica detallada siguiendo el formato LNCS.
- **docker/**: Configuraciones para la contenedorización del sistema.
- **scripts/**: Utilidades para tareas administrativas y de compilación del informe.

## Endpoints de la API

La aplicación FastAPI vive en `src/api/main.py` y se arranca con `uvicorn src.api.main:app --reload`.

| Método | Ruta      | Descripción                                                                 | Respuesta                 |
|--------|-----------|-----------------------------------------------------------------------------|---------------------------|
| GET    | `/health` | Sonda de disponibilidad del servicio (liveness probe).                      | `{"status": "ok"}` (200)  |
| POST   | `/search` | Recupera destinos aplicando el Booleano Extendido (p-norm) sobre el índice. | `SearchResponse` (200)    |

### `POST /search` (T040)

Delega en `ExtendedBoolean.search` usando el índice invertido persistido en `data/processed/index.pkl`. El índice se carga una sola vez y se comparte vía `Depends(get_index)`, lo que permite inyectarlo en tests con `app.dependency_overrides`.

**Request** (`SearchRequest`):

```json
{
  "query": "beach OR mountain",
  "top_k": 5
}
```

- `query` (str, obligatorio): consulta con operadores `AND` / `OR` en mayúsculas.
- `top_k` (int, 1-100, por defecto 10): número máximo de resultados.

**Response** (`SearchResponse`): lista de `DestinationResult` ordenada de mayor a menor `score`.

```json
{
  "results": [
    {"id": "wikivoyage-varadero", "score": 0.63},
    {"id": "wikivoyage-tokyo",    "score": 0.41}
  ]
}
```

- `results[*].id` (str): identificador del destino en el corpus.
- `results[*].score` (float, `[0, 1]`): score del Booleano Extendido.

Si el índice no está disponible en disco, la ruta responde `503`. Los schemas `SearchRequest`, `SearchResponse` y `DestinationResult` viven en [`src/api/schemas.py`](../src/api/schemas.py) (T041) y se reutilizan desde la API y la futura UI.

## Manejo de errores (T042)

El módulo [`src/api/middleware.py`](../src/api/middleware.py) centraliza dos responsabilidades transversales del servicio, registradas en `app` mediante `middleware.install(app)`:

### Logging de requests

`RequestLoggingMiddleware` envuelve cada request y emite un log `INFO` al logger `smart_tourism_engine.api` con los campos `request_id`, `method`, `path`, `status_code` y `duration_ms`. El `request_id` (12 hex) se expone además como cabecera `X-Request-ID` en la respuesta para correlacionar logs con clientes. Si el handler lanza una excepción no capturada, se emite un log `ERROR` con stack trace antes de re-lanzarla para que el handler de excepciones la formatee.

### Respuesta uniforme de errores

Todos los errores devueltos por la API siguen el mismo contrato JSON:

```json
{
  "code": "validation_error",
  "message": "Request payload inválido."
}
```

| Origen                                | `status` | `code`                |
|---------------------------------------|----------|-----------------------|
| `HTTPException(404, ...)`             | 404      | `not_found`           |
| `HTTPException(503, ...)` (sin índice)| 503      | `service_unavailable` |
| `RequestValidationError` (Pydantic)   | 422      | `validation_error`    |
| Excepción no controlada               | 500      | `internal_error`      |
| Otros `HTTPException`                 | `exc.status_code` | `http_error` (fallback) |

La tabla `_HTTP_CODE_MAP` en `middleware.py` concentra el mapeo `status_code → code`, evitando dispersión de literales entre handlers. Los códigos son identificadores estables pensados para que la UI y clientes externos discriminen casos sin parsear mensajes en español.

## Observabilidad

El sistema utiliza un esquema de **Logging Estructurado** en formato JSON, facilitando su integración con herramientas modernas de agregación y análisis de logs (como ELK Stack o Loki).

- **Estandarización**: Todos los logs del sistema, incluyendo los de librerías de terceros y FastAPI, son redirigidos a la salida estándar (`stdout`) con una estructura coherente.
- **Campos base**: `timestamp` (ISO-8601 UTC), `level`, `message`, `module`, `funcName` y `lineno`.
- **Configuración**: El nivel de detalle se ajusta mediante la variable de entorno `LOG_LEVEL` (vía `src/config.py`).

## Estrategia de Testing

El proyecto adopta un enfoque de desarrollo basado en pruebas (TDD incremental) para asegurar la integridad de los componentes del SRI.

- **Tests de Humo (Smoke Tests)**: Verificaciones rápidas de la configuración y dependencias base (`tests/test_smoke.py`).
- **Tests Unitarios**: Validación de funciones puras, lógica de recuperación y normalización de texto.
- **Tests de Integración**: Pruebas de flujo completo entre la API, el índice invertido y Qdrant.
- **Evaluación de RI**: Medición de métricas de calidad (Precision@k, Recall, etc.) sobre el corpus de prueba.

Para ejecutar los tests:
```bash
pytest
```
o con reporte de cobertura:
```bash
pytest --cov=src
```
