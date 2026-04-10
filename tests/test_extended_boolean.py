"""T032/T033/T034/T036/T037 — Modelo Booleano Extendido (p-norm)."""
import math

import pytest

from src.retrieval.extended_boolean import ExtendedBoolean

# ── Constructor ───────────────────────────────────────────────────────────────

def test_default_p_value():
    eb = ExtendedBoolean()
    assert eb.p == 2.0


def test_custom_p_value():
    eb = ExtendedBoolean(p=5.0)
    assert eb.p == 5.0


def test_p_must_be_positive():
    with pytest.raises(ValueError):
        ExtendedBoolean(p=0.0)


def test_p_must_be_greater_than_zero():
    with pytest.raises(ValueError):
        ExtendedBoolean(p=-1.0)


# ── score stub ────────────────────────────────────────────────────────────────

def test_score_returns_zero_stub():
    """score() sigue siendo stub hasta T035/T036 (parser + evaluador AST)."""
    eb = ExtendedBoolean(p=2.0)
    assert eb.score("turismo AND playa", "doc1") == 0.0


def test_score_return_type_is_float():
    eb = ExtendedBoolean(p=2.0)
    result = eb.score("turismo", "doc1")
    assert isinstance(result, float)


# ── T033: OR p-norm ───────────────────────────────────────────────────────────

def test_or_norm_empty_weights_returns_zero():
    eb = ExtendedBoolean(p=2.0)
    assert eb.or_norm([]) == 0.0


def test_or_norm_single_full_match():
    """Un único término con peso 1 → similitud 1.0 (sin importar p)."""
    for p in (1.0, 2.0, 5.0):
        eb = ExtendedBoolean(p=p)
        assert eb.or_norm([1.0]) == pytest.approx(1.0)


def test_or_norm_single_no_match():
    """Un único término con peso 0 → similitud 0.0."""
    for p in (1.0, 2.0, 5.0):
        eb = ExtendedBoolean(p=p)
        assert eb.or_norm([0.0]) == pytest.approx(0.0)


def test_or_norm_p1_equals_arithmetic_mean():
    """p=1: la fórmula colapsa a la media aritmética de los pesos."""
    eb = ExtendedBoolean(p=1.0)
    assert eb.or_norm([0.5, 0.5]) == pytest.approx(0.5)
    assert eb.or_norm([0.4, 0.6]) == pytest.approx(0.5)
    assert eb.or_norm([0.2, 0.4, 0.6]) == pytest.approx(0.4)


def test_or_norm_all_ones_any_p():
    """Todos los pesos = 1 → similitud 1.0 para cualquier p."""
    for p in (1.0, 2.0, 10.0):
        eb = ExtendedBoolean(p=p)
        assert eb.or_norm([1.0, 1.0, 1.0]) == pytest.approx(1.0)


def test_or_norm_p2_example_from_paper():
    """Ejemplo numérico (Salton et al., 1983): p=2, w=[0.6, 0.8].

    sim_or = sqrt((0.6² + 0.8²) / 2) = sqrt((0.36 + 0.64) / 2) = sqrt(0.5) ≈ 0.7071
    """
    eb = ExtendedBoolean(p=2.0)
    expected = math.sqrt((0.6**2 + 0.8**2) / 2)
    assert eb.or_norm([0.6, 0.8]) == pytest.approx(expected, rel=1e-6)


def test_or_norm_large_p_approaches_max():
    """p→∞: sim_or → max(weights) (Booleano puro: basta que un término ocurra)."""
    eb = ExtendedBoolean(p=1000.0)
    weights = [0.3, 0.9, 0.1]
    result = eb.or_norm(weights)
    # Con p finito la convergencia es gradual; tolerancia del 2 %
    assert result == pytest.approx(max(weights), rel=2e-2)


def test_or_norm_symmetric():
    """El orden de los pesos no altera el resultado."""
    eb = ExtendedBoolean(p=2.0)
    assert eb.or_norm([0.3, 0.7]) == pytest.approx(eb.or_norm([0.7, 0.3]))


def test_or_norm_return_type_is_float():
    eb = ExtendedBoolean(p=2.0)
    assert isinstance(eb.or_norm([0.5, 0.5]), float)


# ── T034: AND p-norm ──────────────────────────────────────────────────────────

def test_and_norm_empty_weights_returns_zero():
    eb = ExtendedBoolean(p=2.0)
    assert eb.and_norm([]) == 0.0


def test_and_norm_all_full_match():
    """Todos los pesos = 1 → similitud 1.0 (todos los términos presentes)."""
    for p in (1.0, 2.0, 5.0):
        eb = ExtendedBoolean(p=p)
        assert eb.and_norm([1.0, 1.0, 1.0]) == pytest.approx(1.0)


