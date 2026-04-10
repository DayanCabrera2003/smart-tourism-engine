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
