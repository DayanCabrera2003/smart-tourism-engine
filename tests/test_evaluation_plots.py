"""Tests for T109 — evaluation plots."""
from __future__ import annotations

from pathlib import Path

import pytest

from src.evaluation.plots import (
    METRIC_ORDER,
    metric_bar_chart,
    per_query_heatmap,
    render_plots,
)
from src.evaluation.runner import (
    EvaluationConfig,
    EvaluationReport,
    ModeReport,
)


def _build_report() -> EvaluationReport:
    queries = [
        {"id": "q01", "query": "Madrid", "relevant": ["d-madrid"]},
        {"id": "q02", "query": "Paris", "relevant": ["d-paris"]},
    ]
    boolean = ModeReport(
        mode="boolean",
        available=True,
        precision_at_k=0.5,
        recall_at_k=0.5,
        f1_at_k=0.5,
        map_=0.5,
        mrr=0.5,
        ndcg_at_k=0.5,
        per_query=[
            {"id": "q01", "P@k": 1.0, "R@k": 1.0, "F1@k": 1.0, "AP": 1.0, "RR": 1.0, "nDCG@k": 1.0},
            {"id": "q02", "P@k": 0.0, "R@k": 0.0, "F1@k": 0.0, "AP": 0.0, "RR": 0.0, "nDCG@k": 0.0},
        ],
    )
    semantic = ModeReport(
        mode="semantic",
        available=True,
        precision_at_k=0.75,
        recall_at_k=0.75,
        f1_at_k=0.75,
        map_=0.75,
        mrr=0.75,
        ndcg_at_k=0.75,
        per_query=[
            {"id": "q01", "P@k": 1.0, "R@k": 1.0, "F1@k": 1.0, "AP": 1.0, "RR": 1.0, "nDCG@k": 1.0},
            {"id": "q02", "P@k": 0.5, "R@k": 0.5, "F1@k": 0.5, "AP": 0.5, "RR": 0.5, "nDCG@k": 0.5},
        ],
    )
    unavailable = ModeReport(mode="hybrid", available=False, error="qdrant down")
    return EvaluationReport(
        config=EvaluationConfig(top_k=5),
        queries=queries,
        modes={"boolean": boolean, "semantic": semantic, "hybrid": unavailable},
    )


def test_metric_bar_chart_skips_unavailable_modes() -> None:
    report = _build_report()
    fig = metric_bar_chart(report)
    ax = fig.axes[0]
    legend_labels = {t.get_text() for t in ax.get_legend().get_texts()}
    assert legend_labels == {"boolean", "semantic"}
    assert "hybrid" not in legend_labels


def test_metric_bar_chart_uses_all_metrics_by_default() -> None:
    report = _build_report()
    fig = metric_bar_chart(report)
    ax = fig.axes[0]
    labels = [t.get_text() for t in ax.get_xticklabels()]
    assert len(labels) == len(METRIC_ORDER)


def test_metric_bar_chart_handles_empty_modes() -> None:
    empty = EvaluationReport(
        config=EvaluationConfig(top_k=5),
        queries=[],
        modes={"hybrid": ModeReport(mode="hybrid", available=False, error="x")},
    )
    fig = metric_bar_chart(empty)
    # The chart still renders without raising; legend may be missing.
    assert fig.axes


def test_per_query_heatmap_default_metric_is_precision() -> None:
    report = _build_report()
    fig = per_query_heatmap(report)
    ax = fig.axes[0]
    title = ax.get_title()
    assert "Precision" in title


def test_per_query_heatmap_rejects_unknown_metric() -> None:
    report = _build_report()
    with pytest.raises(ValueError):
        per_query_heatmap(report, metric="not-a-metric")


def test_render_plots_writes_png_files(tmp_path: Path) -> None:
    report = _build_report()
    paths = render_plots(report, tmp_path)
    assert len(paths) >= 1
    for path in paths:
        assert path.exists()
        assert path.suffix == ".png"
        assert path.stat().st_size > 0


def test_render_plots_creates_output_dir(tmp_path: Path) -> None:
    target = tmp_path / "new" / "subdir"
    paths = render_plots(_build_report(), target)
    assert target.is_dir()
    assert paths
