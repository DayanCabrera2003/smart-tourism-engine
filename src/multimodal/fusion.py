"""T088 — Fusión de scores en búsqueda multimodal combinada.

Combina el vector de texto CLIP y el vector de imagen CLIP en un único
vector de consulta ponderado con ``alpha``:

    query_vector = alpha * text_vector + (1 - alpha) * image_vector

Luego se normaliza a norma L2 para respetar la métrica coseno de Qdrant.
"""
from __future__ import annotations

import math


def combine_vectors(
    text_vector: list[float],
    image_vector: list[float],
    alpha: float,
) -> list[float]:
    """Combina dos vectores CLIP con peso ``alpha`` para el texto.

    ``alpha=1.0`` → solo texto; ``alpha=0.0`` → solo imagen.
    El resultado se normaliza a norma L2.
    """
    if len(text_vector) != len(image_vector):
        raise ValueError(
            f"Dimensiones incompatibles: texto={len(text_vector)}, imagen={len(image_vector)}"
        )
    pairs = zip(text_vector, image_vector, strict=True)
    combined = [alpha * t + (1.0 - alpha) * i for t, i in pairs]
    norm = math.sqrt(sum(v * v for v in combined)) or 1.0
    return [v / norm for v in combined]
