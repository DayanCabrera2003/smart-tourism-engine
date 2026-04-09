# 05 - Indexación y Preprocesamiento

Este documento describe el pipeline de procesamiento de texto utilizado para transformar el contenido crudo en un formato adecuado para la indexación y recuperación.

## Preprocesamiento

Antes de la tokenización, el texto de los destinos turísticos se somete a un proceso de normalización para reducir el ruido y asegurar que términos equivalentes se representen de la misma forma.

### Pipeline de Normalización

La normalización se implementa en `src/ingestion/normalize.py` y consta de los siguientes pasos:

1.  **Limpieza de HTML**: Eliminación de etiquetas residuales que puedan haber quedado tras el parseado inicial de fuentes web o dumps.
2.  **Conversión a Minúsculas**: Estandarización de todo el texto a minúsculas para evitar duplicidad de términos por capitalización.
3.  **Eliminación de Acentos (Stripping)**: Los caracteres con diacríticos se transforman a su versión base (ej. `á` -> `a`, `ñ` -> `n`). Esto facilita la recuperación independientemente de cómo el usuario introduzca la consulta.
4.  **Normalización de Espacios**: Eliminación de espacios en blanco adicionales, saltos de línea y tabulaciones, dejando un único espacio entre palabras.

### Ejemplo de Transformación

| Entrada | Salida |
|---------|--------|
| `  <p>¡Hola <b>España</b>!  </p> \n ¿Cómo está todo?  ` | `¡hola espana! ¿como esta todo?` |

Las pruebas unitarias asociadas se encuentran en `tests/test_normalize.py`.

## Tokenización

La tokenización es el proceso de dividir el texto normalizado en unidades mínimas de significado (tokens), que serán las entradas del índice invertido.

### Implementación

El tokenizador se encuentra en `src/indexing/tokenizer.py` y expone una única función pública:

```python
def tokenize(text: str) -> list[str]
```

### Pipeline interno

1. **Minúsculas**: convierte todo el texto a minúsculas.
2. **Eliminación de acentos**: transforma caracteres con diacríticos a su forma base (ej. `á` → `a`, `ñ` → `n`) mediante descomposición Unicode NFD.
3. **Split por no-alfanuméricos**: divide el texto usando la expresión `[^a-z0-9]+` como separador, lo que elimina puntuación, signos de interrogación/exclamación y espacios en un solo paso.
4. **Filtrado de tokens vacíos**: descarta los tokens resultantes que sean cadenas vacías.

### Ejemplos

| Entrada | Tokens |
|---------|--------|
| `"¡España es bonita!"` | `["espana", "es", "bonita"]` |
| `"¿Cómo está todo?"` | `["como", "esta", "todo"]` |
| `"hotel 5 estrellas"` | `["hotel", "5", "estrellas"]` |
| `"Café, té y más..."` | `["cafe", "te", "y", "mas"]` |
| `"!!! ???"` | `[]` |

### Casos límite cubiertos

- **Puntuación múltiple**: `"un-guión y punto.final"` → `["un", "guion", "y", "punto", "final"]`
- **Solo puntuación**: devuelve lista vacía.
- **Texto vacío o solo espacios**: devuelve lista vacía.
- **Números**: se conservan como tokens (ej. `"2024"`, `"5"`).
- **Mayúsculas y acentos combinados**: `"ÁRBOL"` → `["arbol"]`.

Las pruebas unitarias asociadas se encuentran en `tests/test_tokenizer.py`.

## Stopwords

Las stopwords son palabras funcionales de alta frecuencia (artículos, preposiciones, conjunciones) que no aportan valor discriminativo al índice. Eliminarlas reduce el tamaño del índice y mejora la precisión de la recuperación.

### Justificación bilingüe

El sistema indexa contenido tanto en **español** (fuente principal: Wikivoyage en español, OpenTripMap) como en **inglés** (descripciones de POIs en inglés de OpenTripMap). Usar una lista combinada evita que palabras funcionales de un idioma queden en el índice por no estar en la lista del otro.

