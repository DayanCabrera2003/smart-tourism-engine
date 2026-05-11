# Manual de Usuario

Este manual describe cómo levantar el sistema, los flujos de uso de cada interfaz (CLI, API REST, UI Streamlit) y cómo correr la evaluación. Está pensado tanto para un usuario final que quiere probar el producto como para el equipo de desarrollo durante la defensa.

---

## 1. Levantar el sistema desde cero

### 1.1 Requisitos

- Python 3.11 o superior
- (Opcional) Docker — solo si quieres correr Qdrant sin instalarlo manualmente
- (Opcional) Pandoc + LaTeX — solo para exportar la documentación a PDF (T114)

### 1.2 Instalación

```bash
git clone https://github.com/DayanCabrera2003/smart-tourism-engine.git
cd smart-tourism-engine

python -m venv venv
source venv/bin/activate

pip install -e ".[dev]"
```

### 1.3 Variables de entorno

```bash
cp .env.example .env
# Edita .env y rellena al menos LLM_API_KEY si vas a usar RAG.
```

Las variables relevantes:

| Variable | Necesaria para | Notas |
|---|---|---|
| `QDRANT_URL` | búsqueda semántica / híbrida / multimodal / recomendación | Default `http://localhost:6333` |
| `LLM_API_KEY` | RAG (`/ask`) | Free tier de Google AI Studio |
| `LLM_PROVIDER` | RAG | `gemini` (default) o `ollama` |
| `TAVILY_API_KEY` | Fallback web | Opcional |
| `OPENTRIPMAP_API_KEY` | Ingesta extra desde OpenTripMap | Opcional |

### 1.4 Orden de ejecución mínimo

```bash
# 1. Ingestar el corpus
python -m src.cli ingest wikivoyage

# 2. Recalcular popularidad (T099)
python scripts/compute_popularity.py

# 3. Construir el índice invertido (modos boolean y híbrido)
python -m src.cli build-index

# 4. Levantar Qdrant (en otra terminal)
docker run -p 6333:6333 -v $(pwd)/qdrant_storage:/qdrant/storage qdrant/qdrant

# 5. Materializar embeddings densos en Qdrant
python scripts/init_qdrant.py
python -m src.cli embed

# 6. (Opcional) Indexar imágenes para multimodal
python -m src.cli embed-images

# 7. Levantar la API
uvicorn src.api.main:app --reload

# 8. (En otra terminal) Levantar la UI
streamlit run src/ui/app.py
```

La UI queda en `http://localhost:8501`, la API en `http://localhost:8000` y la documentación Swagger automática en `http://localhost:8000/docs`.

---

## 2. CLI

Todos los comandos se ejecutan desde la raíz del repo con el venv activo.

### 2.1 `python -m src.cli --help`

Lista todos los comandos:

```
ingest wikivoyage         Procesa páginas de Wikivoyage al JSONL canónico.
build-index               Construye data/processed/index.pkl desde el JSONL.
embed                     Genera embeddings densos y los sube a Qdrant.
embed-images              Indexa imágenes con CLIP en destinations_image.
evaluate                  Corre los recuperadores contra queries.json y produce métricas + plots (T108-T109).
```

### 2.2 `evaluate` (T108)

Ejemplos comunes:

```bash
# Default: corre los tres modos (boolean, semantic, hybrid) con top_k=10
python -m src.cli evaluate

# Solo Booleano (no requiere Qdrant)
python -m src.cli evaluate --modes boolean --top-k 10

# Volcar reporte completo a JSON
python -m src.cli evaluate --output data/eval/report.json

# Saltar la generación de gráficas
python -m src.cli evaluate --no-plots
```

La salida es una tabla en stdout con seis métricas por modo, plus los PNGs en `docs/figures/`. Si Qdrant no está disponible, los modos `semantic` y `hybrid` aparecen con `available=False` pero `boolean` sigue produciendo métricas válidas.

---

## 3. API REST

### 3.1 Endpoints disponibles

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Liveness probe. |
| POST | `/search` | Booleano Extendido (p-norm). |
| POST | `/search/semantic` | Búsqueda densa en Qdrant. |
| POST | `/search/hybrid` | Combinación lineal léxica + semántica. |
| POST | `/search/image-by-text` | CLIP texto → imágenes. |
| POST | `/search/by-image` | Upload de imagen → destinos similares. |
| POST | `/search/multimodal` | Texto + imagen opcional combinados. |
| POST | `/ask` | RAG (respuesta + fuentes). |
| POST | `/ask/stream` | RAG con SSE streaming. |
| POST | `/recommend` | Recomendación por perfil. |

### 3.2 Ejemplos con curl

```bash
# Sanity check
curl http://localhost:8000/health
# {"status":"ok"}

# Búsqueda léxica
curl -X POST http://localhost:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"history AND museum","top_k":5,"p":2.0}'

# Recomendación con perfil sintético
curl -X POST http://localhost:8000/recommend \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"synthetic:cultural","top_k":5,"mode":"hybrid"}'

# RAG conversacional
curl -X POST http://localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"query":"¿Qué ciudades históricas debería visitar en España?","top_k":5}'
```

