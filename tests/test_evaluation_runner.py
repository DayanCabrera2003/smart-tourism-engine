"""Tests for T108 — evaluation runner."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.evaluation.runner import (
    EvaluationConfig,
    evaluate,
    evaluate_mode,
    load_queries,
)

QUERIES_FIXTURE = [
    {"id": "q01", "query": "Madrid", "relevant": ["d-madrid"]},
    {"id": "q02", "query": "Barcelona", "relevant": ["d-barcelona", "d-bcn-alt"]},
]


def _fake_perfect_retriever(query: str, top_k: int) -> list[str]:
    if "Madrid" in query:
        return ["d-madrid"]
    if "Barcelona" in query:
        return ["d-barcelona", "d-bcn-alt", "d-other"]
    return []


def _fake_useless_retriever(query: str, top_k: int) -> list[str]:
    return ["d-other", "d-other2"]


def _fake_crashing_retriever(query: str, top_k: int) -> list[str]:
    raise RuntimeError("qdrant down")


def test_load_queries_returns_list(tmp_path: Path) -> None:
    payload = {"queries": QUERIES_FIXTURE}
    path = tmp_path / "queries.json"
    path.write_text(json.dumps(payload))
    queries = load_queries(path)
    assert len(queries) == 2
    assert queries[0]["id"] == "q01"


def test_load_queries_missing_key_raises(tmp_path: Path) -> None:
    path = tmp_path / "queries.json"
    path.write_text(json.dumps({"not_queries": []}))
    with pytest.raises(ValueError):
        load_queries(path)


def test_load_queries_entry_missing_field_raises(tmp_path: Path) -> None:
    bad = {"queries": [{"id": "q01", "query": "Madrid"}]}  # no 'relevant'
    path = tmp_path / "queries.json"
    path.write_text(json.dumps(bad))
    with pytest.raises(ValueError):
        load_queries(path)


def test_evaluate_mode_perfect_retriever_scores_high() -> None:
    report = evaluate_mode(
        "boolean", _fake_perfect_retriever, QUERIES_FIXTURE, top_k=5
    )
    assert report.available is True
    # q01 hits 1/1, q02 hits 2/2 -> recall = 1.0 for both.
    assert report.recall_at_k == pytest.approx(1.0)
    # MRR should be 1.0 because both first hits are correct.
    assert report.mrr == pytest.approx(1.0)


def test_evaluate_mode_useless_retriever_scores_zero() -> None:
    report = evaluate_mode(
        "boolean", _fake_useless_retriever, QUERIES_FIXTURE, top_k=5
    )
    assert report.precision_at_k == 0.0
    assert report.recall_at_k == 0.0
    assert report.mrr == 0.0
    assert report.ndcg_at_k == 0.0


def test_evaluate_mode_crashing_retriever_records_unavailable() -> None:
    report = evaluate_mode(
        "semantic", _fake_crashing_retriever, QUERIES_FIXTURE, top_k=5
    )
    assert report.available is False
    assert "qdrant down" in report.error


def test_evaluate_mode_records_per_query_detail() -> None:
    report = evaluate_mode(
        "boolean", _fake_perfect_retriever, QUERIES_FIXTURE, top_k=5
    )
    assert len(report.per_query) == 2
    first = report.per_query[0]
    assert first["id"] == "q01"
    assert first["retrieved"] == ["d-madrid"]
    assert "P@k" in first
    assert "AP" in first


def test_evaluate_combines_multiple_modes() -> None:
    retrievers = {
        "perfect": _fake_perfect_retriever,
        "useless": _fake_useless_retriever,
        "crash": _fake_crashing_retriever,
    }
    config = EvaluationConfig(top_k=5)
    report = evaluate(retrievers, QUERIES_FIXTURE, config)
    assert set(report.modes.keys()) == {"perfect", "useless", "crash"}
    assert report.modes["perfect"].available is True
    assert report.modes["useless"].available is True
    assert report.modes["crash"].available is False


def test_evaluation_report_to_json_serialises() -> None:
    retrievers = {"perfect": _fake_perfect_retriever}
    config = EvaluationConfig(top_k=5)
    report = evaluate(retrievers, QUERIES_FIXTURE, config)
    payload = report.to_json()
    # Round-trips through json without exploding.
    json.dumps(payload)
    assert payload["num_queries"] == 2
    assert "perfect" in payload["modes"]
    assert payload["modes"]["perfect"]["metrics"]["P@k"] >= 0.0