def test_and_norm_single_no_match():
    """Un único término con peso 0 → similitud 0.0."""
    for p in (1.0, 2.0, 5.0):
        eb = ExtendedBoolean(p=p)
        assert eb.and_norm([0.0]) == pytest.approx(0.0)


def test_and_norm_p1_equals_arithmetic_mean():
    """p=1: AND colapsa a la media aritmética (igual que OR con p=1)."""
    eb = ExtendedBoolean(p=1.0)
    assert eb.and_norm([0.5, 0.5]) == pytest.approx(0.5)
    assert eb.and_norm([0.4, 0.6]) == pytest.approx(0.5)
    assert eb.and_norm([0.2, 0.4, 0.6]) == pytest.approx(0.4)


def test_and_norm_p2_example_from_paper():
    """Ejemplo numérico (Salton et al., 1983): p=2, w=[0.6, 0.8].

    sim_and = 1 - sqrt(((1-0.6)² + (1-0.8)²) / 2)
             = 1 - sqrt((0.16 + 0.04) / 2)
             = 1 - sqrt(0.1) ≈ 0.6838
    """
    eb = ExtendedBoolean(p=2.0)
    expected = 1.0 - math.sqrt(((1 - 0.6) ** 2 + (1 - 0.8) ** 2) / 2)
    assert eb.and_norm([0.6, 0.8]) == pytest.approx(expected, rel=1e-6)


def test_and_norm_large_p_approaches_min():
    """p→∞: sim_and → min(weights) (Booleano puro: todos deben ocurrir)."""
    eb = ExtendedBoolean(p=1000.0)
    weights = [0.9, 0.3, 0.7]
    result = eb.and_norm(weights)
    # Con p finito la convergencia es gradual; tolerancia del 2 %
    assert result == pytest.approx(min(weights), rel=2e-2)


def test_and_norm_symmetric():
    """El orden de los pesos no altera el resultado."""
    eb = ExtendedBoolean(p=2.0)
    assert eb.and_norm([0.3, 0.7]) == pytest.approx(eb.and_norm([0.7, 0.3]))


def test_and_norm_leq_or_norm():
    """AND siempre es ≤ OR para los mismos pesos y p (el AND es más exigente)."""
    eb = ExtendedBoolean(p=2.0)
    weights = [0.4, 0.9, 0.6]
    assert eb.and_norm(weights) <= eb.or_norm(weights)


def test_and_norm_return_type_is_float():
    eb = ExtendedBoolean(p=2.0)
    assert isinstance(eb.and_norm([0.5, 0.5]), float)


# ── T036: evaluate ────────────────────────────────────────────────────────────

def test_evaluate_term_node_present():
    """TermNode: devuelve el peso del término en doc_weights."""
    from src.retrieval.query_parser import TermNode

    eb = ExtendedBoolean(p=2.0)
    node = TermNode(term="beach")
    assert eb.evaluate(node, {"beach": 0.7}) == pytest.approx(0.7)


def test_evaluate_term_node_absent():
    """TermNode: término ausente → 0.0."""
    from src.retrieval.query_parser import TermNode

    eb = ExtendedBoolean(p=2.0)
    node = TermNode(term="mountain")
    assert eb.evaluate(node, {"beach": 0.7}) == pytest.approx(0.0)


def test_evaluate_and_node():
    """AndNode: aplica and_norm sobre los pesos de los hijos."""
    import math

    from src.retrieval.query_parser import AndNode, TermNode

    eb = ExtendedBoolean(p=2.0)
    node = AndNode(children=[TermNode("beach"), TermNode("tourism")])
    doc_weights = {"beach": 0.6, "tourism": 0.8}
    expected = 1.0 - math.sqrt(((1 - 0.6) ** 2 + (1 - 0.8) ** 2) / 2)
    assert eb.evaluate(node, doc_weights) == pytest.approx(expected, rel=1e-6)


def test_evaluate_or_node():
    """OrNode: aplica or_norm sobre los pesos de los hijos."""
    import math

    from src.retrieval.query_parser import OrNode, TermNode

    eb = ExtendedBoolean(p=2.0)
    node = OrNode(children=[TermNode("beach"), TermNode("mountain")])
    doc_weights = {"beach": 0.6, "mountain": 0.8}
    expected = math.sqrt((0.6 ** 2 + 0.8 ** 2) / 2)
    assert eb.evaluate(node, doc_weights) == pytest.approx(expected, rel=1e-6)


