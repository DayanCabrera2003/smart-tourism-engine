#!/usr/bin/env bash
# T114 - Build the LNCS-style PDF report from the markdown chapters.
#
# Usage:
#   scripts/build_pdf.sh                 # build to docs/informe_final.pdf
#   scripts/build_pdf.sh /tmp/foo.pdf    # custom output path
#
# Requires pandoc and a LaTeX engine (xelatex or pdflatex) on the PATH.
# If pandoc is missing, the script explains how to install it and exits
# non-zero so the user knows the PDF was not produced.
set -euo pipefail

OUTPUT="${1:-docs/informe_final.pdf}"

if ! command -v pandoc >/dev/null 2>&1; then
    cat >&2 <<'EOF'
ERROR: pandoc is not installed.

Install it before running this script:

    Fedora / RHEL:   sudo dnf install pandoc texlive-scheme-medium
    Debian / Ubuntu: sudo apt install pandoc texlive-xetex texlive-fonts-recommended
    macOS (brew):    brew install pandoc basictex

The script will then concatenate the markdown chapters and emit a
single PDF with the LNCS-style template.
EOF
    exit 1
fi

# Pick the first available LaTeX engine (xelatex preferred for Unicode).
if command -v xelatex >/dev/null 2>&1; then
    ENGINE="xelatex"
elif command -v pdflatex >/dev/null 2>&1; then
    ENGINE="pdflatex"
else
    echo "ERROR: no LaTeX engine found (xelatex or pdflatex)." >&2
    exit 1
fi

# Chapter order matches docs/00_indice.md.
CHAPTERS=(
    docs/01_dominio.md
    docs/02_arquitectura.md
    docs/03_modelo_ri.md
    docs/04_adquisicion_datos.md
    docs/05_indexacion.md
    docs/06_recuperador.md
    docs/07_base_vectorial.md
    docs/08_rag.md
    docs/09_busqueda_web.md
    docs/10_multimodal.md
    docs/11_recomendacion.md
    docs/12_interfaz.md
    docs/13_posicionamiento.md
    docs/14_evaluacion.md
    docs/15_despliegue.md
    docs/16_manual_usuario.md
    docs/17_critica_y_deficiencias.md
    docs/bibliografia.md
)

# Sanity check.
for chapter in "${CHAPTERS[@]}"; do
    if [[ ! -f "$chapter" ]]; then
        echo "ERROR: chapter not found: $chapter" >&2
        exit 1
    fi
done

mkdir -p "$(dirname "$OUTPUT")"

echo "Building $OUTPUT with $ENGINE..."
pandoc \
    --from=markdown \
    --to=pdf \
    --pdf-engine="$ENGINE" \
    --toc \
    --toc-depth=2 \
    --number-sections \
    --metadata title="Smart Tourism Engine — Informe Final" \
    --metadata author="Dayan Cabrera Corvo" \
    --metadata date="$(date +%Y-%m-%d)" \
    --variable documentclass=article \
    --variable papersize=a4 \
    --variable geometry:margin=2.5cm \
    --variable fontsize=11pt \
    --variable mainfont="DejaVu Sans" \
    --variable monofont="DejaVu Sans Mono" \
    --output="$OUTPUT" \
    "${CHAPTERS[@]}"

echo "OK: $OUTPUT"
