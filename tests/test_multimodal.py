"""T090 — Tests del módulo multimodal (ClipEmbedder, image_indexer, fusion, API).

Verifica que:
- ClipEmbedder produce vectores de 512 dimensiones para texto e imágenes.
- image_indexer recorre el directorio correctamente y sube a Qdrant.
- combine_vectors fusiona embeddings con el peso correcto.
- /search/image-by-text devuelve resultados del espacio CLIP.
- /search/by-image acepta un upload y devuelve resultados similares.
- /search/multimodal funciona con texto solo y con texto + imagen.

Los tests usan modelos stub y Qdrant en memoria para no depender de pesos
descargados ni de un servicio externo.
"""
from __future__ import annotations

import io
import math
import tempfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from src.api.main import (
    app,
    get_clip_embedder,
    get_image_collection,
    get_vector_store,
)
from src.indexing.vector_store import VectorStore
from src.multimodal.clip_embedder import ClipEmbedder
from src.multimodal.fusion import combine_vectors
from src.multimodal.image_indexer import embed_images

# ── Dimensión pequeña para tests rápidos ──────────────────────────────────────

DIM = 4
TEST_COLLECTION = "destinations_image_test"


# ── Stubs ──────────────────────────────────────────────────────────────────────


class _StubClipModel:
    """Modelo CLIP falso que devuelve vectores deterministas por tipo de input."""

    def encode(self, input_, normalize_embeddings: bool = False):
        if isinstance(input_, str):
            seed = sum(ord(c) for c in input_) % 7
        else:
            seed = 3
        raw = [float(((seed + i) % 7) + 1) for i in range(DIM)]
        if normalize_embeddings:
            norm = math.sqrt(sum(v * v for v in raw)) or 1.0
            raw = [v / norm for v in raw]
        return raw


def _stub_embedder() -> ClipEmbedder:
    return ClipEmbedder(model=_StubClipModel())


def _stub_store() -> VectorStore:
    store = VectorStore(url=":memory:")
    store.create_collection(TEST_COLLECTION, vector_size=DIM)
    return store


# ── Tests de ClipEmbedder (T081) ───────────────────────────────────────────────


def test_clip_embedder_text_returns_list_of_floats():
    embedder = ClipEmbedder(model=_StubClipModel())
    vec = embedder.embed_text("playa tropical")
    assert isinstance(vec, list)
    assert all(isinstance(v, float) for v in vec)


def test_clip_embedder_text_dimension_matches_dim():
    embedder = ClipEmbedder(model=_StubClipModel())
    vec = embedder.embed_text("montaña")
    assert len(vec) == DIM


def test_clip_embedder_image_uses_pil():
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        img = Image.new("RGB", (64, 64), color=(100, 150, 200))
        img.save(tmp.name, format="JPEG")
        tmp_path = tmp.name

    embedder = ClipEmbedder(model=_StubClipModel())
    vec = embedder.embed_image(tmp_path)
    assert isinstance(vec, list)
    assert len(vec) == DIM

    import os

    os.unlink(tmp_path)


def test_clip_embedder_text_is_normalized():
    embedder = ClipEmbedder(model=_StubClipModel())
    vec = embedder.embed_text("ciudad historica")
    norm = math.sqrt(sum(v * v for v in vec))
    assert math.isclose(norm, 1.0, abs_tol=1e-5)


# ── Tests de combine_vectors / fusion (T088) ───────────────────────────────────


def test_combine_vectors_alpha_one_returns_text_vector():
    text = [1.0, 0.0, 0.0, 0.0]
    image = [0.0, 1.0, 0.0, 0.0]
    result = combine_vectors(text, image, alpha=1.0)
    norm = math.sqrt(sum(v * v for v in result))
    assert math.isclose(norm, 1.0, abs_tol=1e-5)
    assert math.isclose(result[0], 1.0, abs_tol=1e-5)
    assert math.isclose(result[1], 0.0, abs_tol=1e-5)


def test_combine_vectors_alpha_zero_returns_image_vector():
    text = [1.0, 0.0, 0.0, 0.0]
    image = [0.0, 1.0, 0.0, 0.0]
    result = combine_vectors(text, image, alpha=0.0)
    norm = math.sqrt(sum(v * v for v in result))
    assert math.isclose(norm, 1.0, abs_tol=1e-5)
    assert math.isclose(result[1], 1.0, abs_tol=1e-5)


def test_combine_vectors_half_alpha_is_normalized():
    text = [1.0, 0.0, 0.0, 0.0]
    image = [0.0, 1.0, 0.0, 0.0]
    result = combine_vectors(text, image, alpha=0.5)
    norm = math.sqrt(sum(v * v for v in result))
    assert math.isclose(norm, 1.0, abs_tol=1e-5)


def test_combine_vectors_dimension_mismatch_raises():
    with pytest.raises(ValueError, match="Dimensiones incompatibles"):
        combine_vectors([1.0, 0.0], [1.0, 0.0, 0.0], alpha=0.5)


