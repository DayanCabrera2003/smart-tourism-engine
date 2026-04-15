from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from scripts.init_qdrant import COLLECTION_NAME
from src.indexing.embed_destinations import embed_destinations, slug_to_uuid
from src.indexing.vector_store import VectorStore


class _StubEmbedder:
    DIMENSION = 8

    def __init__(self) -> None:
        self.calls: list[str] = []

    def embed(self, text: str) -> list[float]:
        self.calls.append(text)
        length = len(text) or 1
        raw = [((i + 1) * length) % 7 + 0.5 for i in range(self.DIMENSION)]
        norm = math.sqrt(sum(v * v for v in raw))
        return [v / norm for v in raw]


def _write_jsonl(path: Path, docs: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for d in docs:
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")


def _fresh_store() -> VectorStore:
    store = VectorStore(url=":memory:")
    store.create_collection(COLLECTION_NAME, vector_size=_StubEmbedder.DIMENSION)
    return store


@pytest.fixture
def jsonl_file(tmp_path: Path) -> Path:
    path = tmp_path / "destinations.jsonl"
    _write_jsonl(
        path,
        [
            {
                "id": "madrid-es",
                "name": "Madrid",
                "country": "España",
                "region": "Comunidad de Madrid",
                "description": "Capital de España, conocida por sus museos.",
                "tags": ["ciudad", "cultura"],
                "image_urls": ["https://example.com/madrid.jpg"],
                "source": "wikivoyage",
            },
            {
                "id": "toledo-es",
                "name": "Toledo",
                "country": "España",
                "region": "Castilla-La Mancha",
                "description": "Ciudad medieval con catedral gótica.",
                "tags": ["historia"],
                "image_urls": [],
                "source": "wikivoyage",
            },
        ],
    )
    return path


def test_embed_destinations_uploads_all_points(jsonl_file: Path) -> None:
    store = _fresh_store()
    embedder = _StubEmbedder()

    count = embed_destinations(jsonl_file, store, embedder)

    assert count == 2
    info = store.client.get_collection(COLLECTION_NAME)
    assert info.points_count == 2


def test_embed_destinations_payload_and_id(jsonl_file: Path) -> None:
    store = _fresh_store()
    embedder = _StubEmbedder()

    embed_destinations(jsonl_file, store, embedder)

    madrid_uuid = slug_to_uuid("madrid-es")
    points = store.client.retrieve(
        collection_name=COLLECTION_NAME,
        ids=[madrid_uuid],
        with_payload=True,
    )
    assert len(points) == 1
    payload = points[0].payload or {}
    assert payload["slug"] == "madrid-es"
    assert payload["name"] == "Madrid"
    assert payload["country"] == "España"
    assert payload["region"] == "Comunidad de Madrid"
    assert payload["tags"] == ["ciudad", "cultura"]
    assert payload["image_urls"] == ["https://example.com/madrid.jpg"]
    assert payload["source"] == "wikivoyage"


def test_embed_destinations_embeds_name_plus_description(jsonl_file: Path) -> None:
    store = _fresh_store()
    embedder = _StubEmbedder()

    embed_destinations(jsonl_file, store, embedder)

    assert "Madrid. Capital de España, conocida por sus museos." in embedder.calls
    assert "Toledo. Ciudad medieval con catedral gótica." in embedder.calls


def test_embed_destinations_batches(tmp_path: Path) -> None:
    path = tmp_path / "big.jsonl"
    docs = [
        {
            "id": f"dest-{i}",
            "name": f"Dest {i}",
            "country": "ES",
            "description": f"Descripción número {i}.",
        }
        for i in range(10)
    ]
    _write_jsonl(path, docs)

    store = _fresh_store()
    calls: list[int] = []
    original_upsert = store.upsert

    def tracking_upsert(collection, points):
        points = list(points)
        calls.append(len(points))
        return original_upsert(collection, points)

    store.upsert = tracking_upsert  # type: ignore[assignment]

    total = embed_destinations(path, store, _StubEmbedder(), batch_size=3)

    assert total == 10
    assert calls == [3, 3, 3, 1]


def test_embed_destinations_empty_file(tmp_path: Path) -> None:
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")

    store = _fresh_store()
    assert embed_destinations(path, store, _StubEmbedder()) == 0


def test_embed_destinations_is_idempotent(jsonl_file: Path) -> None:
    store = _fresh_store()
    embedder = _StubEmbedder()

    embed_destinations(jsonl_file, store, embedder)
    embed_destinations(jsonl_file, store, embedder)

    info = store.client.get_collection(COLLECTION_NAME)
    assert info.points_count == 2


def test_embed_destinations_missing_source(tmp_path: Path) -> None:
    store = _fresh_store()
    with pytest.raises(FileNotFoundError):
        embed_destinations(tmp_path / "nope.jsonl", store, _StubEmbedder())


def test_slug_to_uuid_is_deterministic() -> None:
    assert slug_to_uuid("madrid-es") == slug_to_uuid("madrid-es")
    assert slug_to_uuid("madrid-es") != slug_to_uuid("toledo-es")


