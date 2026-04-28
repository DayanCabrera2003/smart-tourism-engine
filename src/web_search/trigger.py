"""T074 — Detector de informacion insuficiente para activar fallback web."""
from __future__ import annotations

__all__ = ["should_fallback"]

_DEFAULT_THRESHOLD = 0.30


def should_fallback(
    hits: list[tuple[str, float]],
    *,
    low_confidence: bool = False,
    threshold: float = _DEFAULT_THRESHOLD,
) -> bool:
    """True si los resultados locales son insuficientes.

    Activa fallback si:
    - No hay hits.
    - El score maximo esta por debajo del umbral.
    - El LLM previamente indico baja confianza.
    """
    if low_confidence:
        return True
    if not hits:
        return True
    max_score = max(score for _, score in hits)
    return max_score < threshold
