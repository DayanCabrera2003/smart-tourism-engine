# Posicionamiento Avanzado

El módulo de posicionamiento toma el ranking del recuperador (Booleano Extendido, semántico o híbrido) y lo combina con señales adicionales para producir el orden final mostrado al usuario. La idea es separar **relevancia** (¿qué tan bien encaja con la query?) de **conveniencia** (¿es un destino popular?, ¿es información fresca?, ¿le importa al usuario?).

---

## T099 — Score de popularidad

`src/retrieval/popularity.py` calcula un score `[0, 1]` por destino que se persiste en `Destination.popularity` y en la columna `popularity` de la tabla SQLite `destinations`.

### Decisión sobre la señal

El plan original sugiere "número de fuentes que mencionan el destino o reviews count". Nuestro corpus es **mono-fuente** (Wikivoyage) y no incluye ratings, así que el campo `source` no aporta variabilidad. Aproximamos popularidad con dos señales intrínsecas al corpus:

| Señal | Peso por defecto | Justificación |
|---|---|---|
| **Longitud de la descripción** | 0.7 | Wikivoyage invierte más prosa en destinos más visitados y debatidos. Es la señal más densa y barata. |
| **Menciones cruzadas** | 0.3 | Cuántas otras entradas del corpus mencionan el destino por nombre. Una ciudad que aparece en muchas otras páginas del mismo corpus es notable en el discurso turístico regional. |

Las dos señales se normalizan min-max por separado y se combinan linealmente con los pesos. Los pesos se renormalizan internamente para que siempre sumen 1.0.

### Implementación

```python
from src.retrieval.popularity import compute_popularity_scores

scores = compute_popularity_scores(destinations)  # dict[id, float]
```

El script `scripts/compute_popularity.py` recalcula popularity para todo el corpus, escribe el JSONL en sitio y hace `UPDATE` sobre las filas correspondientes de SQLite. Es idempotente: ejecutarlo dos veces da el mismo resultado. Hay que volver a correrlo cada vez que se añadan o eliminen destinos del corpus para mantener la normalización comparable.

### Migración SQLite

La columna `popularity` se añade automáticamente vía `_ensure_popularity_column` en `src/ingestion/store.py`. Esa función inspecciona el esquema vivo y emite `ALTER TABLE destinations ADD COLUMN popularity FLOAT` solo cuando la columna no existe. Bases de datos creadas antes de T099 se migran al primer import sin intervención manual.

### Verificación contra el corpus real

Con los 206 destinos de Wikivoyage, la distribución resultante encaja con la intuición turística:

- **Top**: Ho Chi Minh City, Turín, Madrid, París, Barcelona (descripciones largas y muy citadas por otras entradas).
- **Bottom**: Bogotá, Cádiz, Gijón, Mérida, Cancún (descripciones de una sola línea sin menciones cruzadas).

### Decisiones de diseño

- **Persistir, no recalcular**: el score se calcula una vez y se guarda. Calcular menciones cruzadas requiere O(n²) escaneos del corpus, demasiado caro para hacer por consulta.
- **Nombres < 3 caracteres se ignoran**: regexes de palabras cortas matchean falsamente (p. ej. "Vi" matchearía "via", "Vienna"). Filtrarlos evita inflación artificial.
- **Sin auto-menciones**: un destino no cuenta sus propias menciones; eso premiaría la verbosidad y no la popularidad real.
- **Min-max independiente**: normalizar cada señal por separado antes de combinar evita que un destino con descripción muy larga ahogue la señal de menciones.
