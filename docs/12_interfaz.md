# Interfaz de usuario

## T043 — Streamlit MVP

La UI vive en [`src/ui/app.py`](../src/ui/app.py) y se construye sobre
[Streamlit](https://streamlit.io/). El MVP expone un input de texto, un botón
**Buscar** y, desde T044, una lista de **tarjetas** por resultado. Las
imágenes (T045) y los sliders para `top_k` y `p` (T047) llegarán en tareas
siguientes.

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

### Manejo de errores

- Si la consulta está vacía, la UI muestra un aviso y no llama a la API.
- Si la API responde con un error HTTP (p.ej. `503` porque el índice aún no
  está construido), la UI captura la excepción de `httpx` y la muestra en un
  bloque de error, sin tumbar la sesión de Streamlit.
