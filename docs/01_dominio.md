# Dominio del Problema

Este capítulo describe el dominio que aborda el Smart Tourism Engine, los usuarios objetivo, los tipos de consulta que el sistema debe responder y los requisitos no funcionales que condicionan las decisiones técnicas del resto del proyecto.

---

## Motivación

La planeación de un viaje arrastra dos problemas que un buscador web tradicional resuelve solo a medias:

1. **Demasiada información, poca curaduría**: una búsqueda de "ciudades históricas en Europa" en Google devuelve millones de páginas, la mayoría comerciales o desactualizadas. El usuario tiene que filtrar a mano.
2. **Lenguaje natural y subjetivo**: "playas tranquilas para luna de miel" mezcla un concepto objetivo (playa) con uno subjetivo (tranquilo/romántico) que los modelos booleanos puros no pueden capturar.

El Smart Tourism Engine se construye como un sistema de **Recuperación de Información** (SRI) curado al dominio del turismo, con un corpus de destinos enriquecido y modelos que combinan búsqueda léxica clásica, embeddings semánticos densos, generación aumentada (RAG) y recomendación personalizada.

---

## Usuarios objetivo

| Persona | Necesidades dominantes |
|---|---|
| Viajero independiente (mochilero, aventurero) | Búsqueda flexible, sugerencias diversas, bajo presupuesto. |
| Familia | Destinos seguros, actividades para niños, servicios accesibles. |
| Pareja en luna de miel | Privacidad, atardeceres, gastronomía, recomendaciones cualitativas. |
| Viajero cultural | Patrimonio, museos, historia, fechas de festivales. |
| Viajero de lujo | Hoteles de gama alta, exclusividad. |

Los seis perfiles sintéticos del módulo de recomendación (`mochilero`, `familia`, `luna_de_miel`, `aventurero`, `cultural`, `lujo`) reflejan esta segmentación; ver [11 - Recomendación](11_recomendacion.md).

---

## Tipos de consulta soportados

| Tipo | Ejemplo | Modo del sistema |
|---|---|---|
| Booleana clásica | `playa AND España` | `POST /search` con `p=∞` |
| Booleana extendida (p-norm) | `playa AND España`, `p=2` | `POST /search` |
| Semántica | `playas tranquilas para luna de miel` | `POST /search/semantic` |
| Híbrida (léxica + semántica) | Cualquier query natural | `POST /search/hybrid` |
| Conversacional con respuesta generada | `¿Qué ciudades históricas debería visitar en España?` | `POST /ask` con citaciones |
| Multimodal texto → imagen | `playa tropical con palmeras` | `POST /search/image-by-text` |
| Multimodal imagen → destinos | Upload de una foto | `POST /search/by-image` |
| Recomendación basada en perfil | "Quiero destinos para mochileros" | `POST /recommend` con `user_id=synthetic:mochilero` |

---

## Requisitos funcionales

1. **Recuperación rankeada** con al menos tres estrategias (léxica, semántica, híbrida).
2. **Respuestas en lenguaje natural** (RAG) con citas de las fuentes recuperadas.
3. **Fallback a búsqueda web** cuando el corpus local no es suficiente (Tavily).
4. **Búsqueda multimodal** con CLIP (texto → imagen, imagen → texto, multimodal combinada).
5. **Recomendación personalizada** con perfiles sintéticos y filtrado content-based + pseudo-colaborativo.
6. **Posicionamiento avanzado** con score de popularidad, frescura y diversificación.
7. **API REST documentada** (Swagger automático vía FastAPI).
8. **UI accesible** desde navegador (Streamlit).
9. **Evaluación cuantitativa** con métricas estándar de IR (P@k, R@k, MAP, MRR, nDCG).

---

## Requisitos no funcionales

| Categoría | Requisito | Decisión técnica |
|---|---|---|
| Reproducibilidad | El sistema debe poder levantarse de cero desde el repo. | `pyproject.toml`, `requirements.txt`, scripts CLI versionados, queries.json en repo. |
| Observabilidad | Trazabilidad de cada request. | Logging JSON estructurado + `X-Request-ID` (T042). |
| Robustez | Ningún endpoint debe devolver 500 por inputs inválidos. | Validación Pydantic en boundary + handlers unificados de errores (T110). |
| Degradación | El sistema debe seguir respondiendo cuando un servicio externo cae. | 503 explícito si Qdrant no responde; respuesta vacía si el LLM falla. |
| Mantenibilidad | Una sola responsabilidad por archivo. | Estructura `src/{ingestion, indexing, retrieval, rag, web_search, multimodal, recommendation, api, ui, evaluation}`. |
| Testabilidad | Tests sin servicios externos. | Stubs/fakes para Qdrant, LLM y embedder; 500+ tests pytest. |
| Multiplataforma | Funciona en Linux y macOS sin Docker obligatorio. | Sin assumptions de Docker; Qdrant opcional como binario local o contenedor. |
| Seguridad | Sin credenciales hardcodeadas. | `.env` ignorado, `Settings` Pydantic, `LLM_API_KEY` y `TAVILY_API_KEY` por entorno. |

---

## Alcance y no-alcance

**Dentro del alcance:**

- Corpus de destinos turísticos (200+ entries).
- Recuperación léxica, semántica e híbrida.
- RAG con un LLM (Gemini) y fallback a Ollama local.
- Búsqueda web fallback con Tavily.
- Multimodal (texto + imagen) con CLIP.
- Recomendación con perfiles sintéticos.
- Posicionamiento avanzado y diversificación.
- Evaluación con métricas de IR.

**Fuera del alcance:**

- Reserva de vuelos u hospedaje.
- Pasarela de pago.
- Cuentas de usuario reales con autenticación.
- Reviews generadas por la comunidad.
- Mobile native app (la UI Streamlit es web responsive pero no nativa).
- Traducción automática multilingüe del corpus (el corpus actual es mono-idioma inglés).
