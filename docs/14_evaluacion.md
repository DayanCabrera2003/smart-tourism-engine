# Evaluación del Sistema

Este capítulo documenta la metodología de evaluación del recuperador. Cubre el conjunto de queries con ground truth (T105), las métricas implementadas (T106, T107) y el script de evaluación (T108).

---

## T105 — Conjunto de queries de prueba

El archivo `data/eval/queries.json` contiene **22 queries en español e inglés** con su lista de destinos relevantes (ground truth). El archivo se versiona con el repositorio para que la evaluación sea reproducible.

### Estructura

```json
{
  "metadata": {
    "version": "1.0",
    "total_queries": 22,
    "annotation_methodology": "...",
    "review_status": "pending_human_validation",
    "corpus_size": 206
  },
  "queries": [
    {
      "id": "q01",
      "query": "Madrid",
      "language": "es",
      "annotation_rule": "id=wikivoyage-madrid",
      "relevant": ["wikivoyage-madrid"],
      "relevant_count": 1
    }
  ]
}
```

### Metodología de anotación

Las 22 queries se anotan **por reglas objetivas derivadas del corpus**, no a juicio subjetivo. Cada entrada lleva su `annotation_rule` para que la metodología sea auditable.

| Tipo de regla | Significado | Queries que la usan |
|---|---|---|
| `id=X` | Coincidencia exacta de id. | q01-q03 |
| `country=X` | Todos los destinos con `country == X`. | q04-q08, q19-q21 |
| `keyword=X` | Descripción contiene la palabra completa `X` (case-insensitive). | q09-q11, q14-q15, q18 |
| `keyword_any=X1,X2` | Cualquiera de las palabras aparece en la descripción. | q12, q13 |
| `keyword_in_country=X\|C` | Palabra `X` en la descripción **y** `country == C`. | q16, q17, q22 |

### Reproducibilidad

El JSON se genera con `python scripts/build_eval_queries.py`. El script lee `data/processed/destinations.jsonl`, aplica cada regla y escribe el JSON. Hay que regenerarlo cada vez que cambie el corpus para mantener el ground truth consistente:

```bash
python scripts/build_eval_queries.py
```

Si una regla deja la lista de relevantes vacía, el script falla con `exit 1` y lista las queries problemáticas para que se ajusten antes de versionar.

### Composición del conjunto

| Categoría | Queries | Total relevantes (suma) |
|---|---|---|
| Match por id exacto | 3 | 3 |
| Match por país | 9 | 152 |
| Match por keyword en descripción | 6 | 75 |
| Match combinado (keyword + país) | 3 | 10 |
| Match por keyword en cualquiera de varios | 2 | 85 |

Las queries por país son intencionalmente "fáciles" — sirven como sanity check del recuperador léxico. Las queries por keyword son más representativas de un uso real porque exigen entender el contenido (el modo semántico debería superar al booleano en esas).

### Estado de validación

El campo `review_status: "pending_human_validation"` señala que las anotaciones se generaron algorítmicamente y deberían revisarse a mano antes de la defensa final. Editar `data/eval/queries.json` directamente es seguro; el script se re-ejecuta solo cuando se quiere regenerar todo desde reglas.

### Limitaciones declaradas

- El corpus es **mono-idioma inglés** (Wikivoyage). Las queries en español funcionan porque los modos semántico y híbrido usan un embedder multilingüe (`all-MiniLM-L6-v2`), pero el modo booleano tiene desventaja inherente con queries en español.
- Las reglas de keyword usan **whole-word matching** (`\bbeach\b`), no stemming. Esto se hace porque el ground truth debe ser literalmente verificable; el recuperador es el que aplica stemming.
- No hay queries adversariales (típos, sinónimos exóticos, dominios fuera de turismo). Se podrían añadir como segunda iteración.

---

## T106 — Precision@k, Recall@k, F1@k

`src/evaluation/metrics.py` define los tres clásicos por consulta.

### Definiciones

| Métrica | Fórmula | Interpretación |
|---|---|---|
| **Precision@k** | $\frac{\|\{ \text{relevantes} \cap \text{top-}k \}\|}{k}$ | Fracción del top-k que es relevante. Si pides 10 y 3 son útiles, P@10 = 0.30. |
| **Recall@k** | $\frac{\|\{ \text{relevantes} \cap \text{top-}k \}\|}{\|\text{relevantes}\|}$ | Fracción de los relevantes que se recuperaron. |
| **F1@k** | $\frac{2 \cdot P \cdot R}{P + R}$ | Media armónica; 0 cuando no hay aciertos. |

### Convenciones de borde

- **k fijo aunque la lista sea corta**: si el recuperador devuelve solo 2 documentos pero el usuario pidió k=5, el denominador de P@5 sigue siendo 5. Eso penaliza correctamente la sub-entrega.
- **Sin relevantes → 0.0**: si una query tiene ground truth vacío, las tres métricas devuelven 0.0 en lugar de NaN o excepción para que la media sobre el batch siga siendo calculable.
- **k inválido → excepción**: `k <= 0` o no-entero hacen fallar la llamada inmediatamente. Mejor un error claro que un cálculo silenciosamente roto.



---

## T107 — MAP, MRR y nDCG

### Average Precision y MAP

