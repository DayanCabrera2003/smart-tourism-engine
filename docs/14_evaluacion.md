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