### Implementación

La lógica se encuentra en `src/indexing/stopwords.py` y expone:

- `STOPWORDS` — `frozenset[str]` con las palabras a eliminar, cargado al importar el módulo.
- `remove_stopwords(tokens: list[str]) -> list[str]` — filtra la lista de tokens devolviendo solo los que no sean stopwords.

La lista se carga desde **NLTK** (`nltk.corpus.stopwords`) combinando los idiomas `"spanish"` (313 palabras) e `"english"` (198 palabras). Si el corpus no está descargado, se descarga automáticamente en el primer uso.

### Ejemplo

```python
tokens = ["el", "turismo", "en", "espana", "es", "bonito"]
remove_stopwords(tokens)
# → ["turismo", "espana", "bonito"]
```

Las pruebas unitarias asociadas se encuentran en `tests/test_stopwords.py`.

## Stemming

El stemming reduce cada token a su raíz morfológica (*stem*), agrupando variantes de una misma palabra bajo una representación común. Esto mejora el recall al unificar formas como "turismo", "turista" y "turístico" bajo el stem "turism".

### Stemmer vs. Lemmatizer

Se eligió **stemming** (en lugar de lemmatización) por las siguientes razones:

| Criterio | Stemmer (Snowball) | Lemmatizer (spaCy/NLTK) |
|----------|--------------------|-------------------------|
| Velocidad | Muy rápido (reglas) | Lento (modelo neuronal) |
| Dependencias | Solo NLTK | Modelos de idioma pesados |
| Precisión lingüística | Menor (raíces heurísticas) | Mayor (formas canónicas) |
| Adecuación para IR | Suficiente para recuperación por palabras clave | Overkill para este caso |

Para un sistema de recuperación de información basado en índice invertido, la precisión lingüística exacta del lemmatizer no justifica el coste en velocidad y dependencias. El stemmer de Snowball es el estándar de facto en IR para español e inglés.

### Implementación

La lógica se encuentra en `src/indexing/stemmer.py` y expone:

- `stem_token(token, language="spanish") -> str` — aplica stemming a un único token.
- `stem(tokens, language="spanish") -> list[str]` — aplica stemming a una lista de tokens.

El parámetro `language` es configurable: acepta `"spanish"` (por defecto) o `"english"`. Los stemmers se instancian una sola vez y se reutilizan mediante caché interna.

### Ejemplos

| Token | Stem (ES) | Stem (EN) |
|-------|-----------|-----------|
| `turismo` | `turism` | — |
| `playas` | `play` | — |
| `beaches` | — | `beach` |
| `running` | — | `run` |
| `restaurantes` | `restaur` | — |

Las pruebas unitarias asociadas se encuentran en `tests/test_stemmer.py`.

## Pipeline de preprocesamiento completo

El módulo `src/indexing/preprocess.py` encadena los tres pasos anteriores en una única función pública:

```python
def preprocess(text: str, language: str = "spanish") -> list[str]
```

### Diagrama del pipeline

```
Texto de entrada
      │
      ▼
┌─────────────┐
│  tokenize() │  minúsculas + strip acentos + split [^a-z0-9]+
└─────────────┘
      │  list[str]
      ▼
┌──────────────────────┐
│  remove_stopwords()  │  filtra palabras funcionales ES + EN
└──────────────────────┘
      │  list[str]
      ▼
┌────────────┐
│   stem()   │  SnowballStemmer (configurable: "spanish" | "english")
└────────────┘
      │
      ▼
list[str]  ← stems listos para indexar
```

### Ejemplo

```python
preprocess("¡Playas hermosas de España!")
# tokenize  → ["playas", "hermosas", "de", "espana"]
# stopwords → ["playas", "hermosas", "espana"]  ("de" eliminado)
# stem      → ["play", "herm", "espan"]
```

