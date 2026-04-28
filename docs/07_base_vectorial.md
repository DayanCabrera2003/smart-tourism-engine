# 07. Base Vectorial (Qdrant)

La Fase 4 incorpora una **base de datos vectorial** para soportar búsqueda
semántica sobre las descripciones de los destinos. La elección recae en
[Qdrant](https://qdrant.tech/), desplegado como contenedor Docker dentro del
mismo `docker-compose` del proyecto.

## ¿Por qué Qdrant?

| Criterio | Qdrant | Alternativas |
|----------|--------|--------------|
| Licencia | Apache-2.0 | FAISS (MIT, sólo librería), Milvus (Apache-2.0, pesado), Pinecone (SaaS, propietario) |
| Despliegue | Binario único o Docker; modo embebido `:memory:` para tests | FAISS no expone API HTTP; Milvus requiere etcd + MinIO |
| API | REST + gRPC + cliente Python tipado | Pinecone sólo SaaS; FAISS sólo Python/C++ |
| Filtros + payload | Sí, ricos y combinables con la búsqueda vectorial | FAISS necesita indexación externa para metadata |
| Persistencia | En disco con snapshots | FAISS requiere lógica propia |

Para un proyecto académico que ya corre Docker Compose, Qdrant es el equilibrio
adecuado: **open-source, ligero, persistente y con cliente Python de primera
clase** que también ofrece un modo en memoria ideal para los tests.

## Cliente: `VectorStore`

La clase [`src/indexing/vector_store.py`](../src/indexing/vector_store.py)
encapsula `qdrant-client` y expone tres operaciones mínimas, suficientes para
las tareas T050 – T053 que vendrán a continuación:

```python
from src.indexing.vector_store import VectorStore

store = VectorStore()  # usa settings.QDRANT_URL
store.create_collection("destinations_text", vector_size=384)
store.upsert(
    "destinations_text",
    [("madrid-es", embedding, {"name": "Madrid", "country": "ES"})],
)
hits = store.search("destinations_text", query_vector, top_k=5)
```

### Métodos

- **`create_collection(name, *, vector_size, distance="Cosine", recreate=False)`**
  Crea la colección si no existe. `distance` admite las métricas soportadas por
  Qdrant (`Cosine`, `Dot`, `Euclid`). `recreate=True` la borra y la vuelve a
  crear, útil para scripts de inicialización idempotentes.
- **`upsert(collection, points)`** Inserta o actualiza una colección de tuplas
  `(id, vector, payload)`. Devuelve el número de puntos enviados; tolera
  iteradores vacíos.
- **`search(collection, query_vector, *, top_k=10, score_threshold=None)`**
  Devuelve `[(id, score, payload), …]` ordenados por score descendente. Usa
  `query_points`, la API recomendada del cliente moderno.

### Configuración

La URL del servidor se toma de `settings.QDRANT_URL`
(por defecto `http://localhost:6333`, sobreescrita a `http://qdrant:6333`
dentro de Docker Compose). En tests se inyecta `url=":memory:"`, lo que
arranca un Qdrant embebido sin red.

## Modelo de embeddings: `TextEmbedder`

La clase [`src/indexing/embedder.py`](../src/indexing/embedder.py) envuelve
`sentence-transformers` y expone un único método `embed(text) -> list[float]`
que produce el vector denso usado como entrada a Qdrant:

```python
from src.indexing.embedder import TextEmbedder

embedder = TextEmbedder()
vector = embedder.embed("Playas del Caribe colombiano")
assert len(vector) == TextEmbedder.DIMENSION  # 384
```

### ¿Por qué `all-MiniLM-L6-v2`?

| Criterio | `all-MiniLM-L6-v2` | Alternativas |
|----------|--------------------|--------------|
| Tamaño | ~90 MB, 22 M parámetros | `mpnet-base-v2` ~420 MB; modelos LLM > 1 GB |
| Dimensión | 384 | `mpnet-base-v2` 768 (mayor coste en Qdrant) |
| Velocidad CPU | ~14 k oraciones/s en un i7 moderno | `mpnet` ~2.8 k/s |
| Multilingüe | Rinde razonablemente en ES/EN tras fine-tuning de STS | Modelos monolingües pierden en EN+ES mixto |
| Licencia | Apache-2.0 | Varias |

Para un catálogo de destinos con descripciones cortas (pocos párrafos) y una
máquina de desarrollo sin GPU, MiniLM ofrece el mejor equilibrio
**calidad/velocidad/tamaño** y encaja con la dimensión 384 que usará la
colección `destinations_text`. Los vectores se generan **normalizados L2**
(`normalize_embeddings=True`) para que la métrica `Cosine` en Qdrant sea
numéricamente equivalente al producto punto.

### Tests

[`tests/test_vector_store.py`](../tests/test_vector_store.py) cubre:

- Idempotencia de `create_collection`.
- Recreación destructiva de colección.
- Upsert + búsqueda por similitud coseno.
- Comportamiento ante un upsert vacío.
- Filtrado por `score_threshold`.

Todos corren contra el cliente en memoria, por lo que no requieren un
servicio Qdrant externo en CI.

[`tests/test_embedder.py`](../tests/test_embedder.py) inyecta un modelo
falso con la misma API de `SentenceTransformer.encode`, por lo que no se
descargan pesos del Hub durante las pruebas.

## Esquema de la colección `destinations_text`

La colección que aloja los embeddings de los destinos se llama
`destinations_text`. Sus parámetros son:

| Aspecto | Valor | Justificación |
|---------|-------|---------------|
| Nombre | `destinations_text` | Separa vectores textuales de futuras colecciones (p. ej. imágenes). |
| Dimensión | `384` | Coincide con la salida de `all-MiniLM-L6-v2` (`TextEmbedder.DIMENSION`). |
| Distancia | `Cosine` | Los vectores se entregan normalizados L2, por lo que coseno ≡ producto punto. |
| ID del punto | entero o UUID | Qdrant exige uno de estos dos tipos; usaremos el id interno del destino. |
| Payload típico | `{ "name": str, "country": str, "slug": str, ... }` | Campos que el recuperador expondrá al UI tras un hit. |

### Script `scripts/init_qdrant.py` (T051)

El script crea la colección de forma idempotente contra la URL definida en
`settings.QDRANT_URL`:

```bash
# Crea la colección si no existe
python scripts/init_qdrant.py

# Fuerza recreación destructiva (útil tras cambios de esquema)
python scripts/init_qdrant.py --recreate

# Override explícito de URL (p. ej. apuntando al contenedor local)
python scripts/init_qdrant.py --url http://localhost:6333
```

Expone una función `init(store, *, recreate=False)` para invocarla desde
tests con un `VectorStore` en memoria, de modo que
[`tests/test_init_qdrant.py`](../tests/test_init_qdrant.py) verifica la
creación, la idempotencia y el borrado con `--recreate` sin depender de un
servicio Qdrant externo.

## Caché de embeddings en disco (T056)

El módulo [`src/indexing/embedding_cache.py`](../src/indexing/embedding_cache.py)
implementa la clase `EmbeddingCache`, que actúa como decorador transparente
sobre cualquier embedder:

```python
from src.indexing.embedding_cache import EmbeddingCache
from src.indexing.embedder import TextEmbedder

cache_path = "data/processed/embeddings_cache.pkl"
cached_embedder = EmbeddingCache.load(TextEmbedder(), cache_path)

vector = cached_embedder.embed("Playas del Caribe")   # genera y guarda
vector = cached_embedder.embed("Playas del Caribe")   # hit — no llama al modelo
cached_embedder.save()                                # persiste en disco
```

### Estrategia de caché

La caché es un `dict[str, list[float]]` persistido con `pickle`. La clave
es el **texto exacto** usado para generar el embedding. La decisión de usar
pickle (en lugar de LMDB o SQLite) favorece la simplicidad: el corpus de
destinos cabe completamente en RAM (~200 vectores × 384 floats × 4 bytes ≈
300 KB), por lo que cargar el pickle completo al arranque es instantáneo.

| Aspecto | Decisión |
|---------|----------|
| Formato | Pickle binario (`dict[str, list[float]]`) |
| Clave | Texto completo (sensible a cambios menores) |
| Persistencia | Explícita: llamar `save()` cuando corresponda |
| Ubicación por defecto | `data/processed/embeddings_cache.pkl` |
| Tolerancia a corrupción | Si el pickle no es un `dict`, la caché inicia vacía |

La persistencia es **explícita** para que el llamador controle cuándo se
escribe a disco. Esto evita I/O por cada petición en un servidor web y
permite decidir, por ejemplo, persistir solo al terminar un lote de embeddings
(como en el comando `embed`).

## Pipeline de embedding (T052)

El módulo [`src/indexing/embed_destinations.py`](../src/indexing/embed_destinations.py)
recorre el JSONL de destinos procesados
(`data/processed/destinations.jsonl`), genera un embedding por destino con
`TextEmbedder` y los sube a la colección `destinations_text` en batches.

El comando CLI `python -m src.cli embed` envuelve el pipeline:

```bash
# Embeber todo el corpus en Qdrant (requiere colección ya creada por T051)
python -m src.cli embed

# Override de fuente y tamaño de batch
python -m src.cli embed --source data/processed/destinations.jsonl --batch-size 128
```

### Texto a embeber

Para cada destino se construye la cadena `f"{name}. {description}"` con
acentos y puntuación — el modelo multilingüe `all-MiniLM-L6-v2` aprovecha
los diacríticos, a diferencia del índice Booleano Extendido que consume
`description_normalized`.

### ID del punto

Qdrant exige que los IDs sean enteros o UUIDs. Como el `id` de un destino
es un slug textual (p. ej. `madrid-es`), lo convertimos a UUID5 determinista
con un namespace fijo (`slug_to_uuid`). El slug original se preserva en el
payload bajo la clave `slug` para que el recuperador pueda devolverlo a la
UI tras un hit. La función es determinista, por lo que re-ejecutar el
comando `embed` actualiza puntos existentes en lugar de duplicarlos
(idempotencia sobre el mismo corpus).

### Payload

Se copian del destino los campos `name`, `country`, `region`, `tags`,
`image_urls`, `source`, más el `slug`. Son los mismos que la UI necesita
para renderizar una *card* sin consultar otra base de datos.

### Tests

[`tests/test_embed_destinations.py`](../tests/test_embed_destinations.py)
cubre el conteo de puntos, la forma del payload, la división en batches
de tamaño configurable, el archivo vacío, la idempotencia y el error
cuando falta el JSONL de origen. Todos corren contra `VectorStore(url=":memory:")`
con un embedder de 8 dimensiones, sin red ni descargas de modelos.
