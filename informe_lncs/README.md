# Informe LNCS — 12 páginas

Versión condensada del informe del proyecto en plantilla LNCS (Lecture Notes in Computer Science), cumpliendo el límite de 12 páginas que pide la rúbrica de la entrega.

## Compilar

```bash
cd informe_lncs
xelatex -interaction=nonstopmode main.tex
xelatex -interaction=nonstopmode main.tex   # segundo pase para refs
```

Salida: `main.pdf` (~9 páginas).

## Archivos

- `main.tex` — fuente del informe.
- `main.pdf` — PDF compilado (entregable final).
- `llncs.cls`, `splncs03.bst`, `aliascnt.sty`, `remreset.sty` — plantilla LNCS oficial de Springer.
- `metrics_by_mode.png`, `heatmap_P_at_k.png`, `heatmap_nDCG_at_k.png` — figuras de evaluación (copiadas de `docs/figures/`).

## Diferencia con `docs/informe_final.pdf`

`docs/informe_final.pdf` es la referencia técnica detallada (~96 páginas, generada concatenando todos los markdowns de `docs/`). Sirve para estudio y consulta interna del autor.

`informe_lncs/main.pdf` es la versión académica para entrega: cumple el formato LNCS, el límite de 12 páginas y la estructura de un paper (abstract, secciones, referencias). Ambos documentos describen el mismo sistema; el LNCS sintetiza lo esencial.
