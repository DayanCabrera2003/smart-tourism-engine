# 15 - Despliegue y Requisitos

Este documento detalla los requisitos técnicos y los pasos necesarios para desplegar el Smart Tourism Engine en diferentes entornos.

## Requisitos del Sistema

### Software Base
- **Python**: Versión 3.11 o superior.
- **Qdrant**: Binario local para la base vectorial (ver sección de instalación).
- **Git**: Para el control de versiones y gestión del código fuente.

## Instalación del Entorno de Desarrollo

1. **Clonar el repositorio**:
   ```bash
   git clone <url-del-repositorio>
   cd smart-tourism-engine
   ```

2. **Crear y activar entorno virtual**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # En Linux/macOS
   # o
   .\venv\Scripts\activate   # En Windows
   ```

3. **Instalar dependencias**:
   El proyecto utiliza `pyproject.toml` para gestionar las dependencias. Puedes instalarlo en modo editable con:
   ```bash
   pip install -e .
   ```

   Para instalar también las herramientas de desarrollo (linting, tests):
   ```bash
   pip install -e ".[dev]"
   ```

   Como respaldo, también se incluye un archivo `requirements.txt`:
   ```bash
   pip install -r requirements.txt
   ```

## Estructura de Dependencias Clave
- **FastAPI**: Framework web para la API.
- **Pydantic**: Validación de datos y configuraciones.
- **Pytest**: Framework de pruebas unitarias.
- **Ruff/Black/Isort**: Herramientas de calidad de código y formateo.

## Variables de Entorno

El sistema se configura a través de variables de entorno que pueden definirse en un archivo `.env` en la raíz del proyecto. Estas son gestionadas mediante Pydantic Settings en `src/config.py`.

| Variable | Descripción | Valor por Defecto |
|----------|-------------|-------------------|
| `QDRANT_URL` | Dirección de la base vectorial Qdrant. | `http://localhost:6333` |
| `LLM_API_KEY` | Clave API para el servicio LLM (ej. Groq). | `None` |
| `LOG_LEVEL` | Nivel de verbosidad de los logs del sistema. | `INFO` |
| `DATA_DIR` | Ruta base para el almacenamiento de datos. | `data` |

Para configurar estas variables, copia el ejemplo:
```bash
cp .env.example .env
```
Y edita los valores según sea necesario.

## Arranque local del sistema

Con las dependencias instaladas y el corpus procesado, el sistema se levanta con dos procesos:

```bash
# Terminal 1 — API FastAPI
uvicorn src.api.main:app --reload

# Terminal 2 — UI Streamlit
streamlit run src/ui/app.py
```

La API queda disponible en `http://localhost:8000` y la UI en `http://localhost:8501`.

### Qdrant local

Qdrant se ejecuta como proceso independiente. Descarga el binario desde
[qdrant.tech/documentation/guides/installation](https://qdrant.tech/documentation/guides/installation/)
y arráncalo con:

```bash
./qdrant
```

Por defecto escucha en `http://localhost:6333`, que coincide con el valor de
`QDRANT_URL` en `.env`.

### Persistencia de datos

- `data/processed/destinations.db`: catálogo SQLite.
- `data/processed/index.pkl`: índice invertido.
- `data/processed/qdrant/`: vectores de Qdrant (si se configura `--storage-path`).

## Despliegue offline (Ollama) — T072

Para usar el sistema sin conexión a internet, configura Ollama como proveedor LLM:

1. Instala Ollama: https://ollama.com/download
2. Descarga el modelo: `ollama pull llama3`
3. En `.env`, cambia:
   ```
   LLM_PROVIDER=ollama
   OLLAMA_URL=http://localhost:11434
   OLLAMA_MODEL=llama3
   ```
4. Levanta la API: `uvicorn src.api.main:app --reload`
