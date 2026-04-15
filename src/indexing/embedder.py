from __future__ import annotations

from typing import Any, Optional

__all__ = ["TextEmbedder"]


class TextEmbedder:
    """
    Genera embeddings densos de texto con `sentence-transformers`.

    Por defecto usa ``all-MiniLM-L6-v2``, que produce vectores de 384
    dimensiones y soporta contenido multilingüe con un tamaño reducido
    (~90 MB), adecuado para el catálogo de destinos del proyecto.

    El modelo se puede inyectar vía ``model=`` para facilitar tests sin
    descargar pesos.
    """

    MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
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

    def embed(self, text: str) -> list[float]:
        """Devuelve el vector normalizado (L2) del texto dado."""
        vector = self._model.encode(text, normalize_embeddings=True)
        return [float(x) for x in vector]
