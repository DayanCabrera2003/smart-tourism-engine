# Smart Tourism Engine

![CI](https://github.com/dayancc/smart-tourism-engine/actions/workflows/ci.yml/badge.svg)

Sistema de Recuperación de Información (SRI) para turismo y viajes. Permite consultas en lenguaje natural sobre destinos turísticos y devuelve resultados rankeados, respuestas generadas con RAG, búsqueda multimodal (texto + imágenes) y recomendaciones personalizadas con re-ranking por popularidad, frescura y perfil de usuario.

Proyecto Integrador del curso de SRI (2025-2026, 2do semestre).

---

## Equipo

- Dayan Cabrera Corvo

---

## Stack técnico

| Capa | Tecnología |
|---|---|
| Backend | FastAPI + Uvicorn |
| UI | Streamlit + streamlit-folium |
| Recuperador léxico | Booleano clásico y Booleano Extendido (p-norm, Salton/Fox/Wu 1983) |
| Embeddings de texto | `intfloat/multilingual-e5-small` (384 dim, multilingüe) |
| Embeddings multimodales | `clip-ViT-B-32` (512 dim) |
| Base vectorial | Qdrant |
| Persistencia metadatos | SQLite (vía SQLAlchemy) |
| LLM (RAG) | Gemini (configurable a Ollama local) |
| Búsqueda web fallback | Tavily |

---

## Documentación

El informe completo vive en [docs/](docs/). El índice principal está en [docs/00_indice.md](docs/00_indice.md). Por capítulo:

- [docs/02_arquitectura.md](docs/02_arquitectura.md) — arquitectura general y endpoints.
- [docs/03_modelo_ri.md](docs/03_modelo_ri.md) — modelo Booleano Extendido (p-norm).
- [docs/04_adquisicion_datos.md](docs/04_adquisicion_datos.md) — Wikivoyage, OpenTripMap, deduplicación.
- [docs/05_indexacion.md](docs/05_indexacion.md) — tokenización, índice invertido, TF-IDF.
- [docs/06_recuperador.md](docs/06_recuperador.md) — recuperadores léxico, semántico, híbrido.
- [docs/07_base_vectorial.md](docs/07_base_vectorial.md) — Qdrant.
- [docs/08_rag.md](docs/08_rag.md) — pipeline RAG con citaciones y streaming.
- [docs/09_busqueda_web.md](docs/09_busqueda_web.md) — fallback Tavily.
- [docs/10_multimodal.md](docs/10_multimodal.md) — CLIP, búsqueda por imagen.
- [docs/11_recomendacion.md](docs/11_recomendacion.md) — perfiles sintéticos, content-based, pseudo-colaborativo, híbrido.
- [docs/12_interfaz.md](docs/12_interfaz.md) — UI Streamlit, secciones y mapa.
- [docs/13_posicionamiento.md](docs/13_posicionamiento.md) — popularidad, frescura, re-ranker, MMR.
- [docs/15_despliegue.md](docs/15_despliegue.md) — variables de entorno y despliegue.

---

## Despliegue rápido con Docker (recomendado para la entrega)

```bash
git clone <url-del-repositorio>
cd smart-tourism-engine
cp .env.example .env             # editar LLM_API_KEY (Gemini) y, opcional, TAVILY_API_KEY
docker compose build             # ~3-5 min la primera vez
docker compose up -d
```

Abrir `http://localhost:8501`. Si la UI muestra el banner "Sistema no inicializado", ir al tab **Sistema** y pulsar **Inicializar sistema**. La pipeline arranca crawler + ingest + indexación + embeddings con progreso visible en pantalla. El mismo tab expone los botones **Limpiar índices** y **Limpiar TODO** para resetear el sistema antes de grabar el video de defensa (requisito del enunciado).

Documentación completa del despliegue, incluida la rotación de datos y la operación del stack: [docs/15_despliegue.md](docs/15_despliegue.md).

## Instalación (modo desarrollo)

### 1. Requisitos

- Python 3.11 o superior
- (Opcional) Docker — solo si quieres correr Qdrant sin instalarlo manualmente

### 2. Entorno virtual y dependencias

```bash
python -m venv venv
source venv/bin/activate            # Linux / macOS
# .\venv\Scripts\activate           # Windows

pip install -e ".[dev]"
```

### 3. Variables de entorno

Copia el ejemplo y rellena las claves que necesites:

```bash
cp .env.example .env
```

Variables:

| Variable | Necesaria para | Notas |
|---|---|---|
| `QDRANT_URL` | búsqueda semántica, híbrida, multimodal, recomendación | Default `http://localhost:6333` |
| `LLM_API_KEY` | RAG (`/ask`, `/ask/stream`) con Gemini | Free tier de Google AI Studio |
| `LLM_PROVIDER` | RAG | `gemini` (default) o `ollama` |
| `OLLAMA_URL` / `OLLAMA_MODEL` | RAG offline | Solo si `LLM_PROVIDER=ollama` |
| `OPENTRIPMAP_API_KEY` | Ingesta extra desde OpenTripMap | Opcional |
| `TAVILY_API_KEY` | Búsqueda web fallback | Opcional |
| `LOG_LEVEL` | Logging | `INFO` por defecto |
| `DATA_DIR` | Raíz de `data/processed`, `data/raw` | `data` por defecto |

### 4. Pre-commit (opcional)

```bash
pre-commit install
pre-commit run --all-files          # ejecuta black, ruff, isort sobre todo el repo
```

---

## Cómo probar cada feature

A continuación se explica cómo verificar cada bloque funcional del sistema. Los bloques están ordenados por dependencias: lo que necesitas para los siguientes asume que lo anterior ya está hecho.

### A. Suite de tests automatizados

Cubre 507 casos con stubs y datos sintéticos. No requiere servicios externos.

```bash
source venv/bin/activate
ruff check src tests scripts
pytest -q
```

Salida esperada: `All checks passed!` para ruff y `507 passed` para pytest.

Tests específicos por capítulo:

```bash
pytest tests/test_tokenizer.py tests/test_stopwords.py tests/test_stemmer.py     # preprocesamiento
pytest tests/test_inverted_index.py tests/test_tfidf.py                          # indexación
pytest tests/test_boolean.py tests/test_extended_boolean.py tests/test_query_parser.py    # recuperador léxico
pytest tests/test_hybrid.py tests/test_embedder.py tests/test_vector_store.py    # vectorial e híbrido
pytest tests/test_rag_pipeline.py tests/test_rag_prompts.py tests/test_rag_llm_client.py  # RAG
pytest tests/test_web_search_tavily.py tests/test_web_search_trigger.py          # fallback web
pytest tests/test_multimodal.py                                                  # CLIP
pytest tests/test_recommendation_*.py                                            # recomendación
pytest tests/test_popularity.py tests/test_freshness.py tests/test_reranker.py tests/test_diversify.py tests/test_positioning.py    # posicionamiento
pytest tests/test_api_*.py                                                       # endpoints
pytest tests/test_ui_app.py tests/test_ui_recommend.py tests/test_ui_positioning.py tests/test_ui_map.py     # UI
```

### B. Ingestar el corpus (Fase 1)

Descarga páginas de Wikivoyage, normaliza el texto, deduplica y escribe a `data/processed/destinations.jsonl` + SQLite.

```bash
# Descarga (una vez por revisión del corpus)
python scripts/download_wikivoyage.py

# Pipeline de ingesta vía CLI
python -m src.cli ingest wikivoyage

# Estadísticas del corpus actual
python scripts/stats.py
```

Verificación:

```bash
wc -l data/processed/destinations.jsonl     # debe imprimir 200+ líneas
python -c "import json; d=[json.loads(l) for l in open('data/processed/destinations.jsonl')]; print(len(d), 'destinos')"
```

### C. Construir el índice invertido (Fase 2)

```bash
python -m src.cli build-index
```

Verificación rápida sobre el índice real:

```bash
python -c "
from src.indexing.inverted_index import InvertedIndex
from src.retrieval.extended_boolean import ExtendedBoolean
idx = InvertedIndex.load('data/processed/index.pkl')
print(f'docs={idx.doc_count}, vocab={len(idx.vocabulary)}')
eb = ExtendedBoolean(p=2.0)
print(eb.search('madrid', idx, top_k=3))
print(eb.search('beach OR mountain', idx, top_k=3))
"
```

Output esperado: `madrid` devuelve `wikivoyage-madrid` como top-1; `beach OR mountain` devuelve destinos costeros y de montaña.

### D. Levantar la API (Fase 3)

```bash
uvicorn src.api.main:app --reload
```

La API queda en `http://localhost:8000` y la documentación Swagger en `http://localhost:8000/docs`.

Pruebas rápidas con `curl`:

```bash
# Sonda de disponibilidad
curl http://localhost:8000/health
# {"status":"ok"}

# Búsqueda léxica con Booleano Extendido
curl -X POST http://localhost:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"history AND museum","top_k":5,"p":2.0}'
```

La respuesta incluye `id`, `score`, `name`, `country`, `description`, `image_urls`, `popularity`, `fetched_at`, `latitude`, `longitude`.

### E. Levantar Qdrant y materializar embeddings (Fase 4)

Necesario para búsqueda semántica, híbrida, multimodal y recomendación.

```bash
# Opción 1: Docker (recomendado)
docker run -p 6333:6333 -p 6334:6334 \
  -v $(pwd)/qdrant_storage:/qdrant/storage \
  qdrant/qdrant

# Opción 2: binario nativo (ver docs/15_despliegue.md)

# En otra terminal: crear colecciones y materializar embeddings
python scripts/init_qdrant.py
python -m src.cli embed              # destinations_text, ~5-7 min con 957 destinos
```

Verificación:

```bash
curl http://localhost:6333/collections
# debe listar destinations_text (y destinations_image si ejecutaste embed-images)

curl -X POST http://localhost:8000/search/semantic \
  -H 'Content-Type: application/json' \
  -d '{"query":"playas tropicales para luna de miel","top_k":5}'

curl -X POST http://localhost:8000/search/hybrid \
  -H 'Content-Type: application/json' \
  -d '{"query":"city OR culture","top_k":5,"alpha":0.5,"p":2.0}'
```

### F. RAG (Fase 5)

Requiere Qdrant levantado + `LLM_API_KEY` configurada.

```bash
curl -X POST http://localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"query":"¿Qué ciudades históricas debería visitar en España?","top_k":5,"mode":"hybrid","alpha":0.5}'
```

La respuesta trae `answer`, `sources` (con citas inline `[1]`, `[2]`) y `low_confidence`.

Streaming SSE:

```bash
curl -N -X POST http://localhost:8000/ask/stream \
  -H 'Content-Type: application/json' \
  -d '{"query":"Recomienda 3 destinos para mochileros","top_k":5,"mode":"hybrid","alpha":0.5}'
```

### G. Búsqueda web fallback (Fase 6)

Requiere `TAVILY_API_KEY` configurada. Se activa automáticamente cuando el recuperador local no encuentra resultados con score suficiente o el LLM responde "no sé".

Para forzarlo, lanza una query muy específica que no esté en el corpus:

```bash
curl -X POST http://localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"query":"hoteles boutique en Tofino Canadá 2026","top_k":5}'
```

Los `sources` que vengan de Tavily traen `from_web: true` y la UI los marca con el badge `[Búsqueda web]`.

### H. Multimodal con CLIP (Fase 7)

Requiere imágenes descargadas en `data/raw/images/<destination_id>/` y la colección `destinations_image` en Qdrant.

```bash
# Indexar imágenes (requiere CLIP, ~600MB de pesos la primera vez)
python -m src.cli embed-images

# Texto -> imagen
curl -X POST http://localhost:8000/search/image-by-text \
  -H 'Content-Type: application/json' \
  -d '{"query":"playa tropical con palmeras","top_k":5}'

# Imagen subida -> destinos visualmente similares
curl -X POST http://localhost:8000/search/by-image \
  -F 'file=@/ruta/a/tu/imagen.jpg' \
  -F 'top_k=5'

# Multimodal combinado (texto + imagen opcional en base64)
curl -X POST http://localhost:8000/search/multimodal \
  -H 'Content-Type: application/json' \
  -d '{"query":"playa al atardecer","top_k":5,"alpha":0.5}'
```

Nota: si `data/raw/images/` está vacío (caso por defecto en esta entrega), los tres endpoints responden 503 con un mensaje claro.

### I. Recomendación (Fase 8)

Requiere Qdrant + embeddings ya materializados (paso E).

```bash
# Perfil sintético predefinido
curl -X POST http://localhost:8000/recommend \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"synthetic:mochilero","top_k":5,"mode":"hybrid"}'

# Perfil declarado por intereses libres
curl -X POST http://localhost:8000/recommend \
  -H 'Content-Type: application/json' \
  -d '{"interests":["playa","aventura"],"top_k":5,"mode":"hybrid"}'

# Modo content-based puro
curl -X POST http://localhost:8000/recommend \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"synthetic:cultural","mode":"content"}'

# Modo pseudo-colaborativo (snapping a la persona más cercana)
curl -X POST http://localhost:8000/recommend \
  -H 'Content-Type: application/json' \
  -d '{"user_id":"synthetic:lujo","mode":"collaborative"}'
```

La respuesta incluye `persona` (qué perfil sintético se usó como ancla) y `empty: true` si no había señal suficiente para recomendar.

Personas disponibles: `mochilero`, `familia`, `luna_de_miel`, `aventurero`, `cultural`, `lujo`.

### J. Posicionamiento avanzado (Fase 9)

Toda esta capa funciona offline (no requiere Qdrant) porque opera sobre destinos ya recuperados.

Recalcular popularidad sobre el corpus actual (idempotente, hay que correrlo cada vez que cambia el corpus):

```bash
python scripts/compute_popularity.py
```

Verificar que la popularidad se persiste correctamente:

```bash
python -c "
import json
rows = [json.loads(l) for l in open('data/processed/destinations.jsonl')]
rows.sort(key=lambda r: -(r.get('popularity') or 0))
for r in rows[:5]:
    print(f\"{r['name']:25s} pop={r['popularity']:.3f}\")
"
```

El re-ranker, MMR y las secciones se prueban via tests unitarios (paso A) o llamando `/search` con un cliente y aplicando las funciones de `src/retrieval/positioning.py` y `src/retrieval/reranker.py`.

### K. UI Streamlit (Fases 3, 7, 8, 9)

Con la API arriba, levanta la UI:

```bash
streamlit run src/ui/app.py
```

Abre `http://localhost:8501`. Flujo de prueba sugerido:

1. **Onboarding (T097)**: la app pide elegir un perfil sintético (radio buttons). Selecciona uno y pulsa Continuar.
2. **Tab Buscar destinos (T043-T047, T103, T104)**:
   - Escribe una query, ajusta `top_k` y `p` en el sidebar.
   - Cambia el modo (Booleano Extendido / Semántico / Híbrido) y observa los rankings distintos.
   - Activa "Agrupar por estrategia de posicionamiento" para ver las cuatro secciones: Más relevantes, Populares, Recientes, Variados por país.
   - Activa "Mostrar mapa interactivo" para ver los destinos geocodificados sobre Folium con popups.
3. **Tab Preguntar (T066, T069)**:
   - Escribe una pregunta en lenguaje natural.
   - La respuesta del LLM aparece en streaming. Las fuentes citadas se listan al final con expanders.
4. **Tab Buscar por imagen (T086)**:
   - Opción "Subir imagen": carga una imagen, devuelve destinos visualmente similares.
   - Opción "Descripción de texto": embebe la query con CLIP y busca en `destinations_image`.
5. **Tab Recomendado para ti (T098)**:
   - Pulsa "Cargar recomendaciones" para llamar `/recommend` con el perfil del onboarding.
   - El header muestra la persona usada como ancla.
   - El sidebar tiene un botón "Cambiar perfil" para reiniciar el onboarding.

---

## Comandos útiles

```bash
# Smoke test rápido del recuperador léxico (sin Qdrant)
python -c "
from src.indexing.inverted_index import InvertedIndex
from src.retrieval.extended_boolean import ExtendedBoolean
idx = InvertedIndex.load('data/processed/index.pkl')
for q in ['madrid', 'beach OR mountain', 'history AND museum']:
    hits = ExtendedBoolean(p=2.0).search(q, idx, top_k=3)
    print(f'{q!r:25s} -> {[h[0] for h in hits]}')
"

# Métricas del corpus
python scripts/stats.py

# Métricas del índice vectorial (requiere Qdrant)
python scripts/index_metrics.py

# Levantar API en producción (sin reload, varios workers)
uvicorn src.api.main:app --workers 2 --host 0.0.0.0 --port 8000
```

---

## Estructura del repositorio

```
smart-tourism-engine/
├── docs/                     # Documentación por capítulo
├── data/
│   ├── raw/                  # JSON crudo de Wikivoyage, imágenes
│   └── processed/            # JSONL normalizado, SQLite, index.pkl
├── scripts/                  # Utilidades: download, init_qdrant, popularity, stats
├── src/
│   ├── api/                  # FastAPI (endpoints, schemas, middleware)
│   ├── ingestion/            # Wikivoyage, OpenTripMap, normalize, store
│   ├── indexing/             # Tokenizer, inverted index, embedder, vector store
│   ├── retrieval/            # Boolean, ExtendedBoolean, hybrid, reranker, MMR, popularity, freshness, positioning
│   ├── rag/                  # LLM client, prompts, pipeline, context builder
│   ├── web_search/           # Tavily, trigger, converter
│   ├── multimodal/           # CLIP embedder, image indexer, fusion
│   ├── recommendation/       # UserProfile, synthetic profiles, content-based, collaborative, hybrid, service
│   ├── ui/                   # Streamlit app
│   ├── cli.py                # Comando typer (build-index, embed, embed-images, ingest)
│   ├── config.py             # Pydantic Settings
│   └── logging_config.py
├── tests/                    # 507 tests pytest
├── pyproject.toml
├── requirements.txt
└── .env.example
```

---

## Limitaciones conocidas

Documentado con honestidad para la defensa:

- El corpus actual es **bi-fuente** (957 destinos: 179 de Wikivoyage en inglés + 778 de Wikidata/Wikipedia en español). La columna `popularity` se aproxima a partir de la longitud de descripción + menciones cruzadas porque ninguna de las dos fuentes expone un `reviews_count`.
- La tabla SQLite `destinations` puede quedar fuera de sincronía con `data/processed/destinations.jsonl` si no se re-ingiere después de regenerar el JSONL. La UI degrada elegantemente (popularidad, país y coordenadas en `null`) en ese caso.
- Las búsquedas semántica, híbrida, multimodal, RAG y recomendación requieren **Qdrant corriendo**; si está caído, los endpoints devuelven 500 en lugar de 503 (mismo patrón en todos esos endpoints).
- La búsqueda multimodal funciona solo cuando hay imágenes descargadas en `data/raw/images/`; el script de descarga de imágenes no se ejecuta por defecto en esta entrega.
- El fallback Tavily requiere `TAVILY_API_KEY`. Sin ella, se omite y el RAG responde solo con el contexto local.
- Las métricas formales del recuperador (Precision@k, Recall@k, F1@k, MAP, MRR, nDCG@k) están implementadas en `src/evaluation/` y se ejecutan con `python -m src.cli evaluate --queries data/eval/queries_v2.json`. El detalle, las definiciones y los números actuales viven en el capítulo 14.

---

## Licencia

MIT. Ver [LICENSE](LICENSE).
