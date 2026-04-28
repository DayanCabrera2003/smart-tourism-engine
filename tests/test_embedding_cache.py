"""T056 — Tests del EmbeddingCache."""
from __future__ import annotations

import pickle

import pytest

from src.indexing.embedding_cache import EmbeddingCache


class _CountingEmbedder:
    """Embedder de prueba que cuenta cuántas veces se invoca."""

    def __init__(self) -> None:
        self.call_count = 0

    def embed(self, text: str) -> list[float]:
        self.call_count += 1
        return [float(ord(c)) for c in text[:4]]


def test_cache_miss_calls_embedder():
    embedder = _CountingEmbedder()
    cache = EmbeddingCache(embedder)
    vector = cache.embed("hello")
    assert len(vector) > 0
    assert embedder.call_count >= 1


def test_cache_hit_does_not_call_embedder():
    embedder = _CountingEmbedder()
    cache = EmbeddingCache(embedder)
    v1 = cache.embed("hello")
    count_after_first = embedder.call_count
    v2 = cache.embed("hello")
    assert embedder.call_count == count_after_first
    assert v1 == v2


def test_different_texts_get_different_vectors():
    embedder = _CountingEmbedder()
    cache = EmbeddingCache(embedder)
    v1 = cache.embed("hello")
    v2 = cache.embed("world")
    assert v1 != v2
    assert embedder.call_count == 2


def test_size_tracks_unique_entries():
    embedder = _CountingEmbedder()
    cache = EmbeddingCache(embedder)
    assert cache.size == 0
    cache.embed("a")
    assert cache.size == 1
    cache.embed("a")
    assert cache.size == 1
    cache.embed("b")
    assert cache.size == 2


def test_contains_operator():
    embedder = _CountingEmbedder()
    cache = EmbeddingCache(embedder)
    assert "hello" not in cache
    cache.embed("hello")
    assert "hello" in cache


def test_save_and_load_roundtrip(tmp_path):
    embedder = _CountingEmbedder()
    cache_path = tmp_path / "cache.pkl"
    cache = EmbeddingCache(embedder, cache_path=cache_path)
    v1 = cache.embed("playa")
    cache.save()

    embedder2 = _CountingEmbedder()
    loaded = EmbeddingCache.load(embedder2, cache_path)
    assert loaded.size == 1
    v2 = loaded.embed("playa")
    assert v1 == v2
    assert embedder2.call_count == 0


def test_load_creates_empty_cache_if_file_missing(tmp_path):
    embedder = _CountingEmbedder()
    cache = EmbeddingCache.load(embedder, tmp_path / "nonexistent.pkl")
    assert cache.size == 0


def test_save_creates_parent_directories(tmp_path):
    embedder = _CountingEmbedder()
    cache_path = tmp_path / "deep" / "nested" / "cache.pkl"
    cache = EmbeddingCache(embedder, cache_path=cache_path)
    cache.embed("test")
    saved = cache.save()
    assert saved.exists()


def test_save_to_explicit_path(tmp_path):
    embedder = _CountingEmbedder()
    cache = EmbeddingCache(embedder)
    cache.embed("hello")
    path = tmp_path / "explicit.pkl"
    cache.save(path)
    with path.open("rb") as fh:
        data = pickle.load(fh)
    assert "hello" in data


def test_save_without_path_raises():
    embedder = _CountingEmbedder()
    cache = EmbeddingCache(embedder)
    with pytest.raises(ValueError):
        cache.save()


def test_pickle_file_content_is_plain_dict(tmp_path):
    embedder = _CountingEmbedder()
    cache_path = tmp_path / "cache.pkl"
    cache = EmbeddingCache(embedder, cache_path=cache_path)
    cache.embed("montaña")
    cache.save()
    with cache_path.open("rb") as fh:
        raw = pickle.load(fh)
    assert isinstance(raw, dict)
    assert "montaña" in raw


def test_load_ignores_non_dict_pickle(tmp_path):
    """Si el archivo pickle contiene algo que no es un dict, la caché inicia vacía."""
    cache_path = tmp_path / "bad.pkl"
    with cache_path.open("wb") as fh:
        pickle.dump(["not", "a", "dict"], fh)
    embedder = _CountingEmbedder()
    cache = EmbeddingCache.load(embedder, cache_path)
    assert cache.size == 0
