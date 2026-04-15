from __future__ import annotations

import math

from src.indexing.embedder import TextEmbedder


class _StubModel:
    """Modelo falso que imita la API de SentenceTransformer para tests."""

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension
        self.calls: list[tuple[str, bool]] = []

    def encode(self, text: str, normalize_embeddings: bool = False):
        self.calls.append((text, normalize_embeddings))
        length = len(text) or 1
        raw = [((i + 1) * length) % 7 + 0.5 for i in range(self.dimension)]
        if normalize_embeddings:
            norm = math.sqrt(sum(v * v for v in raw))
            raw = [v / norm for v in raw]
        return raw


def test_embed_returns_list_of_floats_with_expected_dimension() -> None:
    stub = _StubModel(dimension=TextEmbedder.DIMENSION)
    embedder = TextEmbedder(model=stub)

    vector = embedder.embed("Madrid es la capital de España")

    assert isinstance(vector, list)
    assert len(vector) == TextEmbedder.DIMENSION
    assert all(isinstance(v, float) for v in vector)


def test_embed_requests_normalized_vectors() -> None:
    stub = _StubModel(dimension=8)
    embedder = TextEmbedder(model=stub)

    vector = embedder.embed("hola")

    assert stub.calls == [("hola", True)]
    norm = math.sqrt(sum(v * v for v in vector))
    assert norm == 1.0 or math.isclose(norm, 1.0, abs_tol=1e-6)


def test_embed_is_deterministic_for_same_input() -> None:
    stub = _StubModel(dimension=16)
    embedder = TextEmbedder(model=stub)

    assert embedder.embed("Toledo") == embedder.embed("Toledo")
