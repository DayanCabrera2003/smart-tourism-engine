"""T031 — Modelo Booleano clásico con soporte AND, OR, NOT."""
from src.indexing.inverted_index import InvertedIndex
from src.indexing.preprocess import preprocess

__all__ = ["boolean_query"]

# Operadores reconocidos (case-sensitive en la query)
_AND = "AND"
_OR = "OR"
_NOT = "NOT"
_OPERATORS = {_AND, _OR, _NOT}


def boolean_query(query: str, index: InvertedIndex) -> list[str]:
    """
    Evalúa una consulta booleana clásica sobre el índice invertido.

    Sintaxis soportada (operadores en mayúsculas):
        term
        term1 AND term2 [AND term3 ...]
        term1 OR  term2 [OR  term3 ...]
        NOT term
        term1 AND NOT term2

    Los términos de la consulta pasan por el mismo pipeline de preprocesamiento
    (tokenize → stopwords → stem) que los documentos indexados.

    Args:
        query: Consulta en lenguaje natural con operadores AND/OR/NOT.
        index: Índice invertido ya construido.

    Returns:
        Lista de doc_id ordenada que satisface la consulta.
        Lista vacía si no hay coincidencias o la query es vacía.
    """
    query = query.strip()
    if not query:
        return []

    tokens = query.split()
    return sorted(_evaluate(tokens, index))


# ── Parser / evaluador ────────────────────────────────────────────────────────

def _docs_for_term(term: str, index: InvertedIndex) -> set[str]:
    """Preprocesa un término y devuelve el conjunto de doc_ids que lo contienen."""
    stems = preprocess(term, language="english")
    if not stems:
        return set()
    result: set[str] = set(doc_id for doc_id, _ in index.get_postings(stems[0]))
    for stem in stems[1:]:
        result &= set(doc_id for doc_id, _ in index.get_postings(stem))
    return result


def _all_docs(index: InvertedIndex) -> set[str]:
    """Conjunto de todos los doc_ids del índice."""
    all_ids: set[str] = set()
    for term in index.vocabulary:
        all_ids.update(doc_id for doc_id, _ in index.get_postings(term))
    return all_ids


def _evaluate(tokens: list[str], index: InvertedIndex) -> set[str]:
    """
    Evalúa la lista de tokens con precedencia: NOT > AND > OR.

    La expresión se parsea en dos pasadas:
        1. Agrupar cláusulas AND (incluyendo AND NOT).
        2. Unir cláusulas con OR.
    """
    if not tokens:
        return set()

    # Paso 1: dividir en cláusulas OR
    or_clauses: list[list[str]] = []
    current: list[str] = []
    for tok in tokens:
        if tok == _OR:
            or_clauses.append(current)
            current = []
        else:
            current.append(tok)
    or_clauses.append(current)

    # Paso 2: evaluar cada cláusula AND y unir resultados
    result: set[str] = set()
    for clause in or_clauses:
        result |= _eval_and_clause(clause, index)
    return result


def _eval_and_clause(tokens: list[str], index: InvertedIndex) -> set[str]:
    """
    Evalúa una cláusula AND: ``t1 AND t2 AND NOT t3 ...``
    El primer token puede ser NOT (NOT t1).
    """
    if not tokens:
        return set()

    # Analizar posición inicial: puede ser NOT term o term
    pos = 0
    negate_first = False
    if tokens[pos] == _NOT:
        negate_first = True
        pos += 1

    if pos >= len(tokens) or tokens[pos] in _OPERATORS:
        return set()

    base = _docs_for_term(tokens[pos], index)
    if negate_first:
        base = _all_docs(index) - base
    pos += 1

    # Procesar pares: AND [NOT] term
    while pos < len(tokens):
        op = tokens[pos]
        if op != _AND:
            break
        pos += 1

        negate = False
        if pos < len(tokens) and tokens[pos] == _NOT:
            negate = True
            pos += 1

        if pos >= len(tokens) or tokens[pos] in _OPERATORS:
            break

        operand = _docs_for_term(tokens[pos], index)
        if negate:
            base -= operand
        else:
            base &= operand
        pos += 1

    return base
