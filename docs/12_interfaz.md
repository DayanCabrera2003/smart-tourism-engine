# Interfaz de usuario

## T043 — Streamlit MVP

La UI vive en [`src/ui/app.py`](../src/ui/app.py) y se construye sobre
[Streamlit](https://streamlit.io/). El MVP expone un input de texto, un botón
**Buscar** y, desde T044, una lista de **tarjetas** por resultado. Desde T045
cada tarjeta muestra además la primera imagen disponible del destino. Los
sliders para `top_k` y `p` (T047) llegarán en tareas siguientes.

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
  `SMART_TOURISM_API_URL` (por defecto `http://localhost:8000`), lo que
  facilita montar el servicio en Docker Compose (T046).

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

### Manejo de errores

- Si la consulta está vacía, la UI muestra un aviso y no llama a la API.
- Si la API responde con un error HTTP (p.ej. `503` porque el índice aún no
  está construido), la UI captura la excepción de `httpx` y la muestra en un
  bloque de error, sin tumbar la sesión de Streamlit.
