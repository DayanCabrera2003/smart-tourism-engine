# Usamos una imagen base ligera de Python 3.11
FROM python:3.11-slim

# Evitar que Python genere archivos .pyc y permitir logs en tiempo real
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Configurar el directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copiar archivos de dependencias
COPY pyproject.toml .
COPY requirements.txt .

# Instalar dependencias del proyecto
# Se instala en modo editable para que el paquete 'src' sea reconocido correctamente
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir -e .

# Copiar el código fuente y el archivo de configuración de pytest
COPY src/ ./src/
COPY tests/ ./tests/
COPY pytest.ini .

# Crear directorios de datos
RUN mkdir -p data/raw data/processed data/eval

# Exponer el puerto (FastAPI por defecto usa 8000, Streamlit 8501)
EXPOSE 8000 8501

# Por defecto, ejecutamos el main de verificación como módulo
CMD ["python", "-m", "src.main"]