# ── Tests de image_indexer (T083) ─────────────────────────────────────────────


def _make_test_images(base: Path) -> None:
    """Crea una estructura mínima data/raw/images/{id}/img.jpg."""
    for dest_id in ("beach-es", "mountain-ar"):
        dest_dir = base / dest_id
        dest_dir.mkdir(parents=True)
        img = Image.new("RGB", (32, 32), color=(10, 20, 30))
        img.save(dest_dir / "img.jpg", format="JPEG")


def test_embed_images_indexes_all_images():
    with tempfile.TemporaryDirectory() as tmp:
        images_dir = Path(tmp)
        _make_test_images(images_dir)
        store = _stub_store()
        embedder = ClipEmbedder(model=_StubClipModel())
        count = embed_images(images_dir, store, embedder, collection=TEST_COLLECTION)
        assert count == 2


def test_embed_images_only_new_skips_existing():
    with tempfile.TemporaryDirectory() as tmp:
        images_dir = Path(tmp)
        _make_test_images(images_dir)
        store = _stub_store()
        embedder = ClipEmbedder(model=_StubClipModel())
        embed_images(images_dir, store, embedder, collection=TEST_COLLECTION)
        count_new = embed_images(
            images_dir, store, embedder, collection=TEST_COLLECTION, only_new=True
        )
        assert count_new == 0


def test_embed_images_returns_zero_for_empty_dir():
    with tempfile.TemporaryDirectory() as tmp:
        store = _stub_store()
        embedder = ClipEmbedder(model=_StubClipModel())
        count = embed_images(Path(tmp), store, embedder, collection=TEST_COLLECTION)
        assert count == 0


# ── Tests de API multimodal (T084/T085/T088) ──────────────────────────────────


def _api_client(*, with_data: bool = True) -> TestClient:
    store = _stub_store()
    if with_data:
        embedder = ClipEmbedder(model=_StubClipModel())
        store.upsert(
            TEST_COLLECTION,
            [
                (
                    "00000000-0000-0000-0000-000000000001",
                    embedder.embed_text("playa"),
                    {"destination_id": "beach-es", "image_path": "images/beach-es/img.jpg"},
                ),
                (
                    "00000000-0000-0000-0000-000000000002",
                    embedder.embed_text("montana"),
                    {"destination_id": "mountain-ar", "image_path": "images/mountain-ar/img.jpg"},
                ),
            ],
        )
    app.dependency_overrides[get_clip_embedder] = lambda: ClipEmbedder(model=_StubClipModel())
    app.dependency_overrides[get_vector_store] = lambda: store
    app.dependency_overrides[get_image_collection] = lambda: TEST_COLLECTION
    return TestClient(app)


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_image_by_text_returns_200():
    client = _api_client()
    resp = client.post("/search/image-by-text", json={"query": "playa", "top_k": 2})
    assert resp.status_code == 200
    body = resp.json()
    assert "results" in body
    assert len(body["results"]) <= 2


def test_image_by_text_result_has_required_fields():
    client = _api_client()
    resp = client.post("/search/image-by-text", json={"query": "playa", "top_k": 1})
    assert resp.status_code == 200
    result = resp.json()["results"][0]
    assert "destination_id" in result
    assert "image_path" in result
    assert 0.0 <= result["score"] <= 1.0


def test_image_by_text_empty_collection_returns_empty():
    client = _api_client(with_data=False)
    resp = client.post("/search/image-by-text", json={"query": "playa", "top_k": 5})
    assert resp.status_code == 200
    assert resp.json()["results"] == []


def _make_jpeg_bytes() -> bytes:
    img = Image.new("RGB", (32, 32), color=(200, 100, 50))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_search_by_image_returns_200():
    client = _api_client()
    jpeg = _make_jpeg_bytes()
    resp = client.post(
        "/search/by-image",
        files={"file": ("test.jpg", jpeg, "image/jpeg")},
        params={"top_k": 2},
    )
    assert resp.status_code == 200
    assert "results" in resp.json()


def test_search_by_image_rejects_invalid_file():
    client = _api_client()
    resp = client.post(
        "/search/by-image",
        files={"file": ("bad.jpg", b"not-an-image", "image/jpeg")},
        params={"top_k": 2},
    )
    assert resp.status_code == 400


def test_multimodal_text_only_returns_200():
    client = _api_client()
    resp = client.post(
        "/search/multimodal",
        json={"query": "playa tropical", "top_k": 2},
    )
    assert resp.status_code == 200
    assert "results" in resp.json()


def test_multimodal_with_image_b64_returns_200():
    import base64

    client = _api_client()
    jpeg_b64 = base64.b64encode(_make_jpeg_bytes()).decode()
    resp = client.post(
        "/search/multimodal",
        json={"query": "playa", "image_b64": jpeg_b64, "top_k": 2, "alpha": 0.5},
    )
    assert resp.status_code == 200
    assert "results" in resp.json()
