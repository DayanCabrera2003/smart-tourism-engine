from scripts.init_qdrant import COLLECTION_NAME, VECTOR_SIZE, init
from src.indexing.vector_store import VectorStore


def _fresh_store() -> VectorStore:
    return VectorStore(url=":memory:")


def test_init_creates_collection() -> None:
    store = _fresh_store()
    init(store)
    assert store.client.collection_exists(COLLECTION_NAME)
    info = store.client.get_collection(COLLECTION_NAME)
    assert info.config.params.vectors.size == VECTOR_SIZE


def test_init_is_idempotent() -> None:
    store = _fresh_store()
    init(store)
    init(store)
    assert store.client.collection_exists(COLLECTION_NAME)


def test_init_recreate_wipes_data() -> None:
    store = _fresh_store()
    init(store)
    store.upsert(
        COLLECTION_NAME,
        [(1, [0.1] * VECTOR_SIZE, {"name": "Madrid"})],
    )
    init(store, recreate=True)
    hits = store.search(COLLECTION_NAME, [0.1] * VECTOR_SIZE, top_k=5)
    assert hits == []


def test_vector_size_matches_embedder_dimension() -> None:
    from src.indexing.embedder import TextEmbedder

    assert VECTOR_SIZE == TextEmbedder.DIMENSION
