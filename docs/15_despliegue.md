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
| `LLM_API_KEY` | Clave API para Gemini (modelo LLM por defecto). | `None` |
| `LLM_PROVIDER` | Proveedor del LLM: `gemini` (default) u `ollama` para uso offline. | `gemini` |
| `OLLAMA_URL` | URL base de Ollama (solo si `LLM_PROVIDER=ollama`). | `http://localhost:11434` |
| `OLLAMA_MODEL` | Modelo de Ollama (solo si `LLM_PROVIDER=ollama`). | `llama3` |

## T114 — Generar el informe final en PDF

El sistema incluye un script reproducible para concatenar los markdowns de `docs/` y producir un PDF estilo LNCS.

### Requisitos

- **pandoc** (no está incluido en las dependencias Python).
- Un motor LaTeX: **xelatex** (preferido por Unicode) o **pdflatex** como fallback.

Instalación según sistema:

```bash
# Fedora / RHEL
sudo dnf install pandoc texlive-scheme-medium

# Debian / Ubuntu
sudo apt install pandoc texlive-xetex texlive-fonts-recommended

# macOS (brew)
brew install pandoc basictex
```

### Ejecución

```bash
# Build a docs/informe_final.pdf
./scripts/build_pdf.sh

# Build a una ruta custom
./scripts/build_pdf.sh /tmp/sri_informe.pdf
```

El script:

1. Verifica que `pandoc` esté en `$PATH`; si no, imprime instrucciones por sistema y sale con `exit 1`.
2. Elige `xelatex` si está disponible, si no `pdflatex`.
3. Concatena los 17 capítulos (`docs/01_dominio.md` ... `docs/17_critica_y_deficiencias.md` + `bibliografia.md`) en el orden de `docs/00_indice.md`.
4. Inyecta metadatos (título, autor, fecha) y genera tabla de contenidos numerada hasta nivel 2.
5. Aplica papel A4, márgenes 2.5 cm, fuente DejaVu Sans 11pt.

### Fuentes (opcional)

Por defecto el script usa la familia **Latin Modern** que viene con `texlive-collection-fontsrecommended`, por lo que funciona sin instalar nada extra. Para una tipografía más amplia con cobertura Unicode completa (recomendado para evitar warnings con caracteres `∈ ≈ α` y los box-drawing `─ ┘`):

```bash
sudo dnf install -y dejavu-sans-fonts dejavu-sans-mono-fonts dejavu-serif-fonts

# Y al correr el script:
MAINFONT="DejaVu Sans" MONOFONT="DejaVu Sans Mono" ./scripts/build_pdf.sh
```

Las variables `MAINFONT` y `MONOFONT` se honran solo si están seteadas, así que `./scripts/build_pdf.sh` solo (sin variables) usa Latin Modern.

### Estado verificado

Probado en Fedora 43 con `pandoc 3.6.4`, `xelatex` de `texlive-xetex svn66203-95.fc43.1`. Resultado: `docs/informe_final.pdf` de 86 páginas, 354 KB, incluye tabla de contenidos numerada hasta nivel 2 y los 18 capítulos en el orden del índice.
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
