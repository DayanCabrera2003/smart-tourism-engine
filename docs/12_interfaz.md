# Interfaz de usuario

## T043 — Streamlit MVP

La UI vive en [`src/ui/app.py`](../src/ui/app.py) y se construye sobre
[Streamlit](https://streamlit.io/). El MVP expone un input de texto, un botón
**Buscar** y, desde T044, una lista de **tarjetas** por resultado. Desde T045
cada tarjeta muestra además la primera imagen disponible del destino. Desde
T047 un sidebar con sliders permite ajustar `top_k` y `p` antes de cada
búsqueda.

### Arquitectura

```
┌──────────────┐   POST /search   ┌──────────────┐
│ Streamlit UI │ ───────────────▶ │  FastAPI API │
│  (app.py)    │ ◀─────────────── │ (main.py)    │
└──────────────┘   SearchResponse └──────────────┘
```

- La UI **no** habla con el índice ni con el recuperador directamente: todo
  pasa por el endpoint `POST /search` de la API, para mantener un único punto
  de entrada y poder reutilizar la misma lógica desde otros clientes.
- La llamada HTTP se encapsula en
  [`search_destinations`](../src/ui/app.py), una función pura que acepta un
  `httpx.Client` inyectable. Esto permite testearla sin levantar el runtime de
  Streamlit (ver [`tests/test_ui_app.py`](../tests/test_ui_app.py)).
- La URL de la API se configura con la variable de entorno
  `SMART_TOURISM_API_URL` (por defecto `http://localhost:8000`).

### Ejecución local

```bash
# 1. Levantar la API (en otra terminal):
uvicorn src.api.main:app --reload

# 2. Lanzar la UI:
streamlit run src/ui/app.py
```

La aplicación queda disponible en `http://localhost:8501`.

### Flujo de uso

1. El usuario escribe una consulta con operadores en mayúsculas, p.ej.
   `playa AND España`.
2. Al pulsar **Buscar**, la UI envía `{query, top_k: 10}` al endpoint
   `/search`.
3. Los resultados se muestran como una lista numerada `id — score`, ordenados
   de mayor a menor score tal y como los devuelve el Booleano Extendido.

## T044 — Tarjetas de destino

Desde T044 cada resultado se renderiza como una *card* en lugar de una línea
plana. La API acompaña cada destino con `name`, `country` y `description`
leídos de `destinations.db`; los tres campos son opcionales en el schema
[`DestinationResult`](../src/api/schemas.py) para no romper clientes previos y
para degradar con elegancia si un `id` no tiene metadatos (fallback: se
muestra el propio `id` como título).

### Anatomía de la tarjeta

```
┌──────────────────────────────────────────────────┐
│ ### 1. <name>                          [ score ] │
│ :earth_americas: <country> · `<id>`              │
│                                                   │
│ <descripción truncada a ~220 caracteres…>        │
└──────────────────────────────────────────────────┘
```

- **Título** (`st.markdown` con `###`): nombre del destino o id si falta.
- **Score** en una columna estrecha usando `st.metric`, con 3 decimales.
- **Línea meta** (`st.caption`): país (cuando existe) e identificador en
  monoespaciado para que sea copiable desde la UI.
- **Descripción truncada** por
  [`truncate_description`](../src/ui/app.py), que corta en el último espacio
  antes del límite y añade `…` para evitar partir palabras por la mitad.
- El contenedor usa `st.container(border=True)` para separar visualmente cada
  resultado sin introducir CSS propio.

La decisión de dejar la descripción completa en la respuesta de la API (y
truncar sólo en render) permite que otros clientes ajusten el límite sin
cambios en el backend.

## T045 — Imágenes en las tarjetas

Cuando `destinations.db` contiene URLs de imagen para un destino, la API las
expone en el campo `image_urls` del schema
[`DestinationResult`](../src/api/schemas.py) y la UI muestra **la primera
utilizable** en la card, justo debajo de la línea meta y antes de la
descripción:

```
┌──────────────────────────────────────────────────┐
│ ### 1. <name>                          [ score ] │
│ :earth_americas: <country> · `<id>`              │
│ ┌──────────────────────────────────────────────┐ │
│ │                  <imagen>                    │ │
│ └──────────────────────────────────────────────┘ │
│ <descripción truncada a ~220 caracteres…>        │
└──────────────────────────────────────────────────┘
```

### Degradación

El helper puro [`pick_cover_image`](../src/ui/app.py) elige la primera URL
válida de la lista (ignora entradas vacías o no-strings). Si la lista está
ausente, vacía o todas las URLs son inválidas, la card se renderiza **sin**
bloque de imagen, manteniendo el layout compacto del MVP. Si `st.image`
falla al cargar una URL marcada como válida, se captura la excepción y se
sustituye por un caption :frame_with_picture: `Imagen no disponible.` para
no tumbar la sesión de Streamlit.

La decisión de elegir una sola imagen (y no una galería) es deliberada para
el MVP: mantiene la densidad de la lista de resultados y evita cargas
pesadas cuando el top_k es alto. La búsqueda multimodal (T081+) reutilizará
el mismo campo `image_urls` más adelante.

## T047 — Sliders de `top_k` y `p` en el sidebar

El sidebar de Streamlit expone dos sliders que se leen en cada click de
**Buscar** y se envían al backend dentro del body de `POST /search`:

| Parámetro | Rango       | Default | Efecto |
|-----------|-------------|---------|--------|
| `top_k`   | `1` – `50`  | `10`    | Número máximo de destinos rankeados que devuelve la API. Bajar `top_k` acelera la respuesta cuando sólo interesa el podio; subirlo ayuda a explorar la larga cola. |
| `p`       | `1.0` – `10.0` (paso `0.5`) | `2.0` | Norma-p del Booleano Extendido (Salton, Fox & Wu, 1983). Controla cuán **estrictos** son los operadores `AND`/`OR` de la consulta. |

### Efecto de `p` en los resultados

La norma-p interpola de forma continua entre dos extremos clásicos de RI:

- **`p = 1` — comportamiento vectorial**: `AND` y `OR` colapsan a la media
  aritmética de los pesos TF-IDF. Los operadores son *blandos*: un documento
  con un solo término fuerte puede puntuar alto incluso en una consulta
  `AND`. Útil para *query expansion* y consultas exploratorias donde
  preferimos recall sobre precisión.
- **`p → ∞` — comportamiento Booleano puro**: `AND` converge al mínimo de
  los pesos y `OR` al máximo. Los operadores se vuelven *estrictos*: una
  consulta `playa AND España` exige que ambos términos aparezcan con peso
  significativo. Útil para consultas donde todos los términos son
  obligatorios.
- **`p ∈ [2, 5]` — zona recomendada para turismo**: equilibrio entre
  precisión y recall. El valor por defecto (`p = 2`) favorece resultados
  coherentes sin eliminar destinos que sólo cumplen parcialmente la
  consulta.

El endpoint construye un `ExtendedBoolean(p=request.p)` por petición a
través de la fábrica inyectable
[`get_retriever_factory`](../src/api/main.py), por lo que mover el slider
se refleja en el ranking inmediatamente sin reiniciar la API.

### Manejo de errores

- Si la consulta está vacía, la UI muestra un aviso y no llama a la API.
- Si la API responde con un error HTTP (p.ej. `503` porque el índice aún no
  está construido), la UI captura la excepción de `httpx` y la muestra en un
  bloque de error, sin tumbar la sesión de Streamlit.

## T048 — Demo Corte 1 (end-to-end)

Esta sección describe el flujo de demo que cierra el **Corte 1**: levantar
el sistema localmente, abrir la UI en el navegador y ejecutar una búsqueda
de ejemplo (`playa España`) que recorre toda la pila — UI → FastAPI →
recuperador Booleano Extendido → índice invertido → metadatos SQLite — y
devuelve tarjetas renderizadas en Streamlit.

### Prerrequisitos

Antes de la demo, los datos procesados deben existir en `data/processed/`:

```bash
# Una sola vez (o cada vez que cambie el corpus):
python -m src.cli ingest wikivoyage   # genera destinations.jsonl y .db
python -m src.cli build-index         # genera index.pkl
```

Esto produce 206 destinos (Wikivoyage España) y un índice invertido con
~4 100 términos.

### Pasos de la demo

1. **Levantar la API y la UI**:

   ```bash
   # Terminal 1:
   uvicorn src.api.main:app --reload

   # Terminal 2:
   streamlit run src/ui/app.py
   ```

   Espera a ver `Uvicorn running on http://127.0.0.1:8000` y
   `You can now view your Streamlit app in your browser`.

2. **Abrir la UI** en [http://localhost:8501](http://localhost:8501).

3. **Ajustar el sidebar** (opcional): dejar `top_k = 10` y `p = 2.0` para
   reproducir el comportamiento por defecto del Booleano Extendido.

4. **Buscar `playa España`** en el input principal y pulsar **Buscar**.

5. **Resultado esperado**: una lista de tarjetas ordenadas por `score`
   descendente, encabezadas por *Santa Cruz de Tenerife* (`score ≈ 0.06`
   con `p = 2`), cada una con su `name`, `country`, `id` monoespaciado y
   descripción truncada.

### Verificación rápida sin UI

Para chequear el backend de forma aislada (útil en CI o smoke tests):

```bash
curl -s -X POST http://localhost:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"query":"playa AND España","top_k":5,"p":2.0}' | jq '.results[0]'
```

La respuesta incluye `id`, `score`, `name`, `country`, `description` y
`image_urls`. Un `200` con al menos un resultado confirma que el índice
está cargado y que el enriquecimiento con SQLite funciona.

### Sobre las imágenes

El corpus actual de Wikivoyage-España se ingesta sin URLs de imagen (el
extractor de imágenes está pendiente de los pipelines de Wikidata/Commons
que aterrizarán en el Corte 2). En consecuencia, las tarjetas se
renderizan **sin** bloque de imagen aplicando la degradación descrita en
T045 — es el mismo *code path* que se ejercitará cuando lleguen URLs
reales, así que la demo valida tanto el camino feliz como el de
fallback.

> **Hito**: con esta demo reproducible queda cerrado el **Corte 1**
> (T001 – T048): ingestión + indexación + recuperador Booleano Extendido
> + API + UI Streamlit.

## T055 — Selector de modo y slider de alpha

La UI expone ahora tres modos de búsqueda seleccionables mediante radio
buttons en el sidebar:

| Modo | Endpoint | Descripción |
|------|----------|-------------|
| **Booleano Extendido** | `POST /search` | Rankeo léxico con p-norm (Salton/Fox/Wu 1983). Soporta operadores `AND`/`OR` en mayúsculas. |
| **Semántico** | `POST /search/semantic` | Embeddings densos con `all-MiniLM-L6-v2` consultados en Qdrant. Sin operadores; lenguaje natural. |
| **Hibrido** | `POST /search/hybrid` | Combinación lineal de ambos modos: `score = α · léxico + (1-α) · semántico`. |

### Slider de alpha

Visible únicamente en el modo **Hibrido**, el slider `alpha` recorre `[0.0, 1.0]`
en pasos de `0.05`:

- `alpha = 1.0` → solo Booleano Extendido (ignora la rama semántica).
- `alpha = 0.0` → solo semántico (ignora la rama léxica).
- `alpha = 0.5` → mezcla equilibrada (valor por defecto).

### Efecto sobre la consulta

En modo **Booleano Extendido**, el placeholder del input sigue siendo
`playa AND España` para recordar los operadores soportados. En modo
**Semántico** o **Hibrido**, cambia a `playas del caribe` para indicar
que se espera lenguaje natural. La diferencia es solo visual: el backend
acepta cualquier cadena en los tres endpoints.

### Parámetros combinados (modo Híbrido)

Cuando el modo es **Hibrido**, el sidebar muestra los tres parámetros:
`top_k`, `p` (para la rama léxica) y `alpha` (peso de la fusión). En modo
**Semántico** sólo aparece `top_k`, ya que el endpoint no consume `p` ni
`alpha`.
