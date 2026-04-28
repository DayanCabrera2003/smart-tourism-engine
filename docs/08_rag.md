# RAG — Retrieval-Augmented Generation (T061-T072)

## Arquitectura

El módulo RAG conecta el recuperador existente (Fase 4) con un LLM para generar
respuestas en lenguaje natural con citas a los destinos usados como contexto.

### Flujo

```
query → HybridRetriever → ContextBuilder → Prompt → LLMClient → respuesta con citas
```

### Módulos

| Módulo | Responsabilidad |
|---|---|
| `src/rag/llm_client.py` | Abstracción sobre Gemini y Ollama (T061, T072) |
| `src/rag/prompts.py` | Plantilla RAG con instrucciones de citas (T062) |
| `src/rag/context_builder.py` | Formatea destinos numerados para el prompt (T063) |
| `src/rag/pipeline.py` | Orquesta recuperación → contexto → generación → cache (T064, T068, T070) |

## Prompt (T062)

El prompt instruye al LLM a:
- Responder ÚNICAMENTE con la información del contexto provisto.
- Usar referencias `[1]`, `[2]`, etc. para citar los destinos.
- Responder "No tengo suficiente información" si el contexto es insuficiente.

## Citas inline (T067)

Los destinos se numeran en `ContextBuilder` en el mismo orden que llegan del
recuperador. El prompt instruye al LLM a usar `[N]` para referenciarlos. La UI
muestra las fuentes numeradas debajo de la respuesta.

## Detección de incertidumbre (T068)

Si la respuesta del LLM contiene patrones como "no tengo suficiente información",
el pipeline marca `low_confidence=True`. La respuesta no se cachea y la UI
muestra un aviso al usuario.

## Streaming (T069)

El endpoint `POST /ask/stream` devuelve `text/event-stream`:

```
data: <fragmento de texto>\n\n
data: [DONE]\n\n
data: {"sources": [...], "low_confidence": false}\n\n
```

La UI de Streamlit usa `st.write_stream` para mostrar los tokens en tiempo real.

## Cache (T070)

Las respuestas se cachean en memoria (dict con maxsize=128) con clave
`sha256(query|top_k|mode|alpha)`. Las respuestas con `low_confidence=True`
no se cachean.

## Proveedor LLM (T061/T072)

Seleccionado via `LLM_PROVIDER` en `.env`:

| Valor | SDK | Modelo |
|---|---|---|
| `gemini` (default) | `google-genai` | `gemini-2.5-flash` |
| `ollama` | httpx | configurable via `OLLAMA_MODEL` |

## Endpoints

| Método | Ruta | Descripción |
|---|---|---|
| POST | `/ask` | Respuesta completa en JSON |
| POST | `/ask/stream` | Respuesta en streaming SSE |

## Tests

| Archivo | Qué verifica |
|---|---|
| `tests/test_rag_llm_client.py` | LLMClient con stubs de Gemini y Ollama |
| `tests/test_rag_prompts.py` | Plantilla RAG y reglas de citas |
| `tests/test_rag_context_builder.py` | Formato numerado, truncado, fallbacks |
| `tests/test_rag_pipeline.py` | Pipeline end-to-end, cache, low_confidence, 5 queries (T071) |
| `tests/test_api_ask.py` | Endpoint /ask con pipeline mockeado |
| `tests/test_api_ask_stream.py` | Chunks SSE, evento [DONE], JSON de sources |
