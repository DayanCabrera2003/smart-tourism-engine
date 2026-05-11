"""T119 - Expand a user query with semantically similar terms.

The Boolean Extended retriever (T031-T038) only matches the exact
tokens it has in the inverted index. A user typing ``playa`` will not
match Spanish-speaking corpora because the index lemma is ``beach``.
T119 closes that gap by expanding each query term with its top-N most
similar terms in the embedding space.

We deliberately keep the vocabulary expansion **offline and local**:
the embedder loads each candidate term, computes cosine similarity to
the query term and returns the top-N. The candidate vocabulary is
whatever the caller supplies (typically the vocabulary of the inverted
index, so the expansion is guaranteed to add only terms the retriever
already knows).

The module exposes one entry point ``expand_query`` that returns a
plain string with the original query plus the new terms appended
behind ``OR`` connectors. That string can be fed straight back into
``ExtendedBoolean.search`` or any other retriever that consumes
queries with ``AND/OR`` operators.
"""
from __future__ import annotations

import math
from typing import Iterable, Optional, Protocol

__all__ = [
    "DEFAULT_MAX_EXPANSIONS_PER_TERM",
    "DEFAULT_SIMILARITY_THRESHOLD",
    "expand_query",
    "similar_terms",
]


DEFAULT_MAX_EXPANSIONS_PER_TERM = 2
DEFAULT_SIMILARITY_THRESHOLD = 0.55


class _Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        raise ValueError(f"Dimension mismatch: {len(a)} vs {len(b)}")
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


_BOOLEAN_OPERATORS = frozenset({"AND", "OR", "NOT", "(", ")"})


def _split_terms(query: str) -> list[str]:
    """Tokenize ``query`` keeping operators intact.

    Boolean operators (uppercase) and parentheses are preserved so
    callers can fold the expansion back into the original boolean
    structure. Lowercase tokens are treated as terms to expand.
    """
    tokens: list[str] = []
    buffer: list[str] = []
    for char in query:
        if char.isspace() or char in "()":
            if buffer:
                tokens.append("".join(buffer))
                buffer = []
            if char in "()":
                tokens.append(char)
        else:
            buffer.append(char)
    if buffer:
        tokens.append("".join(buffer))
    return tokens


def similar_terms(
    term: str,
    vocabulary: Iterable[str],
    embedder: _Embedder,
    *,
    max_terms: int = DEFAULT_MAX_EXPANSIONS_PER_TERM,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    term_embeddings: Optional[dict[str, list[float]]] = None,
) -> list[tuple[str, float]]:
    """Return up to ``max_terms`` neighbours of ``term`` in ``vocabulary``.

    Each result is a ``(candidate, similarity)`` tuple sorted by
    similarity descending. Candidates whose similarity is below
    ``threshold`` are dropped — the threshold is calibrated against
    sentence-transformers (`all-MiniLM-L6-v2`) where 0.55 is a
    conservative starting point.

    ``term_embeddings`` is an optional precomputed cache so callers
    can avoid embedding the entire vocabulary on every query.
    """
    if max_terms <= 0:
        return []
    target = embedder.embed(term)
    cache = dict(term_embeddings or {})
    scores: list[tuple[str, float]] = []
    for candidate in vocabulary:
        if candidate == term:
            continue
        if candidate not in cache:
            cache[candidate] = embedder.embed(candidate)
        sim = _cosine(target, cache[candidate])
        if sim >= threshold:
            scores.append((candidate, sim))
    scores.sort(key=lambda pair: pair[1], reverse=True)
    return scores[:max_terms]


def expand_query(
    query: str,
    vocabulary: Iterable[str],
    embedder: _Embedder,
    *,
    max_terms_per_word: int = DEFAULT_MAX_EXPANSIONS_PER_TERM,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    term_embeddings: Optional[dict[str, list[float]]] = None,
) -> str:
    """Expand each non-operator token of ``query`` with its neighbours.

    Operators (AND, OR, NOT) and parentheses are preserved verbatim.
    Every other token is replaced by ``(term OR neighbour1 OR
    neighbour2 ...)`` when at least one neighbour passes the
    similarity threshold; otherwise the original token is kept.

    The output is always a syntactically valid input for
    ``ExtendedBoolean.search`` so callers do not need to know whether
    the expansion fired or not.
    """
    vocab_list = list(vocabulary)
    tokens = _split_terms(query)
    expanded: list[str] = []
    for token in tokens:
        if token in _BOOLEAN_OPERATORS:
            expanded.append(token)
            continue
        neighbours = similar_terms(
            token,
            vocab_list,
            embedder,
            max_terms=max_terms_per_word,
            threshold=threshold,
            term_embeddings=term_embeddings,
        )
        if not neighbours:
            expanded.append(token)
            continue
        clause = " OR ".join([token, *(c for c, _ in neighbours)])
        expanded.append(f"({clause})")
    return " ".join(expanded)
