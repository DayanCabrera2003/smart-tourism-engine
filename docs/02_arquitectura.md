# 02 - Arquitectura del Sistema

Esta sección describe la arquitectura técnica del Smart Tourism Engine, los módulos que lo componen y sus responsabilidades.



## Estructura de Módulos (src/)

- **ingestion/**: Adquisición de datos desde fuentes externas (Wikivoyage, Wikidata/Wikipedia, OpenTripMap), normalización y almacenamiento inicial.
- **indexing/**: Preprocesamiento de texto (tokenización, stemming) y construcción del índice invertido y embeddings.
- **retrieval/**: Lógica de búsqueda principal (Booleano Extendido, semántica e híbrida) más módulos auxiliares (expansión bilingüe, cross-encoder rerank, filtro geográfico, popularidad, frescura, MMR).
- **rag/**: Integración con LLM para generación de respuestas contextualizadas basadas en los resultados de búsqueda.
- **web_search/**: Módulo de fallback para búsquedas en la web cuando la información local es insuficiente.
- **multimodal/**: Soporte para búsqueda por imágenes y embeddings CLIP.
- **recommendation/**: Algoritmos de recomendación personalizados para los usuarios.
- **evaluation/**: Métricas P@k, R@k, F1@k, MAP, MRR y nDCG@k sobre el ground truth de `data/eval/queries_v2.json`.
- **bootstrap/**: Pipeline reproducible que lleva el sistema desde "data/ vacío" hasta "indexes listos" en una operación monitorizada (ver sección dedicada más abajo).
- **api/**: Definición de rutas FastAPI, esquemas y lógica de servidor.
- **ui/**: Implementación de la interfaz de usuario con Streamlit, incluido el tab "Sistema" que dispara el bootstrap pipeline.

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
- **scripts/**: Utilidades para tareas administrativas y de compilación del informe.

## Endpoints de la API

La aplicación FastAPI vive en `src/api/main.py` y se arranca con `uvicorn src.api.main:app --reload`.

| Método | Ruta | Descripción | Respuesta |
|--------|------|-------------|-----------|
| GET    | `/health` | Sonda de disponibilidad (liveness probe). | `{"status": "ok"}` (200) |
| POST   | `/search` | Booleano Extendido (p-norm) sobre el índice invertido. | `SearchResponse` (200) |
| POST   | `/search/semantic` | Embeddings densos en Qdrant; opción de cross-encoder. | `SearchResponse` (200) |
| POST   | `/search/hybrid` | Mezcla Booleano + semántico con peso `alpha` (default 0.4). | `SearchResponse` (200) |
| POST   | `/search/image-by-text` | CLIP text-to-image sobre `destinations_image`. | `ImageSearchResponse` (200) |
| POST   | `/search/by-image` | CLIP image-to-image (multipart upload). | `ImageSearchResponse` (200) |
| POST   | `/search/multimodal` | Texto + imagen opcional, fusión con peso `alpha`. | `ImageSearchResponse` (200) |
| POST   | `/ask` | Pregunta natural → respuesta RAG con citas. | `AskResponse` (200) |
| POST   | `/ask/stream` | Igual que `/ask` pero en streaming SSE. | `text/event-stream` (200) |
| POST   | `/recommend` | Destinos según perfil sintético + intereses + historial. | `RecommendResponse` (200) |
| POST   | `/feedback` | Voto thumbs up/down por (user_id, query, destination_id). | `FeedbackResponse` (200) |
| GET    | `/bootstrap/needed` | ¿El sistema necesita inicialización? | `NeededResponse` (200) |
| GET    | `/bootstrap/status` | Snapshot del progreso del pipeline (fase, %, log). | `StatusResponse` (200) |
| POST   | `/bootstrap/start` | Arranca el pipeline en thread de background. | `StartResponse` (200) |
| POST   | `/bootstrap/reset/indexes` | Borra colecciones Qdrant + `index.pkl`. | `ResetResponse` (200) |
| POST   | `/bootstrap/reset/all` | Borra colecciones + index + JSONL + SQLite + raw. | `ResetResponse` (200) |

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
| `qdrant_client.ResponseHandlingException` (T110) | 503 | `service_unavailable` |
| `qdrant_client.UnexpectedResponse` (T110) | 503 | `service_unavailable` |
| Excepción no controlada               | 500      | `internal_error`      |
| Otros `HTTPException`                 | `exc.status_code` | `http_error` (fallback) |

La tabla `_HTTP_CODE_MAP` en `middleware.py` concentra el mapeo `status_code → code`, evitando dispersión de literales entre handlers. Los códigos son identificadores estables pensados para que la UI y clientes externos discriminen casos sin parsear mensajes en español.

### T110 — Robustez end-to-end

Los smoke tests previos detectaron que cuatro endpoints (`/search/semantic`, `/search/hybrid`, `/ask`, `/recommend`) devolvían **500** cuando Qdrant no respondía, en lugar del 503 esperado. La causa: la excepción `ResponseHandlingException` de `qdrant-client` subía hasta el handler genérico de excepciones.

T110 registra dos handlers nuevos en `middleware.install()`:

- `ResponseHandlingException` → 503 `service_unavailable` con mensaje "Servicio vectorial (Qdrant) no disponible".
- `UnexpectedResponse` → 503 con el mismo cuerpo.

Esto cubre los cuatro endpoints semánticos sin tocar su código, porque el handler captura la excepción a nivel de aplicación.

**Pruebas de robustez**: `tests/test_api_robustness.py` agrega 13 casos adversariales:

- **422 validación**: query vacío, `top_k=0`, `top_k=999`, `p` fuera de rango, mode inválido, `alpha` fuera de rango, query ausente.
- **200 happy path** con campo desconocido (Pydantic ignora extras).
- **503 servicio caído** con `ResponseHandlingException` simulada.
- **500 sin filtración** de stack trace cuando hay excepción no manejada — el body siempre es `{"code": "internal_error", "message": "Error interno del servidor."}`.
- **Sanity**: el handler de Qdrant está efectivamente registrado en `app.exception_handlers`.

## Observabilidad

El sistema utiliza un esquema de **Logging Estructurado** en formato JSON, facilitando su integración con herramientas modernas de agregación y análisis de logs (como ELK Stack o Loki).

- **Estandarización**: Todos los logs del sistema, incluyendo los de librerías de terceros y FastAPI, son redirigidos a la salida estándar (`stdout`) con una estructura coherente.
- **Campos base**: `timestamp` (ISO-8601 UTC), `level`, `message`, `module`, `funcName` y `lineno`.
- **Configuración**: El nivel de detalle se ajusta mediante la variable de entorno `LOG_LEVEL` (vía `src/config.py`).

## Empaquetado y despliegue con Docker

El repositorio incluye un `Dockerfile` único que sirve a la API (FastAPI) y a la UI (Streamlit) cambiando el `command` en `docker-compose.yml`. La orquestación reúne tres servicios:

| Servicio | Imagen | Puerto host | Rol |
|---|---|---|---|
| `qdrant` | `qdrant/qdrant:latest` | 6333, 6334 | Base vectorial |
| `api` | `ste-app:latest` (build local) | 8000 | FastAPI + uvicorn |
| `ui` | `ste-app:latest` (build local) | 8501 | Streamlit |

Decisiones de diseño:

- **Imagen base `python:3.12-slim`** con `torch==2.5.1+cpu` instalado explícitamente desde el índice de PyTorch para evitar arrastrar CUDA (~2 GB extra) que el despliegue de demo no necesita.
- **Pin versions de `sentence-transformers==5.3.0` y `transformers==5.5.0`**, ya que la combinación más reciente (transformers 5.6+) rompe `sentence-transformers 5.3` por un cambio interno de `accelerate`. Pinear garantiza reproducibilidad bit-exacta de los embeddings entre el entorno local y el contenedor.
- **Volúmenes con bind mount** para `data/` y `qdrant_storage/`: el catálogo y los vectores sobreviven a `docker compose down`, y el desarrollador puede inspeccionar/editar archivos desde el host sin entrar al contenedor.
- **Volumen nombrado `ste_hf_cache`** para los pesos de HuggingFace; la primera descarga (~150 MB de embedder + 600 MB opcionales de CLIP) se reutiliza entre reinicios y entre rebuilds de la imagen.
- **Usuario `appuser` (UID 1000)** dentro del contenedor coincide con el UID típico del host Linux, evitando problemas de permisos en los archivos creados por el bootstrap pipeline.
- **Healthcheck propio** sobre `/health` en el contenedor `api`; el contenedor `ui` declara `depends_on: api: condition: service_healthy` para no arrancar antes de que la API esté lista.
- **El `.dockerignore`** excluye `venv/`, `data/`, `qdrant_storage/`, `docs/`, `tests/` y demás artefactos que no son necesarios en runtime, manteniendo la imagen alrededor de los 3 GB en disco (817 MB el manifiesto final).

El despliegue completo está documentado en el capítulo 15 (`docs/15_despliegue.md`), incluyendo los pasos de `docker compose build`, `up`, `logs`, `down`, y la inicialización del corpus desde la UI.

## Pipeline de bootstrap

El enunciado de la entrega exige que "todos los datos almacenados se eliminen y la carga del sistema indexe su corpus inicial como un paso requerido". Para cumplirlo el sistema incluye un pipeline reproducible (`src/bootstrap/`) expuesto vía API y vía UI.

### Diseño

El paquete `src/bootstrap/` se separa en tres responsabilidades:

| Módulo | Responsabilidad |
|---|---|
| `state.py` | `BootstrapTracker` thread-safe que mantiene fase actual, mensaje, log circular de 30 líneas y porcentaje. Singleton por proceso. |
| `reset.py` | Dos funciones puras: `reset_indexes()` (drop Qdrant + `index.pkl`) y `reset_all()` (lo anterior + JSONL + SQLite + `data/raw/`). Qdrant se limpia vía HTTP, nunca borrando `qdrant_storage/` desde el host. |
| `pipeline.py` | `run(tracker, on_done)` que ejecuta las ocho fases en secuencia. `run_in_thread()` envuelve el call para que la API responda durante los 5-30 minutos del embed/crawl. |

### Fases

| # | Fase | Detalle |
|---|------|---------|
| 1 | `detect` | Verifica si existen `data/raw/wikivoyage/` y `data/processed/destinations.jsonl` para decidir qué fases saltar. |
| 2 | `crawl` | Solo si no hay raw: descarga ~250 páginas de Wikivoyage con rate limit (REQUEST_DELAY_SECONDS) y respeto a robots.txt. Reporta progreso página a página. |
| 3 | `ingest` | Solo si no hay JSONL: parsea raw → `destinations.jsonl` + upsert en SQLite (vía `src/ingestion/pipeline.py`). |
| 4 | `sqlite` | **Sincronización idempotente del catálogo**: re-upserta todas las filas del JSONL. Cubre el caso en que el JSONL ya existía pero la SQLite se quedó desincronizada (problema histórico documentado en el capítulo 17). |
| 5 | `index` | Construye el índice invertido y lo persiste en `data/processed/index.pkl`. |
| 6 | `popularity` | Recalcula `popularity` para todo el corpus (`scripts/compute_popularity.py`) y actualiza JSONL + SQLite. |
| 7 | `qdrant` | Crea (idempotente) la colección `destinations_text` con `vector_size=384`, `distance=Cosine`. |
| 8 | `embed` | Recorre el JSONL embebiendo por lotes de 32 y subiendo a Qdrant. Reporta cada batch. |

### Endpoints

Los cinco endpoints `/bootstrap/*` (ver tabla anterior) cubren los tres casos de uso:

1. **¿Debo inicializar?** `GET /bootstrap/needed` chequea presencia del JSONL, del índice y del conteo de puntos en Qdrant.
2. **Inicializar.** `POST /bootstrap/start` lanza el pipeline en thread. `GET /bootstrap/status` se polea cada ~2 s para mostrar la barra de progreso.
3. **Limpiar.** `POST /bootstrap/reset/indexes` o `/reset/all` para los dos escenarios de cleanup.

### Invalidación de cachés

`src/api/main.py` mantiene singletons con `@lru_cache(maxsize=1)` para el índice, las destinations de SQLite, el embedder, el cliente Qdrant y la pipeline RAG. Tras un bootstrap o un reset el router (`src/api/bootstrap_router.py`) dispara un callback que limpia las ocho cachés, garantizando que la próxima petición reconstruya los handles contra el estado nuevo en disco. Sin esta invalidación, la API serviría el índice viejo aunque Qdrant ya tuviera los vectores nuevos.

### Integración con la UI

El tab "Sistema" de Streamlit (`src/ui/bootstrap_panel.py`) consume `/bootstrap/*` para mostrar:

- Banner persistente cuando `needed=true` en cualquier tab.
- Barra de progreso con porcentaje, fase actual y log circular.
- Auto-refresh cada 2 segundos mientras `status="running"`.
- Tres botones: **Inicializar sistema** (verde), **Limpiar índices** (requiere checkbox de confirmación), **Limpiar todo** (requiere escribir `BORRAR` para evitar accidentes).

Este componente está descrito en el capítulo 12.

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