```python
preprocess("The tourism in Spain is beautiful", language="english")
# tokenize  → ["the", "tourism", "in", "spain", "is", "beautiful"]
# stopwords → ["tourism", "spain", "beautiful"]
# stem      → ["tourism", "spain", "beauti"]
```

Las pruebas unitarias asociadas se encuentran en `tests/test_preprocess.py`.

## Índice invertido

El índice invertido es la estructura central del sistema de recuperación. Mapea cada término del vocabulario a la lista de documentos que lo contienen (*postings list*), junto con la frecuencia de aparición (TF crudo).

### Estructura de datos

```
_index: dict[term, list[(doc_id, freq)]]

Ejemplo:
{
  "turism": [("dest_001", 3), ("dest_042", 1)],
  "play":   [("dest_001", 2), ("dest_007", 5)],
  "herm":   [("dest_007", 1)],
}
```

### Implementación

La clase `InvertedIndex` en `src/indexing/inverted_index.py` expone:

| Método / Propiedad | Descripción |
|--------------------|-------------|
| `add_document(doc_id, tokens)` | Indexa un documento con sus tokens preprocesados; acumula frecuencias (TF crudo). |
| `get_postings(term) -> list[(doc_id, freq)]` | Devuelve los postings con TF crudo, ordenados por `doc_id`. |
| `compute_tf_idf()` | Calcula pesos TF-IDF y normas L2 para todos los documentos. |
| `get_tfidf_postings(term) -> list[(doc_id, weight)]` | Devuelve los postings con peso TF-IDF. Requiere `compute_tf_idf()`. |
| `get_norm(doc_id) -> float` | Devuelve la norma L2 del documento para similitud coseno. |
| `vocabulary` | Conjunto de términos en el índice. |
| `doc_count` | Número de documentos indexados. |
| `len(index)` | Tamaño del vocabulario. |
| `term in index` | Comprueba si un término está indexado. |

### Ejemplo de uso

```python
from src.indexing.inverted_index import InvertedIndex
from src.indexing.preprocess import preprocess

index = InvertedIndex()
index.add_document("dest_001", preprocess("Playas hermosas en Mallorca"))
index.add_document("dest_002", preprocess("Turismo de playa en Ibiza"))

index.get_postings("play")
# → [("dest_001", 1), ("dest_002", 1)]

index.get_postings("turism")
# → [("dest_002", 1)]
```

Las pruebas unitarias asociadas se encuentran en `tests/test_inverted_index.py`.

## TF-IDF

El peso TF-IDF mide la importancia de un término en un documento relativa al resto de la colección. Términos frecuentes en un documento pero raros en la colección reciben mayor peso.

### Fórmulas

**TF normalizado** (evita sesgo por longitud del documento):

$$TF(t, d) = \frac{freq(t, d)}{\max_{t' \in d} freq(t', d)}$$

**IDF suavizado** (evita división por cero y penaliza menos los términos universales):

$$IDF(t) = \log\!\left(\frac{N}{df(t)}\right) + 1$$

**Peso TF-IDF:**

$$w(t, d) = TF(t, d) \times IDF(t)$$

**Norma L2** (necesaria para similitud coseno en recuperación futura):

$$\|d\| = \sqrt{\sum_{t \in d} w(t, d)^2}$$

Donde:
- $freq(t, d)$: número de veces que aparece el término $t$ en el documento $d$.
- $N$: número total de documentos en la colección.
- $df(t)$: número de documentos que contienen el término $t$.

### Flujo de uso

```python
index = InvertedIndex()
for doc_id, tokens in corpus:
    index.add_document(doc_id, tokens)

index.compute_tf_idf()   # calcular pesos y normas

index.get_tfidf_postings("play")
# → [("dest_001", 0.693), ("dest_002", 0.347)]

index.get_norm("dest_001")
# → 1.234
```

Las pruebas unitarias asociadas se encuentran en `tests/test_tfidf.py`.
