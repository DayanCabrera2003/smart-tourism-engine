"""T074 — Detector de informacion insuficiente para activar fallback web."""
from __future__ import annotations

__all__ = ["should_fallback", "should_fallback_by_relevance"]

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


def should_fallback_by_relevance(
    hits: list[tuple[str, float]],
    relevance: float | None,
    *,
    relevance_threshold: float,
    score_threshold: float = _DEFAULT_THRESHOLD,
) -> bool:
    """True si los resultados locales son insuficientes para una busqueda.

    A diferencia de ``should_fallback`` (que solo mira el coseno fusionado),
    esta version usa la relevancia calibrada del cross-encoder cuando esta
    disponible. El coseno bi-encoder mide afinidad tematica, no relevancia:
    'hoteles' matchea descripciones turisticas de cualquier pais. El
    cross-encoder, con atencion cruzada query-documento, distingue
    'Hoteles en alaska' de 'Calle Khaosan, Bangkok'.

    - Sin hits -> insuficiente.
    - Con ``relevance`` (cross-encoder disponible) -> insuficiente si esta
      por debajo de ``relevance_threshold``.
    - Sin ``relevance`` (None) -> degrada al gate por coseno fusionado.
    """
    if not hits:
        return True
    if relevance is not None:
        return relevance < relevance_threshold
    return max(score for _, score in hits) < score_threshold