$$
\mathrm{AP} = \frac{1}{|\text{relevantes}|} \sum_{k \in \text{ranks de hits}} \mathrm{Precision@}k
$$

Y `MAP = mean(AP_q)` para `q` en el set de evaluación. **AP penaliza relevantes no recuperados**: si tienes dos relevantes y solo encuentras uno, AP queda acotado por 0.5 incluso si el hit está en el rango 1.

### Reciprocal Rank y MRR

$$
\mathrm{RR} = \frac{1}{\text{rango del primer hit}}, \quad \mathrm{MRR} = \frac{1}{Q} \sum_{q=1}^{Q} \mathrm{RR}_q
$$

Útil cuando importa "¿qué tan rápido aparece la primera respuesta correcta?" más que el ranking completo. Por construcción RR cae a 0 cuando ningún relevante está en la lista.

### DCG y nDCG

$$
\mathrm{DCG@}k = \sum_{i=1}^{k} \frac{\mathrm{gain}(i)}{\log_2(i+1)}
$$

$$
\mathrm{nDCG@}k = \frac{\mathrm{DCG@}k}{\mathrm{iDCG@}k}
$$

Donde iDCG@k es el DCG del ranking ideal (todos los relevantes lo antes posible). Soporta dos modos:

- **Binario** (default): gain en {0, 1} según si el documento está en `relevant` o no. Es lo que usa nuestra evaluación porque las anotaciones son binarias.
- **Graded** (`binary=False`): si pasas `relevant` como dict `id -> score`, la métrica usa los scores graduados. Lo dejamos disponible para futuras anotaciones con escala 0-3 al estilo TREC.

### Por qué tantas métricas

Ninguna métrica sola dice si un recuperador funciona:

- **Precision@k** mide la calidad del top visible para el usuario.
- **Recall@k** mide si encontramos todo lo importante.
- **MAP** combina precisión con cobertura sobre todos los relevantes.
- **MRR** premia tener el primer hit arriba (útil en "feeling lucky").
- **nDCG** discounta hits que llegan tarde (un relevante en el rango 1 vale más que uno en el rango 10).

Reportar las cinco juntas hace explícitos los trade-offs de cada modo del recuperador (Booleano vs semántico vs híbrido).

---

## T108 — Script de evaluación

`python -m src.cli evaluate` corre las queries del conjunto contra cada modo y produce una tabla comparativa.

### Uso

```bash
# Default: corre los tres modos con top-k=10, p=2.0, alpha=0.5
python -m src.cli evaluate

# Solo Booleano (no requiere Qdrant)
python -m src.cli evaluate --modes boolean --top-k 10

# Con p e híbrido específicos
python -m src.cli evaluate --top-k 5 --p 3.0 --alpha 0.6

# Volcar reporte completo (incluye per-query) a JSON
python -m src.cli evaluate --output data/eval/report.json
```

### Salida

Por stdout imprime una tabla con seis métricas por modo:

```
Reporte de evaluación — top_k=10, queries=22
========================================================================
mode      P@k      R@k     F1@k     MAP      MRR     nDCG@k   available
boolean   0.1136   0.2717  0.1152   0.2214   0.3614  0.2883   True
semantic  -        -       -        -        -       -        False (...)
hybrid    -        -       -        -        -       -        False (...)
```

Con `--output` se guarda un JSON con la misma información agregada **más** el detalle por query (`retrieved`, `P@k`, `R@k`, `AP`, `RR`, `nDCG@k` y la query textual), útil para análisis de errores en cuadros aparte.

### Degradación elegante

Si Qdrant no responde o el embedder no puede materializarse, ese modo se marca como `available=False` con el error completo en la columna y los demás modos siguen ejecutándose. Esto permite producir una tabla útil aunque solo el modo léxico esté operativo (caso típico en CI o en una demo offline).

### Componentes

| Archivo | Responsabilidad |
|---|---|
| `src/evaluation/runner.py` | Orquesta la ejecución por modo y agrega métricas. Acepta cualquier `retriever_fn: (query, top_k) -> list[str]`, por lo que es independiente del recuperador concreto. |
| `src/evaluation/retrievers.py` | Adaptadores que envuelven el código de producción (Booleano Extendido, semántico, híbrido) en la forma `RetrieverFn`. |
| `src/evaluation/metrics.py` | Funciones puras de T106 y T107. |
| `src/cli.py::evaluate_cmd` | Punto de entrada de Typer: parsea flags, construye retrievers, imprime tabla y persiste JSON. |

### Resultado de referencia (modo Booleano, 2026-05-11)

Sobre el corpus actual (206 destinos, índice TF-IDF):

| Métrica | Valor |
|---|---|
| P@10 | 0.1136 |
| R@10 | 0.2717 |
| F1@10 | 0.1152 |
| MAP | 0.2214 |
| MRR | 0.3614 |
| nDCG@10 | 0.2883 |

Los valores bajos en P@k vs R@k son esperables porque varias queries por país (`country=Spain` → 48 relevantes) tienen ground truth mucho mayor que el `top_k=10` del runner. El nDCG por encima del 0.28 confirma que cuando el booleano acierta, los aciertos aparecen razonablemente arriba (rangos cercanos a 1-3). Estos números se compararán contra los modos semántico/híbrido en cuanto Qdrant esté materializado.

