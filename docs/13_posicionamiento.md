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

---

## T101 — Re-ranker combinado

`src/retrieval/reranker.py` define `Reranker`, que toma los `top_k` resultados del recuperador y los reordena por una combinación convexa de cuatro señales.

### Fórmula

$$
\mathrm{score_{final}}(d) = w_{rel} \cdot \mathrm{relevance}(d) + w_{pop} \cdot \mathrm{popularity}(d) + w_{fresh} \cdot \mathrm{freshness}(d) + w_{pers} \cdot \mathrm{personalization}(d)
$$

Con $\sum w_i = 1$ (los pesos se renormalizan al construir el objeto). Todos los componentes viven en $[0, 1]$, así que el resultado también.

### Pesos por defecto

| Peso | Valor | Justificación |
|---|---|---|
| `relevance` | **0.55** | El usuario pidió algo concreto; honrar esa intención es la prioridad. |
| `popularity` | **0.20** | Empuja destinos sólidos del corpus a la superficie sin dominarla. |
| `freshness` | **0.10** | Frescura es relevante pero secundaria a "encaja con la query". |
| `personalization` | **0.15** | Bajo por defecto: solo se activa cuando hay perfil de usuario. |

Las cuatro señales son **independientes**: la query manda quién compite, popularidad/frescura/personalización deciden el orden entre quienes ya pasaron el corte.

### Componente de personalización

Se calcula como coseno entre el embedding del perfil del usuario (T091) y el embedding del destino (Qdrant `destinations_text`). Decisiones:

- **Coseno clampeado a $[0, 1]$**: un destino "anti-similar" (cos negativo) no se penaliza, solo no se boostea. Empujarlo hacia abajo sería castigar al usuario por no encajar perfectamente con su declaración.
- **Sin embedding del usuario → peso redistribuido**: si el usuario es anónimo, el peso de personalización se redistribuye proporcionalmente entre los otros tres componentes. Eso preserva $\sum w_i = 1$ y el rango $[0, 1]$ del resultado.

### Decisiones de diseño

- **Pesos por estrategia**: el `Reranker` acepta `RerankWeights` por instancia. La UI puede crear varios reranqueadores con perfiles distintos: uno popularidad-heavy para la sección "Populares", otro personalización-heavy para "Recomendado para ti", todos compartiendo la misma estructura.
- **Función pura sobre hits ya recuperados**: no toca Qdrant ni LLM. Su input son tuplas `(id, relevance)` y diccionarios laterales. Es trivial de testear y barato de ejecutar por request.
- **Señales ausentes valen 0**: si un destino no tiene popularidad calculada o no está embebido, su componente correspondiente cuenta como cero en lugar de explotar. Esto permite degradar elegante con corpus parciales.

---

## T102 — Diversificación con MMR

`src/retrieval/diversify.py` implementa Maximal Marginal Relevance (Carbonell & Goldstein, 1998) para evitar que el top-k contenga diez resultados visualmente iguales (diez playas del Caribe, diez capitales europeas).

### Algoritmo (greedy)

Sea $S$ el conjunto seleccionado en cada iteración. Para cada candidato $d$ del pool restante:

$$
\mathrm{MMR}(d) = \lambda \cdot \mathrm{relevance}(d) - (1 - \lambda) \cdot \max_{d' \in S} \cos(\mathrm{emb}(d), \mathrm{emb}(d'))
$$

El siguiente seleccionado es $\arg\max_d \mathrm{MMR}(d)$. La primera elección no tiene $S$ aún, así que es pura relevancia (la "semilla").

Iteración hasta llenar `top_k` o vaciar el pool.

### Hiperparámetro lambda

| `lambda_` | Comportamiento |
|---|---|
| `1.0` | Sin diversificación — el ranking original sale intacto. |
| `0.7` (default) | Relevancia domina pero los duplicados visibles se reorganizan hacia abajo. |
| `0.5` | Equilibrio: la mitad del peso es relevancia, la otra mitad diversidad. |
| `0.0` | Maximum diversity. Útil para una sección "Visualmente similares" intencionalmente variada. |

### Manejo de destinos sin embedding

MMR no puede operar sobre destinos no embebidos (no hay vector para medir similitud). En vez de descartarlos, los **apila al final del resultado** preservando su orden relativo. Esto:

- Cubre el caso de un corpus parcialmente embebido (cuando el último batch de ingesta aún no llegó a Qdrant).
- Garantiza que el `top_k` solicitado se puede satisfacer aunque solo una fracción esté embebida.

### Decisiones de diseño

- **Greedy en lugar de óptimo global**: la formulación óptima es NP-hard; el greedy es el estándar de facto en IR y produce resultados indistinguibles en la práctica para `top_k` típicos (5-20).
- **Conserva los scores originales**: MMR no rescribe relevancia, solo decide el orden. Si la UI quiere mostrar el score, ve el mismo número que el recuperador devolvió.
- **Coseno reutilizado**: usa `cosine_similarity` de `src/retrieval/reranker.py` para no duplicar implementaciones del producto interno.
- **MMR no es siempre la mejor opción**: para queries muy específicas ("museos en Madrid"), forzar diversidad puede empujar resultados peores arriba. El módulo es una herramienta, no se aplica por defecto en todas las búsquedas; la UI decide cuándo activarlo (T103).

