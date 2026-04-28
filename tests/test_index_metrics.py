"""T058 — Tests del script de métricas del índice vectorial."""
from __future__ import annotations

import pytest

from scripts.index_metrics import collect_metrics, format_report
from src.indexing.embed_destinations import slug_to_uuid
from src.indexing.vector_store import VectorStore

COLLECTION = "metrics_test"
DIM = 8


def _make_store(with_points: int = 3) -> VectorStore:
    store = VectorStore(url=":memory:")
    store.create_collection(COLLECTION, vector_size=DIM)
    if with_points > 0:
        points = [
            (slug_to_uuid(f"doc-{i}"), [float(i)] * DIM, {"slug": f"doc-{i}"})
            for i in range(with_points)
        ]
        store.upsert(COLLECTION, points)
    return store


def test_collect_metrics_returns_expected_keys():
    store = _make_store()
    metrics = collect_metrics(store, COLLECTION)
    for key in ("collection", "points_count", "vector_dimension", "distance_metric", "status"):
        assert key in metrics


def test_collect_metrics_correct_points_count():
    store = _make_store(with_points=5)
    metrics = collect_metrics(store, COLLECTION)
    assert metrics["points_count"] == 5


def test_collect_metrics_correct_dimension():
    store = _make_store()
    metrics = collect_metrics(store, COLLECTION)
    assert metrics["vector_dimension"] == DIM


def test_collect_metrics_distance_metric():
    store = _make_store()
    metrics = collect_metrics(store, COLLECTION)
    assert "Cosine" in metrics["distance_metric"] or "cosine" in metrics["distance_metric"].lower()


def test_collect_metrics_raises_for_missing_collection():
    store = VectorStore(url=":memory:")
    with pytest.raises(ValueError, match="no existe"):
        collect_metrics(store, "nonexistent")


def test_collect_metrics_empty_collection():
    store = _make_store(with_points=0)
    metrics = collect_metrics(store, COLLECTION)
    assert metrics["points_count"] == 0


def test_format_report_contains_key_fields():
    store = _make_store(with_points=10)
    metrics = collect_metrics(store, COLLECTION)
    report = format_report(metrics)
    assert COLLECTION in report
    assert "10" in report
    assert str(DIM) in report


def test_format_report_returns_multiline_string():
    store = _make_store()
    metrics = collect_metrics(store, COLLECTION)
    report = format_report(metrics)
    lines = report.strip().splitlines()
    assert len(lines) >= 5
