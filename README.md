# Smart Tourism Engine

Sistema de Recuperación de Información (SRI) para el dominio de **turismo y viajes**, desarrollado como Proyecto Integrador del curso de SRI (2025-2026, 2do semestre). El sistema permite consultas en lenguaje natural sobre destinos turísticos y devuelve resultados rankeados con respuestas generadas (RAG), con soporte multimodal (texto + imágenes) y recomendaciones personalizadas.

---

## 👥 Equipo
- Dayan Cabrera Corvo

## 🚀 Tecnologías
- **Backend:** FastAPI
- **Frontend:** Streamlit
- **Base Vectorial:** Qdrant
- **Modelo de RI:** Booleano Extendido (p-norm)
- **LLM:** Groq (Llama 3.3)
- **Embeddings:** CLIP y Sentence-Transformers

## 📁 Documentación
El informe detallado se encuentra en la carpeta `docs/`. El índice principal está en [docs/00_indice.md](docs/00_indice.md).

## 💻 Desarrollo e Instalación

### 1. Requisitos
- Python 3.11+
- Docker y Docker Compose

### 2. Configuración del Entorno
```bash
# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # En Linux/macOS

# Instalar dependencias en modo editable (incluyendo dev)
pip install -e ".[dev]"
```

### 3. Configuración de Calidad de Código (Pre-commit)
Este proyecto utiliza `pre-commit` para asegurar que el código cumpla con los estándares antes de cada commit (Black, Ruff, Isort).

```bash
# Instalar los hooks en el repositorio local
pre-commit install

# (Opcional) Ejecutar en todos los archivos manualmente
pre-commit run --all-files
```

### 4. Variables de Entorno
Copia el archivo de ejemplo y configura tus claves:
```bash
cp .env.example .env
```

## 📄 Licencia
Este proyecto está bajo la Licencia MIT. Ver el archivo [LICENSE](LICENSE) para más detalles.
