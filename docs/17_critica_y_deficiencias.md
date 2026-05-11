# Crítica y Deficiencias

Este capítulo recopila lo que el sistema hace bien, lo que no hace, lo que habría hecho diferente con el tiempo o conocimiento que tenemos hoy, y propuestas concretas de mejora. La transparencia sobre las limitaciones reales tiene más valor en la defensa que esconderlas.

---

## Bondades

### Cobertura amplia

El sistema implementa los nueve módulos del plan original más una capa adicional de posicionamiento y evaluación: ingesta, indexación léxica, recuperación con tres modos (Booleano Extendido, semántico, híbrido), RAG con citas y streaming, fallback web, multimodal con CLIP, recomendación con perfiles sintéticos, re-ranking y mapa interactivo, plus una suite de evaluación completa.

### Modelo Booleano Extendido bien estudiado

El recuperador léxico no se quedó en booleano clásico. El parámetro `p` (Salton/Fox/Wu 1983) permite interpolar continuamente entre vectorial puro y booleano estricto, y la UI lo expone como slider para que el usuario explore el efecto. El comportamiento se valida con tests específicos y se observó empíricamente sobre el corpus real (queries `beach OR mountain` reordenan picks con `p=1` vs `p=10`).

### Separación de responsabilidades

Cada módulo del `src/` tiene una responsabilidad única:

- `ingestion/` solo lee datos crudos y normaliza.
- `indexing/` solo construye índices y embeddings.
- `retrieval/` solo rankea.
- `rag/` solo orquesta la generación con contexto.
- `evaluation/` solo mide.
- `api/` solo expone HTTP.
- `ui/` solo dibuja.

Esta disciplina permite testear cada capa de forma aislada (más de 500 tests, todos pasan sin Qdrant ni Gemini reales) y abre la puerta a sustituir piezas sin tocar el resto.

### Manejo unificado de errores

Después de detectar en smoke tests que cuatro endpoints semánticos devolvían 500 cuando Qdrant caía, T110 registró handlers específicos en el middleware. La API ahora devuelve siempre la misma forma de body `{code, message}`, con status 422 para validación, 503 para servicios externos caídos y 500 sin filtrar trazas como último recurso.

### Reproducibilidad

`queries.json` está versionado y se regenera con un script idempotente. La popularidad se recalcula con otro script idempotente. El índice y los embeddings se reconstruyen con tres comandos CLI. Cualquiera con el repo y Python 3.11 puede levantar el sistema completo desde cero.

### Documentación amplia

Diecisiete capítulos `.md` cubren cada decisión técnica con su motivación, fórmulas (Booleano Extendido, métricas de IR, MMR, decay de frescura) y referencias a la bibliografía. El README explica explícitamente cómo verificar cada feature.

---

## Limitaciones

### Corpus mono-fuente y mono-idioma

Aunque la arquitectura prevé dos fuentes (Wikivoyage y OpenTripMap) y la documentación cubre la fusión con deduplicación por haversine, el corpus que se evalúa contiene **206 destinos solo de Wikivoyage**, todos en inglés. Esto tiene tres consecuencias:

1. La popularidad se aproxima por longitud de descripción y menciones cruzadas porque no hay `reviews_count` ni una segunda fuente que confirme la notoriedad de un destino.
2. Las queries en español dependen del embedder multilingüe (`all-MiniLM-L6-v2`) para puentear el gap. El recuperador léxico puro tiene desventaja inherente con queries en español sobre descripciones en inglés.
3. El corpus tiene **sesgo geográfico**: 48 de 206 destinos son España (23%), 20 Italia, 20 Francia. La sección "Variados por país" del posicionamiento existe precisamente para contrarrestarlo en el output.

### Imágenes no descargadas

El módulo multimodal está implementado y testeado con stubs, pero el script de descarga de imágenes no se ejecutó en esta entrega. `data/raw/images/` está vacío, así que los endpoints `/search/by-image`, `/search/image-by-text` y `/search/multimodal` devuelven 503 contra el corpus actual. La defensa puede mostrar la arquitectura y los tests, pero no una corrida end-to-end con imágenes reales.

### Tabla SQLite desincronizada

`data/processed/destinations.jsonl` tiene 206 entradas; la tabla SQLite `destinations` solo tiene 1 fila (residuo de un test antiguo). La UI degrada elegantemente (popularity, country y lat/lon en `null`) en el tab de búsqueda, pero la demo pide re-ingestar a SQLite. Esto se planificó como acción de data engineering pendiente de aprobación humana en lugar de incluirlo silenciosamente en una tarea de código.

### Métricas todavía parciales

La evaluación se corre solo en modo Booleano por defecto porque Qdrant no está levantado en el entorno donde se midió. Los números actuales (P@10 = 0.11, R@10 = 0.27, MAP = 0.22, MRR = 0.36, nDCG@10 = 0.29) son de referencia pero no permiten todavía la comparación contra semántico/híbrido. La comparación se hará en cuanto Qdrant esté materializado y los tres modos contribuyan a los plots.

