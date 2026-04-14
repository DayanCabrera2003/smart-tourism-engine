import pytest

from src.indexing.vector_store import VectorStore


@pytest.fixture
def store() -> VectorStore:
    return VectorStore(url=":memory:")


COLLECTION = "test_collection"


def test_create_collection_idempotent(store: VectorStore) -> None:
    store.create_collection(COLLECTION, vector_size=4)
    # Crear de nuevo no debe lanzar
    store.create_collection(COLLECTION, vector_size=4)
    assert store.client.collection_exists(COLLECTION)


def test_recreate_collection(store: VectorStore) -> None:
    store.create_collection(COLLECTION, vector_size=4)
    store.upsert(
        COLLECTION,
        [(1, [1.0, 0.0, 0.0, 0.0], {"name": "a"})],
    )
    store.create_collection(COLLECTION, vector_size=4, recreate=True)
    hits = store.search(COLLECTION, [1.0, 0.0, 0.0, 0.0], top_k=5)
    assert hits == []


def test_upsert_returns_count_and_search(store: VectorStore) -> None:
    store.create_collection(COLLECTION, vector_size=3)
    points = [
        (1, [1.0, 0.0, 0.0], {"name": "x"}),
        (2, [0.0, 1.0, 0.0], {"name": "y"}),
        (3, [0.0, 0.0, 1.0], {"name": "z"}),
    ]
    n = store.upsert(COLLECTION, points)
    assert n == 3

    hits = store.search(COLLECTION, [1.0, 0.0, 0.0], top_k=2)
    assert len(hits) == 2
    top_id, top_score, top_payload = hits[0]
    assert top_id == 1
    assert top_payload == {"name": "x"}
    assert top_score == pytest.approx(1.0, abs=1e-5)


def test_upsert_empty_is_noop(store: VectorStore) -> None:
    store.create_collection(COLLECTION, vector_size=3)
    assert store.upsert(COLLECTION, []) == 0


def test_search_respects_score_threshold(store: VectorStore) -> None:
    store.create_collection(COLLECTION, vector_size=3)
    store.upsert(
        COLLECTION,
        [
            (1, [1.0, 0.0, 0.0], {}),
            (2, [-1.0, 0.0, 0.0], {}),
        ],
    )
    hits = store.search(
        COLLECTION, [1.0, 0.0, 0.0], top_k=5, score_threshold=0.5
    )
    assert [h[0] for h in hits] == [1]