def test_evaluate_nested_ast():
    """Árbol mixto: OR(AND(beach, tourism), mountain) con p=2."""
    import math

    from src.retrieval.query_parser import AndNode, OrNode, TermNode

    eb = ExtendedBoolean(p=2.0)
    # OR(AND(beach, tourism), mountain)
    ast = OrNode(children=[
        AndNode(children=[TermNode("beach"), TermNode("tourism")]),
        TermNode("mountain"),
    ])
    doc_weights = {"beach": 0.6, "tourism": 0.8, "mountain": 0.5}

    and_score = 1.0 - math.sqrt(((1 - 0.6) ** 2 + (1 - 0.8) ** 2) / 2)
    mountain_score = 0.5
    expected = math.sqrt((and_score ** 2 + mountain_score ** 2) / 2)
    assert eb.evaluate(ast, doc_weights) == pytest.approx(expected, rel=1e-6)


def test_evaluate_absent_term_in_and_penalizes():
    """Un término ausente en un AND baja la similitud respecto al caso presente."""
    from src.retrieval.query_parser import AndNode, TermNode

    eb = ExtendedBoolean(p=2.0)
    node = AndNode(children=[TermNode("beach"), TermNode("tourism")])
    full = eb.evaluate(node, {"beach": 1.0, "tourism": 1.0})
    partial = eb.evaluate(node, {"beach": 1.0, "tourism": 0.0})
    assert partial < full


def test_evaluate_returns_float():
    from src.retrieval.query_parser import TermNode

    eb = ExtendedBoolean(p=2.0)
    result = eb.evaluate(TermNode("beach"), {"beach": 0.5})
    assert isinstance(result, float)


# ── T037: search ──────────────────────────────────────────────────────────────

def _build_index(docs: dict[str, list[str]]):
    """Construye un InvertedIndex ya con TF-IDF calculado a partir de docs."""
    from src.indexing.inverted_index import InvertedIndex

    idx = InvertedIndex()
    for doc_id, tokens in docs.items():
        idx.add_document(doc_id, tokens)
    idx.compute_tf_idf()
    return idx


def test_search_returns_list():
    idx = _build_index({"d1": ["beach", "tourism"], "d2": ["mountain", "hiking"]})
    eb = ExtendedBoolean(p=2.0)
    result = eb.search("beach", idx, top_k=5)
    assert isinstance(result, list)


def test_search_result_tuples():
    idx = _build_index({"d1": ["beach", "tourism"], "d2": ["mountain"]})
    eb = ExtendedBoolean(p=2.0)
    result = eb.search("beach", idx, top_k=5)
    for item in result:
        assert isinstance(item, tuple)
        assert len(item) == 2
        assert isinstance(item[0], str)
        assert isinstance(item[1], float)


def test_search_top_k_limits_results():
    docs = {f"d{i}": ["beach"] for i in range(10)}
    idx = _build_index(docs)
    eb = ExtendedBoolean(p=2.0)
    result = eb.search("beach", idx, top_k=3)
    assert len(result) <= 3


def test_search_ordered_by_score_descending():
    idx = _build_index({
        "d1": ["beach", "beach", "beach", "tourism"],
        "d2": ["beach"],
        "d3": ["mountain"],
    })
    eb = ExtendedBoolean(p=2.0)
    result = eb.search("beach", idx, top_k=10)
    scores = [s for _, s in result]
    assert scores == sorted(scores, reverse=True)


def test_search_relevant_doc_ranked_higher():
    """Doc con más ocurrencias del término buscado debe puntuar más alto."""
    idx = _build_index({
        "relevant": ["beach", "beach", "beach", "tourism"],
        "irrelevant": ["mountain", "hiking", "forest"],
    })
    eb = ExtendedBoolean(p=2.0)
    result = eb.search("beach", idx, top_k=10)
    doc_ids = [doc_id for doc_id, _ in result]
    assert doc_ids[0] == "relevant"


def test_search_and_query():
    """AND: docs que contengan ambos términos puntúan más alto."""
    idx = _build_index({
        "both": ["beach", "tourism", "beach"],
        "only_beach": ["beach", "beach"],
        "only_tourism": ["tourism", "tourism"],
    })
    eb = ExtendedBoolean(p=2.0)
    result = eb.search("beach AND tourism", idx, top_k=10)
    doc_ids = [doc_id for doc_id, _ in result]
    assert doc_ids[0] == "both"


def test_search_no_match_returns_empty():
    idx = _build_index({"d1": ["mountain", "hiking"]})
    eb = ExtendedBoolean(p=2.0)
    result = eb.search("beach", idx, top_k=10)
    assert result == []


def test_search_scores_in_unit_interval():
    idx = _build_index({
        "d1": ["beach", "tourism"],
        "d2": ["beach", "mountain", "beach"],
    })
    eb = ExtendedBoolean(p=2.0)
    result = eb.search("beach OR tourism", idx, top_k=10)
    for _, score in result:
        assert 0.0 <= score <= 1.0
