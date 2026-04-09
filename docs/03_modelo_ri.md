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

## Fórmulas

Los pesos $w_i \in [0, 1]$ son los pesos TF-IDF normalizados de cada término de la consulta en el documento evaluado.

### OR p-norm (T033)

Para una consulta OR con $n$ términos y pesos $w_1, w_2, \ldots, w_n$:

$$\text{sim}_{OR}(d, q) = \left( \frac{\sum_{i=1}^{n} w_i^{\,p}}{n} \right)^{1/p}$$

**Propiedades clave:**

| Valor de $p$ | Comportamiento |
|---|---|
| $p = 1$ | Media aritmética — comportamiento vectorial puro |
| $p = 2$ | Norma euclidiana normalizada — recomendado para turismo |
| $p \to \infty$ | $\max(w_i)$ — Booleano puro: basta que un término ocurra |

**Ejemplo numérico** (Salton et al., 1983):

Consulta: `"playa OR montaña"` con $p=2$.  
Pesos en el documento: $w_{\text{playa}} = 0.6$, $w_{\text{montaña}} = 0.8$.

$$\text{sim}_{OR} = \left( \frac{0.6^2 + 0.8^2}{2} \right)^{1/2} = \left( \frac{0.36 + 0.64}{2} \right)^{1/2} = \sqrt{0.5} \approx 0.707$$

El documento obtiene una similitud de $0.707$, intermedia entre el 0 del Booleano clásico (si ningún término coincide perfectamente) y el 1 total.

**Implementación:**

```python
from src.retrieval.extended_boolean import ExtendedBoolean

eb = ExtendedBoolean(p=2.0)
sim = eb.or_norm([0.6, 0.8])  # → 0.7071
```

### AND p-norm (T034)

Para una consulta AND con $n$ términos y pesos $w_1, w_2, \ldots, w_n$:

$$\text{sim}_{AND}(d, q) = 1 - \left( \frac{\sum_{i=1}^{n} (1 - w_i)^{\,p}}{n} \right)^{1/p}$$

La fórmula penaliza los términos ausentes ($(1 - w_i)$ alto) y es el complemento simétrico del OR.

**Propiedades clave:**

| Valor de $p$ | Comportamiento |
|---|---|
| $p = 1$ | Media aritmética — comportamiento vectorial puro |
| $p = 2$ | Norma euclidiana complementada — recomendado para turismo |
| $p \to \infty$ | $\min(w_i)$ — Booleano puro: todos los términos deben ocurrir |

**Relación entre AND y OR:** para los mismos pesos y $p$, siempre se cumple $\text{sim}_{AND} \leq \text{sim}_{OR}$. El AND es más exigente.

**Ejemplo numérico** (Salton et al., 1983):

Consulta: `"playa AND montaña"` con $p=2$.  
Pesos en el documento: $w_{\text{playa}} = 0.6$, $w_{\text{montaña}} = 0.8$.

$$\text{sim}_{AND} = 1 - \left( \frac{(1-0.6)^2 + (1-0.8)^2}{2} \right)^{1/2} = 1 - \left( \frac{0.16 + 0.04}{2} \right)^{1/2} = 1 - \sqrt{0.1} \approx 0.684$$

El documento puntúa $0.684$: el término "montaña" está bien representado ($w=0.8$) pero "playa" sólo a medias ($w=0.6$), lo que penaliza el AND respecto al OR ($0.707$).

**Implementación:**

```python
from src.retrieval.extended_boolean import ExtendedBoolean

eb = ExtendedBoolean(p=2.0)
sim = eb.and_norm([0.6, 0.8])  # → 0.6838
```

Las pruebas unitarias asociadas se encuentran en `tests/test_extended_boolean.py`.
