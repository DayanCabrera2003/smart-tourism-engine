# 02 - Arquitectura del Sistema

Esta sección describe la arquitectura técnica del Smart Tourism Engine, los módulos que lo componen y sus responsabilidades.



## Estructura de Módulos (src/)

- **ingestion/**: Adquisición de datos desde fuentes externas (Wikivoyage, OpenTripMap), normalización y almacenamiento inicial.
- **indexing/**: Preprocesamiento de texto (tokenización, stemming) y construcción del índice invertido y embeddings.
- **retrieval/**: Lógica de búsqueda principal (Booleano Extendido, semántica e híbrida).
- **rag/**: Integración con LLM para generación de respuestas contextualizadas basadas en los resultados de búsqueda.
- **web_search/**: Módulo de fallback para búsquedas en la web cuando la información local es insuficiente.
- **multimodal/**: Soporte para búsqueda por imágenes y embeddings CLIP.
- **recommendation/**: Algoritmos de recomendación personalizados para los usuarios.
- **api/**: Definición de rutas FastAPI, esquemas y lógica de servidor.
- **ui/**: Implementación de la interfaz de usuario con Streamlit.

## Gestión de Datos (data/)

- **raw/**: Datos crudos obtenidos de los crawlers y scrapers (ignorado por Git).
- **processed/**: Índices construidos, caché de embeddings y datos limpios listos para el sistema.

## Otros Directorios

- **tests/**: Pruebas unitarias e integración para asegurar la robustez del sistema.
- **docs/**: Documentación técnica detallada siguiendo el formato LNCS.
- **docker/**: Configuraciones para la contenedorización del sistema.
- **scripts/**: Utilidades para tareas administrativas y de compilación del informe.

## Observabilidad

El sistema utiliza un esquema de **Logging Estructurado** en formato JSON, facilitando su integración con herramientas modernas de agregación y análisis de logs (como ELK Stack o Loki).

- **Estandarización**: Todos los logs del sistema, incluyendo los de librerías de terceros y FastAPI, son redirigidos a la salida estándar (`stdout`) con una estructura coherente.
- **Campos base**: `timestamp` (ISO-8601 UTC), `level`, `message`, `module`, `funcName` y `lineno`.
- **Configuración**: El nivel de detalle se ajusta mediante la variable de entorno `LOG_LEVEL` (vía `src/config.py`).