---

## T103 — Secciones en la UI

`src/retrieval/positioning.py` y `src/ui/app.py::build_positioning_sections_from_results` agrupan los mismos hits en cuatro secciones que el usuario puede expandir desde el tab de búsqueda.

### Secciones

| Sección | Estrategia | Cuándo es útil |
|---|---|---|
| **Más relevantes** | Ranking original del recuperador (Booleano / semántico / híbrido). | El usuario sabe lo que busca y quiere el orden que vino del back-end. |
| **Populares** | Re-rank con `popularity_weight = 0.7` sobre los mismos hits. La relevancia sigue contando 0.3 para no degenerar a un top-N global. | Cuando la query es ambigua y se quiere ver primero los destinos más sólidos del corpus. |
| **Recientes** | Re-rank con `freshness_weight = 0.7`. Frescura se calcula al vuelo desde `fetched_at` con `freshness_score` (T100). | Cuando la información cambia rápido (eventos, restricciones de viaje). |
| **Variados (por país)** | Greedy: el primero por relevancia; cada siguiente debe ser un país nuevo hasta agotar países distintos; el resto rellena en orden de relevancia. | Para contrarrestar el sesgo geográfico del corpus (48 destinos de España de 206). |

### Por qué no aplicar MMR para "Variados"

La sección "Visualmente similares" del plan original asume el índice multimodal CLIP poblado, que en nuestro corpus está vacío (cero imágenes descargadas). En su lugar diversificamos por país, que es información presente en SQLite y se calcula sin tocar Qdrant ni CLIP. Cuando el índice de imágenes esté listo, basta cambiar el helper `diverse_by_country_section` por uno basado en `apply_mmr` con embeddings CLIP — la firma y el contrato hacia la UI siguen igual.

### Fuente de las señales

La UI no llama al backend N veces (una por sección). Las cuatro secciones se construyen en local a partir de un único `SearchResponse` que ahora trae `popularity` y `fetched_at` además de los campos previos. El backend popula esos campos desde la tabla SQLite `destinations`, así que la UI funciona aunque Qdrant esté caído (mientras tenga las metadatas en local).

### Decisiones de diseño

- **Helper centralizado en `src/api/main.py::_build_destination_result`**: los cuatro endpoints (`/search`, `/search/semantic`, `/search/hybrid`, `/recommend`) usan el mismo helper para componer la respuesta, evitando que un endpoint olvide propagar popularity o fetched_at.
- **Fallback a relevancia si la señal falta**: si el corpus aún no tiene popularity (BD legacy sin migrar) o country (resultados de la búsqueda web Tavily), la sección correspondiente devuelve el orden de relevancia. La UI nunca tiene que manejar una clave faltante.
- **Toggle opt-in**: el usuario marca "Agrupar por estrategia de posicionamiento". El render por defecto sigue siendo el listado lineal, para no penalizar a quien quiere el flujo directo.

---

## T104 — Mapa interactivo

El tab de búsqueda ofrece un toggle "Mostrar mapa interactivo" que renderiza los destinos geocodificados sobre un mapa Folium usando `streamlit-folium`.

### Comportamiento

1. La UI llama al endpoint de búsqueda como siempre.
2. `results_with_coordinates(results)` filtra los `DestinationResult` que tienen `latitude` y `longitude`. Resultados con coordenadas parciales (solo una de las dos) se tratan como ausentes.
3. `map_center(results)` calcula el centroide promedio para centrar el mapa.
4. Cada destino se renderiza como un `folium.Marker` con tooltip (`rank. name`) y popup HTML generado por `build_marker_popup_html`.
5. La UI muestra una caption con la fracción de resultados con coordenadas (`179 de 206 tienen coords`).

### Popup HTML

Se construye en una función pura para poder testearla sin Streamlit:

- Negrita: nombre del destino (o id si no hay nombre).
- Itálica: país (omitido si no hay).
- Score formateado a tres decimales.
- Descripción truncada a 199 chars + elipsis si es larga.
- Caracteres especiales se escapan con `html.escape` para evitar romper el popup con comillas o `<script>` en la descripción.

### Decisiones de diseño

- **Imports lazy de folium**: la app no debe romper en sistemas que solo corren tests/lint y no instalan `streamlit-folium`. Los imports están dentro de `_render_results_map`.
- **Coordenadas como campos opcionales en `DestinationResult`**: con validación `[-90, 90]` para lat y `[-180, 180]` para lon. Resultados sin coordenadas (búsqueda web Tavily, destinos legacy) no rompen el mapa; simplemente quedan fuera de la capa de marcadores.
- **Cobertura del corpus**: 179 de 206 destinos de Wikivoyage traen coordenadas (Wikivoyage no las expone para subdistritos y barrios). El 13% restante aparece en la lista lineal pero no en el mapa, lo cual la UI explicita en la caption.
- **Sin layer extra de popularidad/frescura en el mapa**: el mapa no es el lugar para rankear; es el lugar para ubicar geográficamente. Mantenerlo simple evita iconos rojos/verdes que el usuario tiene que interpretar.





