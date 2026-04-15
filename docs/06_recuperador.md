# 06 - Recuperador

Este documento describe los modelos de recuperación implementados en `src/retrieval/`.

---

## Baseline Booleano

El modelo Booleano clásico es el punto de partida del sistema de recuperación. Recupera los documentos que satisfacen exactamente una expresión lógica formada por operadores AND, OR y NOT sobre los términos de la consulta.

### Implementación

El módulo `src/retrieval/boolean.py` expone una única función pública:

```python
def boolean_query(query: str, index: InvertedIndex) -> list[str]
```

**Parámetros:**

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `query` | `str` | Consulta en lenguaje natural con operadores AND/OR/NOT en mayúsculas. |
| `index` | `InvertedIndex` | Índice invertido ya construido (ver T027–T029). |

**Retorna:** Lista de `doc_id` ordenada alfabéticamente. Lista vacía si no hay coincidencias.

### Sintaxis de consultas

Los operadores deben escribirse en **mayúsculas** para distinguirlos de términos de búsqueda:

| Consulta | Semántica | Ejemplo |
|----------|-----------|---------|
| `term` | Documentos que contienen el término | `"beach"` |
| `t1 AND t2` | Intersección | `"beach AND tourism"` |
| `t1 OR t2` | Unión | `"beach OR mountain"` |
| `NOT term` | Complemento (todos los docs salvo los que contienen el término) | `"NOT tourism"` |
| `t1 AND NOT t2` | Diferencia | `"tourism AND NOT beach"` |
| `t1 AND t2 AND t3` | Intersección múltiple | `"beach AND mountain AND hiking"` |

### Pipeline de preprocesamiento de la consulta

Los términos de la consulta pasan por el mismo pipeline que los documentos indexados:

```
query term → tokenize → remove_stopwords → stem (English Snowball)
```

Esto garantiza que "beaches" y "beach" resuelvan al mismo posting list.

### Evaluación interna

La expresión se evalúa en dos pasadas con precedencia **NOT > AND > OR**:

1. **División OR**: la consulta se parte en cláusulas separadas por `OR`.
2. **Evaluación AND**: cada cláusula se procesa izquierda a derecha, aplicando intersecciones (`AND`) y diferencias (`AND NOT`).
3. **Unión**: los resultados de todas las cláusulas OR se combinan con unión de conjuntos.

### Ejemplo de uso

```python
from src.indexing.inverted_index import InvertedIndex
from src.retrieval.boolean import boolean_query

# Cargar índice desde disco
idx = InvertedIndex.load("data/processed/index.pkl")

# Consulta simple
boolean_query("beach", idx)
# → ["dest-001", "dest-007", ...]

# Consulta compuesta
boolean_query("tourism AND NOT beach", idx)
# → ["dest-002", "dest-005", ...]
```

### Limitaciones del modelo Booleano clásico

| Limitación | Descripción |
|------------|-------------|
| Sin ranking | Todos los documentos recuperados son equivalentes; no se ordenan por relevancia. |
| Semántica rígida | Un documento que contiene 9 de 10 términos AND es descartado igual que uno con 0. |
| Sin pesos | No considera la frecuencia de los términos ni su importancia en la colección. |

Estas limitaciones motivan el uso del **Modelo Booleano Extendido (p-norm)** como modelo principal del sistema (ver `docs/03_modelo_ri.md`).

Las pruebas unitarias asociadas se encuentran en `tests/test_boolean.py`.

---

## Parser de Queries p-norm (T035)

El módulo `src/retrieval/query_parser.py` convierte una consulta textual a un **árbol AST** que el evaluador p-norm (T036) recorre aplicando las fórmulas AND/OR extendidas.

### Gramática

```
expr      → and_expr (OR and_expr)*
and_expr  → TERM (AND TERM)*
TERM      → cualquier token que no sea AND / OR
```

**Precedencia:** AND se evalúa antes que OR (igual que en álgebra booleana estándar).  
**Preprocesamiento:** los términos pasan por el mismo pipeline que los documentos indexados (tokenize → stopwords → stem), garantizando coherencia con el índice.

### Nodos del AST

| Clase | Descripción | Atributos |
|-------|-------------|-----------|
| `TermNode` | Hoja: término ya preprocesado | `term: str` |
| `AndNode` | Nodo AND p-norm | `children: list[Node]` |
| `OrNode` | Nodo OR p-norm | `children: list[Node]` |

### API pública

```python
from src.retrieval.query_parser import parse_query

node = parse_query("playa AND tranquilo OR montaña")
# → OrNode(children=[AndNode(children=[TermNode("playa"), TermNode("tranquilo")]),
#                    TermNode("montaña")])
```

Lanza `ValueError` si la consulta está vacía o no contiene términos válidos tras el preprocesamiento.

### Ejemplos de árboles generados

