# syntax=docker/dockerfile:1.6
# Smart Tourism Engine - imagen unica para API (FastAPI), UI (Streamlit) y CLI.
# Base slim + torch CPU-only para mantener la imagen alrededor de 2 GB.

FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=300 \
    PIP_RETRIES=8 \
    HF_HOME=/cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/cache/huggingface/sentence-transformers \
    NLTK_DATA=/cache/nltk_data

# Dependencias de sistema:
#   - libgomp1: requerido por torch/sklearn
#   - libjpeg62-turbo, libpng16-16, zlib1g: backends de Pillow
#   - curl: healthchecks de Docker
#   - ca-certificates: TLS hacia Wikidata/Wikipedia/Tavily
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgomp1 \
        libjpeg62-turbo \
        libpng16-16 \
        zlib1g \
        curl \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instalar primero torch CPU-only para evitar que sentence-transformers
# arrastre la build con GPU/CUDA (que pesa ~2 GB).
RUN pip install --extra-index-url https://download.pytorch.org/whl/cpu \
        "torch==2.5.1+cpu"

# Resto de dependencias declaradas en requirements.txt + las que solo viven
# en pyproject.toml (nltk) o que conviene fijar explicitamente.
COPY requirements.txt ./
# transformers 5.6+ rompe sentence-transformers 5.3. Pineamos al combo
# verificado localmente para reproducibilidad y para evitar el NameError
# de transformers.integrations.accelerate (nn no importado).
RUN pip install -r requirements.txt \
        qdrant-client \
        "sentence-transformers==5.3.0" \
        "transformers==5.5.0" \
        nltk \
        sqlalchemy

# Pre-descargar los datos de NLTK que usa el preprocesador
RUN python -c "import nltk; nltk.download('punkt', download_dir='${NLTK_DATA}'); nltk.download('punkt_tab', download_dir='${NLTK_DATA}'); nltk.download('stopwords', download_dir='${NLTK_DATA}')"

# Copiar el codigo fuente y los scripts (el .dockerignore filtra basura)
COPY pyproject.toml ./
COPY src ./src
COPY scripts ./scripts
COPY start.sh ./start.sh

# Instalar el paquete en modo editable para que `python -m src.cli` funcione
RUN pip install -e . --no-deps

# Usuario no-root con permisos sobre /app y /cache
RUN useradd -m -u 1000 appuser \
    && mkdir -p /cache/huggingface /cache/nltk_data /app/data \
    && chown -R appuser:appuser /app /cache

USER appuser

EXPOSE 8000 8501

# Por defecto arranca la API. La UI usa el mismo Dockerfile cambiando el CMD
# en docker-compose.yml.
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