### Sin evaluación cualitativa del LLM

El RAG está implementado y testeado contra mocks pero no hay un set de preguntas con respuestas correctas anotadas que mida la calidad de las respuestas generadas. T071 lo deja como "evaluación cualitativa opcional". Sería defendible añadir 10-20 preguntas con respuesta esperada y un "LLM como juez" para calificar.

### Anotación de queries todavía sin revisión humana

`queries.json` tiene 22 entradas anotadas por reglas objetivas (`country=X`, `keyword=X`). El campo `review_status: pending_human_validation` señala explícitamente que el equipo debería revisar cada lista antes de la defensa. Las reglas son auditables pero pueden tener falsos positivos (descripción con la palabra `wine` que en realidad no es región vinícola, etc.).

### Sin pruebas de carga

El sistema nunca se ha medido bajo concurrencia. No hay datos de latencia p95 ni de comportamiento bajo 50+ usuarios simultáneos. La caché en memoria del RAG (LRU por hash de query) reduciría la presión pero solo si hay patrones de tráfico que la justifiquen.

### Recomendación pseudo-colaborativa, no real

El módulo de recomendación se llama "colaborativo" pero no consume interacciones reales de usuarios: snapping a la persona sintética más cercana es una aproximación. Para un colaborativo real haría falta:

- Recolectar feedback (thumbs up/down planeado en T118 del buffer).
- Matriz usuario × destino.
- Factorización matricial o KNN sobre usuarios.

Esto requiere usuarios reales y persistencia que el alcance del proyecto no contempla.

### Configuración de Ollama no probada

El fallback offline a Ollama está documentado y el código existe (`LLM_PROVIDER=ollama`) pero no se probó contra una instancia real de Ollama. Una demo offline confiable requeriría correr ese path al menos una vez.

---

## Qué se haría diferente

### 1. Empezar con un set de evaluación más diverso

Las 22 queries actuales se anotaron al final del proyecto, cuando ya estaban tomadas todas las decisiones de modelado. Tenerlas desde el día uno habría permitido elegir el `p` por defecto, el `alpha` del híbrido y los pesos del re-ranker con números en mano, no por intuición.

### 2. Acoplar SQLite y JSONL desde la ingesta

Hoy la ingesta escribe el JSONL pero la SQLite quedó parcial. Una sola función `persist_destination(d)` que escriba a ambos en transacción evitaría el drift que detectamos en testing.

### 3. Implementar T117-T118 antes que T091-T098

El feedback de relevancia (thumbs up/down) y el histórico de búsquedas dan datos reales para mejorar el recomendador. Construir un recomendador antes de tener interacciones convierte el módulo en un ejercicio de cold-start con personas sintéticas, no en un colaborativo real.

### 4. Reservar tiempo para una corrida multimodal honesta

Implementar T081-T090 sin descargar imágenes deja el módulo como código testeado pero no validado contra contenido real. Asignar el último día solo a descarga + indexación de imágenes habría producido una demo multimodal demostrable.

### 5. Considerar pre-computar el centroide del corpus para el mapa

El mapa centra automáticamente en el centroide de los resultados. Para corpora globales con clusters dispersos (Asia + Sudamérica + Europa en el mismo top-k), el centroide cae en medio del océano. Sería más útil un bounding box automático.

---

## Propuestas de mejora a corto plazo

| ID propuesta | Esfuerzo | Beneficio |
|---|---|---|
| Re-ingestar SQLite desde JSONL | 1 hora | Activa popularity, country y mapa en la UI. |
| Descargar imágenes para 50 destinos top | 2-3 horas | Habilita multimodal end-to-end para demo. |
| 20 preguntas RAG con respuesta esperada | 1 día | Métricas cualitativas del LLM defensibles. |
| Revisión humana de queries.json | 2 horas | El ground truth deja de ser "pendiente". |
| Probar Ollama offline | 1 hora | Asegura el fallback antes de la demo. |
| Implementar thumbs up/down (T118) | 1 día | Empieza a recolectar señal real para el recomendador. |

---

## Limitaciones que no son resolvibles dentro del alcance

- **Corpus pequeño**: 206 destinos es mucho para tests, poco para diferencias estadísticamente significativas entre modos. Un corpus de 10,000+ requeriría infraestructura distinta (Qdrant en producción, índice TF-IDF persistido en disco, evaluación por batches).
- **LLM en cloud**: Gemini es un servicio externo con cuota y latencia variable. Para una demo crítica habría que asumir Ollama local con un modelo abierto, lo cual cambia las capacidades del RAG.
- **Sin login**: el producto es demo, no servicio. Añadir cuentas reales abre un eje (auth, sesiones, perfiles persistidos) que no estaba en el alcance.