| Consulta | AST |
|----------|-----|
| `"beach"` | `TermNode("beach")` |
| `"beach AND tourism"` | `AndNode([TermNode("beach"), TermNode("tourism")])` |
| `"beach OR mountain"` | `OrNode([TermNode("beach"), TermNode("mountain")])` |
| `"playa AND tranquilo OR montaña"` | `OrNode([AndNode([TermNode("playa"), TermNode("tranquilo")]), TermNode("montaña")])` |

Las pruebas unitarias asociadas se encuentran en `tests/test_query_parser.py`.

---

## Evaluador recursivo del AST (T036)

`ExtendedBoolean.evaluate(ast, doc_weights)` recorre el árbol producido por `parse_query` y combina los pesos TF-IDF del documento usando las fórmulas p-norm.

### Pseudocódigo

```
función evaluate(nodo, doc_weights):
    si nodo es TermNode:
        devolver doc_weights.get(nodo.term, 0.0)

    si nodo es AndNode:
        pesos ← [evaluate(hijo, doc_weights) para hijo en nodo.children]
        devolver and_norm(pesos)        # 1 − (Σ(1−wᵢ)ᵖ / n)^(1/p)

    si nodo es OrNode:
        pesos ← [evaluate(hijo, doc_weights) para hijo en nodo.children]
        devolver or_norm(pesos)         # (Σ wᵢᵖ / n)^(1/p)
```

### Ejemplo completo

Consulta: `"playa AND tranquilo OR montaña"`, $p = 2$.

AST generado por el parser:
```
OrNode
├── AndNode
│   ├── TermNode("playa")
│   └── TermNode("tranquil")   ← stem de "tranquilo"
└── TermNode("montaña")
```

Pesos del documento `dest-042`:

| Término | Peso TF-IDF |
|---------|-------------|
| `playa` | 0.6 |
| `tranquil` | 0.8 |
| `montaña` | 0.5 |

Evaluación paso a paso:

1. `and_norm([0.6, 0.8])` = $1 - \sqrt{(0.4^2 + 0.2^2)/2} \approx 0.684$
2. `or_norm([0.684, 0.5])` = $\sqrt{(0.684^2 + 0.5^2)/2} \approx 0.597$

El documento `dest-042` obtiene una similitud de **0.597**.

### API

```python
from src.retrieval.extended_boolean import ExtendedBoolean
from src.retrieval.query_parser import parse_query

eb = ExtendedBoolean(p=2.0)
ast = parse_query("playa AND tranquilo OR montaña")
score = eb.evaluate(ast, {"playa": 0.6, "tranquil": 0.8, "montaña": 0.5})
# → 0.597
```

Las pruebas unitarias asociadas se encuentran en `tests/test_extended_boolean.py`.

---

## Búsqueda end-to-end (T037)

`ExtendedBoolean.search(query, index, top_k)` orquesta el pipeline completo desde la consulta en texto hasta la lista de resultados ordenados.

### Diagrama de flujo

```
query (str)
    │
    ▼
parse_query(query)
    │  AST
    ▼
_leaf_terms(AST)  →  [t₁, t₂, ..., tₙ]
    │
    ▼  para cada término tᵢ
index.get_tfidf_postings(tᵢ)
    │  {doc_id → tfidf_weight}
    ▼
normalizar: w_norm = tfidf / index.get_norm(doc_id)
    │  doc_weights[doc_id] = {term → w_norm ∈ [0,1]}
    ▼
evaluate(AST, doc_weights)  →  score ∈ [0,1]   (por cada doc candidato)
    │
    ▼
heapq.nlargest(top_k, scores)
    │
    ▼
list[tuple[doc_id, score]]   ordenada por score desc
```

**Nota:** sólo se evalúan los documentos que aparecen en al menos un posting de los términos de la consulta — los documentos sin ningún término obtienen score implícito de 0 y no se incluyen en el resultado.

### API

```python
from src.indexing.inverted_index import InvertedIndex
from src.retrieval.extended_boolean import ExtendedBoolean

# Cargar índice desde disco
idx = InvertedIndex.load("data/processed/index.pkl")

eb = ExtendedBoolean(p=2.0)
results = eb.search("playa AND tranquilo OR montaña", idx, top_k=10)
# → [("dest-042", 0.597), ("dest-017", 0.541), ...]
```

Las pruebas unitarias asociadas se encuentran en `tests/test_extended_boolean.py`.

---

## Tests de integración (T038)

`tests/test_retrieval.py` verifica el pipeline completo sobre el índice real (`data/processed/index.pkl`, 206 documentos Wikivoyage).

### Queries verificadas

| Query | Destino esperado en top-5 | Justificación |
|-------|--------------------------|---------------|
| `"beach"` | `wikivoyage-varadero` (top-1) | Varadero es el destino de playa con mayor densidad del término |
| `"tokyo"` | `wikivoyage-tokyo` (score > 0.5) | Coincidencia directa de nombre propio |
| `"temple AND japan"` | `wikivoyage-kyoto` | Capital cultural de Japón; alta densidad de templos |
| `"beach OR mountain"` | `wikivoyage-varadero` | Mayor peso de "beach" en la colección |
| `"museum AND art"` | `wikivoyage-munich` | Alta concentración de museos de arte en Munich |

