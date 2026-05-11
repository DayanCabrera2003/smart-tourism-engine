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

## 7. Guión de la demo final (T115)

Demo de **10 minutos** que recorre toda la pila terminada en Corte 3. Pensado para ejecutarse delante del tribunal con el sistema corriendo en local.

### Preparación (5 minutos antes de la demo)

```bash
# Verificar entorno
source venv/bin/activate
python -c "import sys; print(sys.version)"     # 3.11+

# Levantar Qdrant (terminal 1)
docker run -p 6333:6333 -v $(pwd)/qdrant_storage:/qdrant/storage qdrant/qdrant

# Asegurarse de que la API arrancó limpia (terminal 2)
uvicorn src.api.main:app --reload

# UI (terminal 3)
streamlit run src/ui/app.py
```

Checklist pre-demo:

- [ ] `curl http://localhost:8000/health` responde `{"status":"ok"}`.
- [ ] `curl http://localhost:6333/collections` lista `destinations_text`.
- [ ] La UI carga sin errores en el navegador.
- [ ] `LLM_API_KEY` está configurada y `/ask` responde sin 503.
- [ ] El monitor está en resolución 1920x1080 mínimo para que las gráficas se vean.

### 0:00 - 1:00 — Contexto del problema

- Abrir [docs/01_dominio.md](01_dominio.md) en pantalla.
- Explicar la motivación: "buscar destinos turísticos en lenguaje natural sin terminar en un buscador genérico con resultados comerciales".
- Mencionar los seis perfiles de viajero como segmentación natural del dominio.
- Mostrar las cinco modalidades soportadas (léxica, semántica, híbrida, conversacional, multimodal, recomendación).

### 1:00 - 2:30 — Recuperador léxico con p-norm

- Abrir la UI en modo **Booleano Extendido**.
- Query: `playa AND mar`. Mostrar resultados.
- Mover el slider `p` de 1.0 a 10.0. Observar cómo el orden cambia (con `p` alto, AND se vuelve estricto). Explicar la interpolación Salton/Fox/Wu (citar [docs/03_modelo_ri.md](03_modelo_ri.md)).
- Query: `madrid`. Mostrar top-1 = wikivoyage-madrid con score 0.589.

### 2:30 - 4:00 — Búsqueda semántica e híbrida

- Cambiar a modo **Semántico**.
- Query: `playas tranquilas para luna de miel`. Mostrar que devuelve destinos relevantes aunque ninguno contenga literalmente la palabra "luna de miel".
- Cambiar a modo **Híbrido** con `alpha=0.5`. Misma query.
- Mover `alpha` para mostrar la transición entre puro semántico y puro léxico.
- Mencionar que `alpha=1.0` colapsa al modo Booleano y `alpha=0.0` al modo Semántico.

### 4:00 - 5:30 — RAG con citas y streaming

- Cambiar al tab **Preguntar**.
- Pregunta: `¿Qué ciudades históricas españolas debería visitar para entender la herencia romana y árabe?`
- Mientras la respuesta hace streaming, explicar que:
  - El recuperador en modo híbrido obtiene los 5 destinos más relevantes.
  - El prompt instruye al LLM a usar **solo** ese contexto.
  - Las fuentes [1], [2], [3]... aparecen en línea y se expanden al final con la descripción completa del destino.
- Si configuró Tavily, hacer una pregunta fuera del corpus (`hoteles boutique en Tofino 2026`) para demostrar el badge `[Búsqueda web]`.

### 5:30 - 7:00 — Recomendación con perfiles sintéticos

- Cambiar el perfil en la sidebar a **mochilero**.
- Tab **Recomendado para ti** → Cargar recomendaciones.
- Mostrar la persona ancla (`synthetic:mochilero`) y los destinos sugeridos.
- Cambiar perfil a **lujo**, recargar. Mostrar destinos totalmente distintos.
- Explicar la estrategia híbrida (content-based + pseudo-colaborativo) en una frase: "embedding del perfil + snap a la persona más cercana, promediados con `alpha=0.6`".
- Referenciar [docs/11_recomendacion.md](11_recomendacion.md) para el detalle algorítmico.

### 7:00 - 8:00 — Posicionamiento avanzado: secciones y mapa

- Volver al tab **Buscar destinos** con la query `ciudades históricas`.
- Activar **Agrupar por estrategia de posicionamiento**.
- Mostrar las cuatro secciones: Más relevantes (orden original), Populares (Turín al frente por popularity=0.696), Recientes (idéntico porque toda la ingesta fue el mismo día), Variados (un país por slot).
- Activar **Mostrar mapa interactivo**.
- Mostrar el mapa Folium con marcadores y popups; hacer click en uno para mostrar el detalle.
- Mencionar que 21 de cada 30 destinos del corpus tienen coordenadas (cobertura 70%).

### 8:00 - 9:00 — Evaluación cuantitativa

- Cerrar la UI, abrir terminal.
- Mostrar `python -m src.cli evaluate --modes boolean --top-k 10`.
- Apuntar a los números (P@10=0.11, R@10=0.27, MAP=0.22, MRR=0.36, nDCG@10=0.29).
- Abrir `docs/figures/metrics_by_mode.png` y los dos heatmaps. Explicar:
  - Bar chart: comparación agregada entre modos (cuando Qdrant esté materializado, mostrará los tres).
  - Heatmap P@k: dónde el modo brilla y dónde falla, query por query.
- Mostrar el contenido de `data/eval/queries.json` y explicar la metodología de anotación por reglas objetivas (T105).

### 9:00 - 10:00 — Decisiones, limitaciones y cierre

- Abrir [docs/17_critica_y_deficiencias.md](17_critica_y_deficiencias.md).
- Mencionar las tres limitaciones más relevantes:
  1. Corpus mono-fuente (Wikivoyage en inglés, 206 destinos).
  2. Imágenes no descargadas (multimodal funcional pero sin contenido real).
  3. SQLite drift que la UI maneja con degradación elegante.
- Resaltar las tres bondades técnicas:
  1. Modelo Booleano Extendido con `p` continuo y validado empíricamente.
  2. Separación de responsabilidades + 500+ tests pytest sin servicios externos.
  3. Manejo unificado de errores (T110) con 503 explícito cuando Qdrant cae.
- Cerrar con propuestas de mejora a corto plazo (sección 4 del capítulo 17).

### Si algo falla en vivo

| Problema | Plan B |
|---|---|
| Qdrant no levanta | Usar solo el modo Booleano. La evaluación funciona, las secciones de posicionamiento también. |
| Gemini cae o no hay internet | Configurar `LLM_PROVIDER=ollama` previamente. El RAG funciona local. |
| Streamlit no responde | Demo por API con curl + `docs/12_interfaz.md` y `docs/figures/*.png`. |
| La pregunta del jurado es sobre un tema no implementado | Apoyarse en [docs/17_critica_y_deficiencias.md](17_critica_y_deficiencias.md) sección "Limitaciones que no son resolvibles dentro del alcance". |

### Cierre

```
"El sistema implementa los nueve módulos del plan más una capa de
posicionamiento, una de evaluación con cinco métricas estándar y
documentación versionada con bibliografía. La crítica y las
limitaciones están escritas con honestidad en el capítulo 17. Estamos
listos para preguntas."
```
