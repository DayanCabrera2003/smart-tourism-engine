# 03 - Modelo de RI: Booleano Extendido (p-norm)

## Motivación

El sistema utiliza el **Modelo Booleano Extendido** como modelo principal de recuperación de información. Este modelo fue propuesto por Salton, Fox y Wu en 1983 y resuelve las dos limitaciones fundamentales del Booleano clásico:

| Limitación (Booleano clásico) | Solución (Booleano Extendido) |
|-------------------------------|-------------------------------|
| Sin ranking: todos los documentos recuperados son equivalentes. | Produce una puntuación continua en [0, 1] que permite ordenar resultados. |
| Semántica rígida: un documento que cumple 9 de 10 condiciones AND es descartado. | La similitud degrada suavemente con los términos ausentes. |

Para el dominio de turismo, las consultas tienen estructura lógica explícita ("playa AND barato AND familiar") pero requieren ranking continuo para presentar los mejores destinos primero. El Booleano Extendido satisface ambas necesidades.

## Referencia principal

> Salton, G., Fox, E. A., & Wu, H. (1983).
> *Extended Boolean information retrieval.*
> Communications of the ACM, **26**(11), 1022–1036.

## Principio del modelo

El modelo interpola entre dos casos extremos mediante el parámetro **p**:

$$p = 1 \quad \Rightarrow \quad \text{comportamiento vectorial (media aritmética de pesos)}$$
$$p \to \infty \quad \Rightarrow \quad \text{comportamiento Booleano puro (min/max de pesos)}$$

Para turismo se recomienda $p \in [2, 5]$, que produce un ranking continuo con penalización moderada a los documentos que no contienen todos los términos obligatorios.

## Implementación

La clase `ExtendedBoolean` en `src/retrieval/extended_boolean.py` encapsula el modelo:

```python
from src.retrieval.extended_boolean import ExtendedBoolean

eb = ExtendedBoolean(p=2.0)   # p=2 recomendado como punto de partida
score = eb.score("beach AND tourism", "dest-001")
```

### Constructor

```python
ExtendedBoolean(p: float = 2.0)
```

| Parámetro | Valor por defecto | Descripción |
|-----------|-------------------|-------------|
| `p` | `2.0` | Parámetro de la norma. Debe ser estrictamente positivo. |

Lanza `ValueError` si `p ≤ 0`.

### Método `score`

```python
score(query: str, doc_id: str) -> float
```

Calcula la similitud p-norm entre una consulta y un documento.
Devuelve un valor en `[0, 1]`.

> **Estado actual (T032):** el método devuelve `0.0` como esqueleto.
> Las fórmulas OR e AND se implementan en T033 y T034 respectivamente.

## Fórmulas (introducción)

Los pesos $w_i \in [0, 1]$ son los pesos TF-IDF normalizados de cada término de la consulta en el documento evaluado. Las fórmulas se completan en las secciones siguientes conforme se implementan.

Las pruebas unitarias asociadas se encuentran en `tests/test_extended_boolean.py`.
