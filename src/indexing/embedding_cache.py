"""T056 — Caché de embeddings en disco.

Evita recalcular embeddings para textos ya procesados guardándolos en un
archivo pickle en ``data/processed/embeddings_cache.pkl``.  La caché es un
``dict[str, list[float]]`` donde la clave es el texto original y el valor es
el vector resultante.

La clase ``EmbeddingCache`` actúa como decorador sobre cualquier objeto con
un método ``embed(text) -> list[float]``: si el texto ya tiene un vector en
caché lo devuelve directamente; si no, llama al embedder subyacente, guarda
el resultado y lo devuelve.

La persistencia es explícita (``save`` / ``load``) para que el llamador
controle cuándo se escribe a disco y no se penalice cada petición con I/O.
"""
from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any, Protocol

__all__ = ["EmbeddingCache"]


class _Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


class EmbeddingCache:
    """Caché de embeddings respaldada por un archivo pickle en disco.

    Uso típico:

    .. code-block:: python

        embedder = TextEmbedder()
        cache = EmbeddingCache.load(path)   # carga caché existente o vacía
        cached_embedder = EmbeddingCache(embedder, cache_path=path)
        vector = cached_embedder.embed("Playas del Caribe")  # hit o miss
        cached_embedder.save()  # persiste solo los nuevos vectores
    """

    def __init__(
        self,
        embedder: _Embedder,
        *,
        cache_path: str | Path | None = None,
        _store: dict[str, list[float]] | None = None,
    ) -> None:
        self._embedder = embedder
        self._path = Path(cache_path) if cache_path else None
        self._store: dict[str, list[float]] = _store if _store is not None else {}

    @classmethod
    def load(
        cls,
        embedder: _Embedder,
        cache_path: str | Path,
    ) -> "EmbeddingCache":
        """Carga la caché desde ``cache_path`` si existe; si no, inicia vacía."""
        path = Path(cache_path)
        store: dict[str, list[float]] = {}
        if path.exists():
            with path.open("rb") as fh:
                loaded = pickle.load(fh)
                if isinstance(loaded, dict):
                    store = loaded
        return cls(embedder, cache_path=path, _store=store)

    def embed(self, text: str) -> list[float]:
        """Devuelve el vector del texto, usando la caché si está disponible."""
        if text in self._store:
            return self._store[text]
        vector = self._embedder.embed(text)
        self._store[text] = vector
        return vector

    def save(self, path: str | Path | None = None) -> Path:
        """Persiste la caché en disco.  Si ``path`` es None usa ``cache_path``."""
        target = Path(path) if path else self._path
        if target is None:
            raise ValueError("Se requiere un path para guardar la caché.")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("wb") as fh:
            pickle.dump(self._store, fh)
        return target

    @property
    def size(self) -> int:
        """Número de entradas en caché."""
        return len(self._store)

    def __contains__(self, text: Any) -> bool:
        return text in self._store
