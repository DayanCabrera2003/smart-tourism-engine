"""T081 — Embedder multimodal CLIP (clip-ViT-B-32).

Genera vectores de 512 dimensiones para texto e imágenes en el mismo espacio
vectorial, lo que permite búsquedas cruzadas: una consulta de texto puede
recuperar imágenes relevantes y viceversa.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

__all__ = ["ClipEmbedder"]


class ClipEmbedder:
    """Genera embeddings de texto e imágenes usando CLIP (clip-ViT-B-32).

    Texto e imágenes comparten el mismo espacio de 512 dimensiones, lo que
    habilita búsquedas semánticas cruzadas sin ajuste fino adicional.

    El modelo puede inyectarse vía ``model=`` para facilitar tests que no
    requieran descargar los pesos (~340 MB).
    """

    MODEL_NAME = "clip-ViT-B-32"
    DIMENSION = 512

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

    def embed_text(self, text: str) -> list[float]:
        """Devuelve el vector normalizado (L2) del texto."""
        vector = self._model.encode(text, normalize_embeddings=True)
        return [float(x) for x in vector]

    def embed_image(self, path: str | Path) -> list[float]:
        """Devuelve el vector normalizado (L2) de la imagen en ``path``."""
        from PIL import Image

        img = Image.open(path).convert("RGB")
        vector = self._model.encode(img, normalize_embeddings=True)
        return [float(x) for x in vector]
