# 05 - Indexación y Preprocesamiento

Este documento describe el pipeline de procesamiento de texto utilizado para transformar el contenido crudo en un formato adecuado para la indexación y recuperación.

## Preprocesamiento

Antes de la tokenización, el texto de los destinos turísticos se somete a un proceso de normalización para reducir el ruido y asegurar que términos equivalentes se representen de la misma forma.

### Pipeline de Normalización

La normalización se implementa en `src/ingestion/normalize.py` y consta de los siguientes pasos:

1.  **Limpieza de HTML**: Eliminación de etiquetas residuales que puedan haber quedado tras el parseado inicial de fuentes web o dumps.
2.  **Conversión a Minúsculas**: Estandarización de todo el texto a minúsculas para evitar duplicidad de términos por capitalización.
3.  **Eliminación de Acentos (Stripping)**: Los caracteres con diacríticos se transforman a su versión base (ej. `á` -> `a`, `ñ` -> `n`). Esto facilita la recuperación independientemente de cómo el usuario introduzca la consulta.
4.  **Normalización de Espacios**: Eliminación de espacios en blanco adicionales, saltos de línea y tabulaciones, dejando un único espacio entre palabras.

### Ejemplo de Transformación

| Entrada | Salida |
|---------|--------|
| `  <p>¡Hola <b>España</b>!  </p> \n ¿Cómo está todo?  ` | `¡hola espana! ¿como esta todo?` |

Las pruebas unitarias asociadas se encuentran en `tests/test_normalize.py`.
