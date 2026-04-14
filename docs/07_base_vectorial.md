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

### Tests

[`tests/test_vector_store.py`](../tests/test_vector_store.py) cubre:

- Idempotencia de `create_collection`.
- Recreación destructiva de colección.
- Upsert + búsqueda por similitud coseno.
- Comportamiento ante un upsert vacío.
- Filtrado por `score_threshold`.

Todos corren contra el cliente en memoria, por lo que no requieren un
servicio Qdrant externo en CI.
