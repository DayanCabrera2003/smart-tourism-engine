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

---

## T100 — Score de frescura

`src/retrieval/freshness.py` calcula la frescura de un destino a partir de `fetched_at` con decay exponencial.

### Fórmula

$$
\mathrm{freshness}(t) = 2^{-\frac{\mathrm{age\_dias}(t)}{\mathrm{half\_life}}}
$$

donde `age_dias = max(0, (now - fetched_at) / 86400)` y `half_life = 180 días` por defecto. El comportamiento de la curva:

| Edad | Score |
|---|---|
| Recién ingresado | 1.00 |
| 90 días | ≈ 0.71 |
| 180 días (1 half-life) | 0.50 |
| 360 días (2 half-lives) | 0.25 |
| 720 días | ≈ 0.06 |

### Por qué decay exponencial

- **Suave y monótono**: pequeñas diferencias de edad producen pequeños cambios de score; no hay saltos discretos que el usuario perciba como arbitrarios.
- **Sin recorte abrupto**: un destino de hace 200 días no se descarta, solo pierde peso frente a uno de hace 30. Eso preserva cobertura del catálogo sin disfrazar contenido viejo de fresco.
- **Half-life como hiperparámetro**: ajustable según la cadencia real de revisión humana del corpus. 180 días refleja una revisión cuatrimestral típica de contenido turístico.

### Decisiones de diseño

- **No persistir el score**: cambia con cada minuto. El timestamp persistido + cálculo barato evita escrituras innecesarias.
- **Naive datetimes asumidos UTC**: la ingesta usa `datetime.now(timezone.utc)` pero los JSONL pueden traer cadenas sin tz; tratarlas como UTC mantiene la coherencia.
- **`fetched_at = None` → score 0**: si no podemos fechar el dato, no lo confiamos. Es estricto pero defensivo.
- **Timestamps futuros clampeados a `now`**: clock skew o data tampering no debe inflar el score por encima de 1.0.

