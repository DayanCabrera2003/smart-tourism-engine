"""T035 — Tests del parser de queries para el Modelo Booleano Extendido."""
import pytest

from src.retrieval.query_parser import AndNode, OrNode, TermNode, parse_query

# ── Consultas de un solo término ──────────────────────────────────────────────

def test_single_term_returns_term_node():
    node = parse_query("beach")
    assert isinstance(node, TermNode)


def test_single_term_is_stemmed():
    """El término se preprocesa (stem): 'beaches' → 'beach'."""
    node = parse_query("beaches")
    assert isinstance(node, TermNode)
    assert node.term == "beach"


def test_single_term_case_insensitive():
    node = parse_query("Beach")
    assert isinstance(node, TermNode)
    assert node.term == "beach"


# ── Consultas AND ─────────────────────────────────────────────────────────────

def test_and_two_terms_returns_and_node():
    node = parse_query("beach AND tourism")
    assert isinstance(node, AndNode)
    assert len(node.children) == 2


def test_and_children_are_term_nodes():
    node = parse_query("beach AND tourism")
    assert isinstance(node, AndNode)
    for child in node.children:
        assert isinstance(child, TermNode)


def test_and_three_terms():
    node = parse_query("playa AND tranquilo AND montaña")
    assert isinstance(node, AndNode)
    assert len(node.children) == 3


def test_and_terms_are_stemmed():
    node = parse_query("beaches AND mountains")
    assert isinstance(node, AndNode)
    terms = [c.term for c in node.children]
    assert "beach" in terms
    assert "mountain" in terms


# ── Consultas OR ──────────────────────────────────────────────────────────────

def test_or_two_terms_returns_or_node():
    node = parse_query("beach OR mountain")
    assert isinstance(node, OrNode)
    assert len(node.children) == 2


def test_or_children_are_term_nodes():
    node = parse_query("beach OR mountain")
    assert isinstance(node, OrNode)
    for child in node.children:
        assert isinstance(child, TermNode)


def test_or_three_terms():
    node = parse_query("playa OR montaña OR ciudad")
    assert isinstance(node, OrNode)
    assert len(node.children) == 3


# ── Consultas mixtas (AND > OR) ───────────────────────────────────────────────

def test_and_or_precedence():
    """'playa AND tranquilo OR montaña' → OR(AND(playa, tranquilo), montaña)."""
    node = parse_query("playa AND tranquilo OR montaña")
    assert isinstance(node, OrNode)
    assert len(node.children) == 2
    assert isinstance(node.children[0], AndNode)
    assert isinstance(node.children[1], TermNode)


def test_or_and_precedence():
    """'playa OR tranquilo AND montaña' → OR(playa, AND(tranquilo, montaña))."""
    node = parse_query("playa OR tranquilo AND montaña")
    assert isinstance(node, OrNode)
    assert len(node.children) == 2
    assert isinstance(node.children[0], TermNode)
    assert isinstance(node.children[1], AndNode)


def test_mixed_three_groups():
    """'a AND b OR c AND d OR e' → OR(AND(a,b), AND(c,d), e)."""
    node = parse_query("beach AND tourism OR mountain AND hiking OR city")
    assert isinstance(node, OrNode)
    assert len(node.children) == 3
    assert isinstance(node.children[0], AndNode)
    assert isinstance(node.children[1], AndNode)
    assert isinstance(node.children[2], TermNode)


# ── Casos de error ────────────────────────────────────────────────────────────

def test_empty_query_raises():
    with pytest.raises(ValueError):
        parse_query("")


def test_whitespace_only_raises():
    with pytest.raises(ValueError):
        parse_query("   ")


def test_only_operators_raises():
    with pytest.raises(ValueError):
        parse_query("AND OR")


# ── Robustez: stopwords y términos vacíos ─────────────────────────────────────

def test_stopword_only_term_in_and_raises():
    """Un término que es stopword se elimina en preprocesamiento."""
    # 'the' es stopword, 'beach' no → el AND colapsa a TermNode
    node = parse_query("the AND beach")
    # 'the' se elimina → queda sólo 'beach'
    assert isinstance(node, TermNode)
    assert node.term == "beach"
