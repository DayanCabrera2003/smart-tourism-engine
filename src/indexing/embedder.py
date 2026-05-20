"""Dense text embedder used by the semantic and hybrid retrievers.

The default model is ``intfloat/multilingual-e5-small`` — a 118M-parameter
multilingual encoder that produces 384-dimensional vectors and runs
comfortably on modest CPU hardware (~16-30 ms per query). It supports
100 languages, including the Spanish queries that dominate this
project, where the previous English-only model produced noisy vectors
that ranked redirect stubs above real destinations.

The model requires callers to prefix their input depending on its
role: ``"query: "`` for search queries and ``"passage: "`` for the
documents being indexed. Without the prefix the model still works but
loses several points of retrieval quality, so the embedder applies the
right prefix based on a ``mode`` argument that defaults to ``"query"``
(the safe default for existing call sites that did not specify one).
"""
from __future__ import annotations

from typing import Any, Literal, Optional

__all__ = ["TextEmbedder", "EmbedMode"]


EmbedMode = Literal["query", "passage"]

_PREFIXES: dict[str, str] = {
    "query": "query: ",
    "passage": "passage: ",
}


class TextEmbedder:
    """Generate dense embeddings with ``sentence-transformers``.

    The model is loaded once per process. Callers should reuse a single
    instance because ``SentenceTransformer`` is not cheap to construct.
    An explicit ``model=`` injection point keeps tests free of model
    downloads.
    """

    MODEL_NAME = "intfloat/multilingual-e5-small"
    DIMENSION = 384

    def __init__(
        self,
        model_name: Optional[str] = None,
        *,
        model: Optional[Any] = None,
    ) -> None:
        if model is not None:
            self._model = model
        else:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(model_name or self.MODEL_NAME)

    def embed(self, text: str, mode: EmbedMode = "query") -> list[float]:
        """Return the unit-norm embedding of ``text``.

        ``mode`` controls the prefix prepended before encoding:

        - ``"query"`` (default) for short user queries.
        - ``"passage"`` for documents stored in the index.
        """
        prefix = _PREFIXES.get(mode)
        if prefix is None:
            raise ValueError(
                f"Unsupported embed mode {mode!r}; expected one of {list(_PREFIXES)}"
            )

        prefixed = f"{prefix}{text}"
        vector = self._model.encode(prefixed, normalize_embeddings=True)
        return [float(x) for x in vector]
