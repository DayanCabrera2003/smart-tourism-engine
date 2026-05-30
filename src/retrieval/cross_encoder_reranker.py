"""T23 - Multilingual cross-encoder reranker.

A bi-encoder (multilingual-e5-small here) computes a query and a document
vector independently and matches them by cosine. That is fast at scale
but loses precision because the two sides never attend to each other.
A cross-encoder takes the (query, document) pair together as one input
and produces a single relevance score with full attention between the
two. The cost is one model forward pass per pair, so it is only used
to rerank a small top-N (typically 30-50) produced by the bi-encoder.

The default model is ``cross-encoder/mmarco-mMiniLMv2-L12-H384-v1``,
which is a multilingual cross-encoder trained on the machine-translated
MS MARCO ranking dataset (14 languages including Spanish and English).
It is small enough (~118M params) to run on CPU at ~20-40 ms per pair,
so reranking a top-50 takes roughly 1-2 s. Heavier multilingual
rerankers (jina-reranker-v2, bge-reranker-v2-m3) are usable on GPU
but were rejected for the "CPU modesta" target.
"""
from __future__ import annotations

from typing import Any, Optional

__all__ = [
    "CrossEncoderReranker",
    "DEFAULT_CROSS_ENCODER_MODEL",
    "max_cross_encoder_relevance",
]

DEFAULT_CROSS_ENCODER_MODEL = "cross-encoder/mmarco-mMiniLMv2-L12-H384-v1"


class CrossEncoderReranker:
    """Thin wrapper that lazy-loads a sentence-transformers CrossEncoder.

    Acepta inyectar el modelo (parameter ``model=``) para que los tests
    no descarguen pesos. ``rerank`` puntúa cada par
    ``(query, document_text)`` y devuelve los doc_ids ordenados de mayor
    a menor score, junto con el score normalizado del cross-encoder.
    """

    def __init__(
        self,
        model_name: Optional[str] = None,
        *,
        model: Optional[Any] = None,
    ) -> None:
        if model is not None:
            self._model = model
        else:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(model_name or DEFAULT_CROSS_ENCODER_MODEL)

    def rerank(
        self,
        query: str,
        candidates: list[tuple[str, str]],
    ) -> list[tuple[str, float]]:
        """Return ``candidates`` re-ordered by cross-encoder relevance.

        ``candidates`` is a list of ``(doc_id, document_text)`` pairs.
        The document text should be short enough to fit the model's
        max_seq_len (typically 512 tokens) — callers can pre-truncate.

        The output is a list of ``(doc_id, score)`` sorted by score
        descending. Empty inputs return empty lists.
        """
        if not candidates:
            return []

        pairs = [(query, text) for _doc_id, text in candidates]
        # CrossEncoder.predict returns a numpy array of floats; the
        # absolute magnitude depends on the model (mMARCO uses logits in
        # roughly [-10, 10]). We map to [0, 1] with a sigmoid so the
        # downstream consumer can treat the value as a calibrated
        # probability and combine it with other [0, 1] signals.
        raw_scores = self._model.predict(pairs)
        scored: list[tuple[str, float]] = []
        for (doc_id, _text), raw in zip(candidates, raw_scores, strict=True):
            scored.append((doc_id, _sigmoid(float(raw))))
        scored.sort(key=lambda hit: hit[1], reverse=True)
        return scored


def max_cross_encoder_relevance(
    query: str,
    hits: list[tuple[str, float]],
    destinations: dict[str, dict[str, Any]],
    cross_encoder: Optional[Any],
    *,
    top_n: int = 5,
) -> Optional[float]:
    """Maxima relevancia calibrada del cross-encoder sobre los mejores ``top_n``.

    Devuelve ``None`` cuando no se puede computar (cross-encoder ausente o
    sin candidatos); el consumidor debe degradar a otra señal en ese caso.
    Solo puntua el top_n (no los 50 del rerank general): el gate solo
    necesita saber si el MEJOR candidato es relevante, y ~5 pares a 20-40 ms
    cada uno es coste despreciable comparado con el rerank completo.
    """
    if cross_encoder is None or not hits:
        return None
    head = hits[:top_n]
    candidates: list[tuple[str, str]] = []
    for doc_id, _score in head:
        meta = destinations.get(doc_id) or {}
        name = str(meta.get("name") or doc_id)
        desc = str(meta.get("description") or "")[:512]
        text = f"{name}. {desc}" if desc else name
        candidates.append((doc_id, text))
    scored = cross_encoder.rerank(query, candidates)
    if not scored:
        return None
    return max(score for _, score in scored)


def _sigmoid(x: float) -> float:
    """Numerically stable sigmoid that keeps the output in (0, 1)."""
    if x >= 0:
        import math

        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    import math

    z = math.exp(x)
    return z / (1.0 + z)
