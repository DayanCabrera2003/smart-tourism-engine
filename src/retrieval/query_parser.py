"""T035 — Parser de queries para el Modelo Booleano Extendido (p-norm).

Convierte una consulta textual con operadores AND/OR a un árbol AST que
`ExtendedBoolean.evaluate` (T036) recorre aplicando las fórmulas p-norm.

Gramática soportada (precedencia AND > OR):
    expr      → and_expr (OR and_expr)*
    and_expr  → TERM (AND TERM)*
    TERM      → cualquier token que no sea AND/OR

Los términos se preprocesan (tokenize → stopwords → stem) al parsear,
garantizando coherencia con el índice invertido.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.indexing.preprocess import preprocess

__all__ = ["AndNode", "Node", "OrNode", "TermNode", "parse_query"]

_AND = "AND"
_OR = "OR"
_OPERATORS = {_AND, _OR}


# ── Nodos del AST ─────────────────────────────────────────────────────────────

@dataclass
class TermNode:
    """Hoja del AST: un término ya preprocesado (stem)."""

    term: str


@dataclass
class AndNode:
    """Nodo AND: todos los hijos deben ocurrir (p-norm AND)."""

    children: list[Node] = field(default_factory=list)


@dataclass
class OrNode:
    """Nodo OR: basta que algún hijo ocurra (p-norm OR)."""

    children: list[Node] = field(default_factory=list)


Node = TermNode | AndNode | OrNode


# ── Parser ────────────────────────────────────────────────────────────────────

def parse_query(query: str) -> Node:
    """Parsea una consulta con AND/OR y devuelve el árbol AST.

    Precedencia: AND se evalúa antes que OR.
    Los términos se preprocesan (stem) para coincidir con el índice.

    Args:
        query: Consulta textual, por ejemplo ``"playa AND tranquilo OR montaña"``.

    Returns:
        Árbol AST: ``TermNode`` para consultas de un término, ``AndNode`` /
        ``OrNode`` para consultas compuestas.

    Raises:
        ValueError: Si la consulta está vacía o sólo contiene operadores.
    """
    query = query.strip()
    if not query:
        raise ValueError("La consulta no puede estar vacía.")

    tokens = query.split()
    and_groups = _split_by_or(tokens)

    or_children: list[Node] = []
    for group in and_groups:
        node = _parse_and_group(group)
        if node is not None:
            or_children.append(node)

    if not or_children:
        raise ValueError(f"La consulta no contiene términos válidos: {query!r}")

    return or_children[0] if len(or_children) == 1 else OrNode(children=or_children)


# ── Helpers internos ──────────────────────────────────────────────────────────

def _split_by_or(tokens: list[str]) -> list[list[str]]:
    """Divide la lista de tokens en grupos separados por OR."""
    groups: list[list[str]] = []
    current: list[str] = []
    for tok in tokens:
        if tok == _OR:
            groups.append(current)
            current = []
        else:
            current.append(tok)
    groups.append(current)
    return groups


def _parse_and_group(tokens: list[str]) -> Node | None:
    """Parsea un grupo AND: ``term1 AND term2 AND term3``."""
    # Filtrar el token "AND" y obtener los términos
    raw_terms = [tok for tok in tokens if tok != _AND]
    stems: list[str] = []
    for raw in raw_terms:
        if raw in _OPERATORS:
            continue
        processed = preprocess(raw, language="english")
        stems.extend(processed)

    if not stems:
        return None

    term_nodes: list[Node] = [TermNode(term=s) for s in stems]
    return term_nodes[0] if len(term_nodes) == 1 else AndNode(children=term_nodes)