### Cómo ejecutar los tests

```bash
# Solo tests de integración del recuperador
pytest tests/test_retrieval.py -v

# Suite completa
pytest -v

# Si el índice no existe, los tests se saltan automáticamente
# → SKIPPED  Índice no encontrado en data/processed/index.pkl
```

Para regenerar el índice:

```bash
python -m src.cli build-index data/raw/destinations.jsonl --output data/processed/index.pkl
```

---

## Búsqueda semántica simple (T053)

`POST /search/semantic` complementa al recuperador léxico: en vez de evaluar
operadores AND/OR sobre el índice invertido, embebe la consulta con
`TextEmbedder` (`all-MiniLM-L6-v2`, 384 d, normalizado L2) y la lanza contra
la colección `destinations_text` de Qdrant para devolver los `top_k` vecinos
más cercanos por similitud coseno.

### API

```http
POST /search/semantic
Content-Type: application/json

{
  "query": "playas tranquilas del Caribe",
  "top_k": 5
}
```

La respuesta reutiliza el mismo `SearchResponse` que `/search`: cada
`DestinationResult` viene con `id` (slug del destino), `score` ∈ [0, 1]
(coseno), y los campos `name`, `country`, `image_urls` tomados del payload
de Qdrant. La `description` se enriquece desde `destinations.db` cuando está
disponible.

### Pipeline

```
query (str)
    │
    ▼
TextEmbedder.embed(query)        # vector ∈ ℝ³⁸⁴, ‖v‖₂ = 1
    │
    ▼
VectorStore.search(
    "destinations_text",
    query_vector,
    top_k=K,
)                                 # cosine similarity en Qdrant
    │
    ▼
[(uuid, score, payload), …]
    │  payload["slug"] → enriquecimiento opcional con destinations.db
    ▼
[DestinationResult, …]            # ordenados por score desc
```

### Booleano Extendido (`/search`) vs semántico (`/search/semantic`)

| Aspecto | `/search` (Booleano Extendido p-norm) | `/search/semantic` (Qdrant + MiniLM) |
|---------|---------------------------------------|--------------------------------------|
| Representación de la query | AST de operadores AND/OR sobre tokens | Vector denso `ℝ³⁸⁴` normalizado |
| Representación del documento | Postings TF-IDF normalizados por término | Embedding del texto `"{name}. {description}"` |
| Score | Norma-p combinando pesos por término ∈ [0, 1] | Similitud coseno ∈ [-1, 1] (clamped a [0, 1]) |
| Coincidencia léxica exacta | Sí (vía stemming Snowball) | Sólo si el modelo aprendió la asociación |
| Sinónimos / paráfrasis | No (`"playa"` y `"costa"` son términos distintos) | Sí (vectores cercanos en el espacio latente) |
| Multilingüe | Sólo si el corpus comparte el idioma del query | Sí, MiniLM mantiene proximidad ES↔EN para conceptos comunes |
| Operadores explícitos | AND/OR/NOT con precedencia | Ninguno; la intención se infiere del embedding |
| Coste por consulta | O(\|términos\| · \|postings\|) en RAM | 1 forward del modelo (~ms en CPU) + ANN en Qdrant |
| Dependencias en runtime | Pickle del índice invertido | Modelo `sentence-transformers` + servicio Qdrant |
| Falla suave | Devuelve top-k aunque sólo un término aparezca | Siempre devuelve `top_k` (incluso si la similitud es baja) |
| Idoneidad | Consultas con vocabulario controlado o booleanas | Lenguaje natural, sinónimos, descripciones libres |

**Cuándo elegir cada uno.** El Booleano Extendido brilla cuando el usuario
sabe los términos exactos (`"museum AND art"`) y quiere control booleano
fino; falla en consultas conversacionales (`"un pueblo costero relajado"`)
porque cada palabra cuenta como literal. El semántico hace lo opuesto:
absorbe paráfrasis y cambios de idioma sin esfuerzo, pero pierde precisión
cuando la query es esencialmente una expresión booleana o cuando el corpus
es pequeño y el modelo no logra distinguir matices. Esta complementariedad
motiva el recuperador híbrido de **T054**, que combina ambos rankings.

### Tests

[`tests/test_api_search_semantic.py`](../tests/test_api_search_semantic.py)
inyecta un `VectorStore(url=":memory:")` sembrado con tres puntos y un
embedder determinista (vectores canónicos de dimensión 4) para verificar:
top-1 correcto, respeto a `top_k`, orden por score, propagación del payload,
enriquecimiento opcional con `destinations.db`, validación del body
(`query` requerida, `top_k` ∈ [1, 100]). Ningún test depende de Qdrant ni
descarga pesos del Hub.
