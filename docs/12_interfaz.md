# Interfaz de usuario

## T043 — Streamlit MVP

La UI mínima vive en [`src/ui/app.py`](../src/ui/app.py) y se construye sobre
[Streamlit](https://streamlit.io/). En este corte el alcance es deliberadamente
reducido: un input de texto, un botón **Buscar** y una lista plana de
resultados (identificador del destino y score). Las tarjetas visuales (T044),
las imágenes (T045) y los sliders para `top_k` y `p` (T047) llegarán en tareas
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

### Manejo de errores

- Si la consulta está vacía, la UI muestra un aviso y no llama a la API.
- Si la API responde con un error HTTP (p.ej. `503` porque el índice aún no
  está construido), la UI captura la excepción de `httpx` y la muestra en un
  bloque de error, sin tumbar la sesión de Streamlit.
