# 16 - Manual de Usuario

Este manual describe cómo utilizar las diferentes interfaces del Smart Tourism Engine, tanto la línea de comandos (CLI) como la interfaz web (Streamlit).

## Interfaz de Línea de Comandos (CLI)

El sistema proporciona una herramienta CLI centralizada para tareas administrativas, de ingestión y procesamiento. Se recomienda ejecutarla desde el entorno virtual y la raíz del proyecto.

### Comandos de Ingestión

Para poblar el catálogo de destinos desde Wikivoyage, utilice:

```bash
python -m src.cli ingest wikivoyage
```

**Propósito**: Este comando lee los archivos JSON crudos de `data/raw/wikivoyage`, aplica los filtros de parsing y normalización de texto, y genera el archivo consolidado `data/processed/destinations.jsonl`.

### Construcción del índice invertido

Después de la ingestión, construya el índice invertido con:

```bash
python -m src.cli build-index
```

**Propósito**: Lee `data/processed/destinations.jsonl`, aplica el pipeline completo de
preprocesamiento (tokenización → eliminación de stopwords → stemming), construye el índice
invertido con pesos TF-IDF y normas L2, y guarda el resultado en
`data/processed/index.pkl`.

**Salida esperada**:
```
Índice construido: 206 documentos → data/processed/index.pkl
```

**Orden de ejecución recomendado**:

```bash
python -m src.cli ingest wikivoyage   # 1. Adquirir y procesar destinos
python -m src.cli build-index         # 2. Construir el índice invertido
```

### Comandos Generales de Ayuda

Para ver la lista de comandos disponibles:
```bash
python -m src.cli --help
```
o para un grupo específico:
```bash
python -m src.cli ingest --help
```

## Modo Preguntar (RAG)

El tab "Preguntar" permite formular preguntas en lenguaje natural.

1. Haz clic en el tab **"Preguntar"**.
2. Escribe tu pregunta: *"¿Qué destinos de playa en España son buenos para familias?"*
3. Pulsa **"Preguntar"**.
4. La respuesta aparece en tiempo real (streaming).
5. Las **fuentes** `[1]`, `[2]`... corresponden a los destinos expandibles al final.

Si aparece el aviso "Informacion insuficiente", el corpus no tiene datos para
esa pregunta. Intenta una búsqueda más general en el tab "Buscar destinos".
