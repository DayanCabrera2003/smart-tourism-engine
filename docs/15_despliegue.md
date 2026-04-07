# 15 - Despliegue y Requisitos

Este documento detalla los requisitos técnicos y los pasos necesarios para desplegar el Smart Tourism Engine en diferentes entornos.

## Requisitos del Sistema

### Software Base
- **Python**: Versión 3.11 o superior.
- **Docker & Docker Compose**: Necesarios para el despliegue de la base vectorial (Qdrant) y la contenedorización de la aplicación.
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