### 3.3 Manejo de errores (T110)

Todos los errores devuelven JSON con la misma forma:

```json
{ "code": "service_unavailable", "message": "..." }
```

| Status | `code` | Cuándo ocurre |
|---|---|---|
| 200 | — | OK |
| 422 | `validation_error` | Payload malformado (campo faltante, fuera de rango, etc.) |
| 503 | `service_unavailable` | Qdrant caído, índice no construido, LLM no responde |
| 500 | `internal_error` | Bug imprevisto (el body nunca filtra el stack) |

---

## 4. UI Streamlit

La interfaz web tiene cuatro pestañas tras un onboarding inicial.

### 4.1 Onboarding (T097)

Al abrir la app por primera vez, se pide elegir un perfil sintético entre seis (mochilero, familia, luna de miel, aventurero, cultural, lujo). La selección queda en `st.session_state` y la sidebar muestra un botón "Cambiar perfil" para volver al onboarding.

### 4.2 Pestaña "Buscar destinos"

1. Escribe la consulta. Si seleccionas el modo Booleano usa `AND` / `OR` en mayúsculas (`playa AND España`). En semántico o híbrido usa lenguaje natural.
2. El sidebar permite ajustar `top_k` (1-50), `p` (1-10, solo modos léxico/híbrido) y `alpha` (0-1, solo híbrido).
3. Marca **"Agrupar por estrategia de posicionamiento"** (T103) para ver los resultados en cuatro secciones expandibles: Más relevantes, Populares, Recientes, Variados por país.
4. Marca **"Mostrar mapa interactivo"** (T104) para renderizar los destinos geocodificados en un mapa Folium con marcadores y popups.

### 4.3 Pestaña "Preguntar" (RAG)

1. Escribe una pregunta en lenguaje natural.
2. La respuesta aparece en streaming.
3. Las citas `[1]`, `[2]`... corresponden a los destinos listados al final con expanders.
4. Si aparece "Información insuficiente", la pregunta cae fuera de lo que el corpus contiene (y, si configuraste `TAVILY_API_KEY`, el fallback web busca en línea).

### 4.4 Pestaña "Buscar por imagen" (multimodal)

Dos modos:

- **Subir imagen**: carga un archivo JPEG/PNG. El sistema embebe la imagen con CLIP y devuelve destinos visualmente similares.
- **Descripción de texto**: escribe lo que quieres ver (`playa tropical con palmeras`). La query se embebe con CLIP y busca en `destinations_image`.

Si no hay imágenes indexadas, el endpoint devuelve 503 con un mensaje claro.

### 4.5 Pestaña "Recomendado para ti"

1. La pestaña lee el perfil del onboarding.
2. Ajusta cuántas recomendaciones quieres (1-20).
3. Pulsa "Cargar recomendaciones". El sistema llama a `/recommend` con `mode=hybrid`.
4. La pestaña muestra qué persona se usó como ancla (e.g. `synthetic:cultural`) y las cards de los destinos sugeridos.

---

## 5. Evaluación

Para reproducir el reporte de métricas:

```bash
# Regenerar queries.json si cambió el corpus
python scripts/build_eval_queries.py

# Correr la evaluación con los tres modos
python -m src.cli evaluate --top-k 10

# Ver las gráficas
xdg-open docs/figures/metrics_by_mode.png
xdg-open docs/figures/heatmap_P_at_k.png
xdg-open docs/figures/heatmap_nDCG_at_k.png
```

El archivo `data/eval/queries.json` contiene 22 queries anotadas con reglas objetivas (ver [docs/14_evaluacion.md](14_evaluacion.md) para la metodología).

---

## 6. Pruebas

```bash
# Lint
ruff check src tests scripts

# Suite completa (500+ tests, sin servicios externos)
pytest -q

# Solo tests de un capítulo
pytest tests/test_evaluation_metrics.py -q
pytest tests/test_api_robustness.py -q
```

---

## 7. Guión de la demo (T115)

Para una demo de 10 minutos:

1. **0-1 min**: Mostrar el problema y los seis perfiles de usuario.
2. **1-3 min**: Búsqueda léxica con `AND`/`OR` y deslizar `p` para mostrar el efecto del p-norm.
3. **3-5 min**: Cambiar a modo Híbrido, mostrar diferencias en queries en lenguaje natural.
4. **5-7 min**: Tab Preguntar — pregunta con citaciones y streaming.
5. **7-8 min**: Tab Recomendado para ti — cambiar perfil y observar cambios.
6. **8-9 min**: Activar el mapa interactivo y las secciones de posicionamiento.
7. **9-10 min**: Mostrar el reporte de evaluación y discutir los trade-offs entre modos.
