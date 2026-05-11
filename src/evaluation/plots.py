"""T109 - Generate comparison plots from an evaluation report.

We deliberately stay close to the matplotlib defaults so the PNGs
render well both on screen and embedded into the LNCS-style PDF
report. All figures are saved to ``docs/figures/`` so the docs can
reference them with a stable relative path.

The module exposes a single entry point (``render_plots``) that takes
an :class:`EvaluationReport` and writes one or more PNG files. Each
helper is split out so tests can inspect the rendered figure without
hitting the filesystem.
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

import matplotlib

matplotlib.use("Agg")  # non-interactive backend for headless / CI runs
import matplotlib.pyplot as plt  # noqa: E402

from src.evaluation.runner import EvaluationReport  # noqa: E402

__all__ = ["metric_bar_chart", "per_query_heatmap", "render_plots"]


METRIC_LABELS = {
    "P@k": "Precision@k",
    "R@k": "Recall@k",
    "F1@k": "F1@k",
    "MAP": "MAP",
    "MRR": "MRR",
    "nDCG@k": "nDCG@k",
}
METRIC_ORDER = list(METRIC_LABELS.keys())


def _available_modes(report: EvaluationReport) -> list[str]:
    return [m for m, r in report.modes.items() if r.available]


def metric_bar_chart(
    report: EvaluationReport,
    metrics: Optional[Iterable[str]] = None,
) -> plt.Figure:
    """Grouped bar chart of the aggregated metrics by mode.

    Modes flagged as ``available=False`` are excluded. Returns the
    Figure so the caller can save it or assert on the axes.
    """
    metric_keys = list(metrics or METRIC_ORDER)
    modes = _available_modes(report)
    fig, ax = plt.subplots(figsize=(9, 5))

    if not modes:
        ax.set_axis_off()
        ax.text(
            0.5,
            0.5,
            "No hay modos disponibles.\nCorre python -m src.cli evaluate primero.",
            ha="center",
            va="center",
        )
        return fig

    bar_width = 0.8 / len(modes)
    indices = list(range(len(metric_keys)))
    for offset, mode in enumerate(modes):
        summary = report.modes[mode].as_summary()
        values = [float(summary[m]) for m in metric_keys]
        positions = [i + offset * bar_width for i in indices]
        ax.bar(positions, values, width=bar_width, label=mode)

    centers = [i + (len(modes) - 1) * bar_width / 2 for i in indices]
    ax.set_xticks(centers)
    ax.set_xticklabels([METRIC_LABELS[m] for m in metric_keys], rotation=0)
    ax.set_ylim(0.0, 1.0)
    ax.set_ylabel("Score")
    ax.set_title(f"Comparación de modos — top_k={report.config.top_k}")
    ax.legend(title="Modo", loc="upper right")
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    fig.tight_layout()
    return fig


def per_query_heatmap(
    report: EvaluationReport,
    metric: str = "P@k",
) -> plt.Figure:
    """Heatmap: each row is a mode, each column a query.

    Cells encode the metric value for that (mode, query). Missing
    queries (unavailable modes) are masked.
    """
    if metric not in METRIC_LABELS:
        raise ValueError(
            f"Unknown metric {metric!r}; expected one of {sorted(METRIC_LABELS)}"
        )
    modes = _available_modes(report)
    fig, ax = plt.subplots(figsize=(11, max(2.0, 0.6 * len(modes) + 1)))

    if not modes or not report.queries:
        ax.set_axis_off()
        ax.text(0.5, 0.5, "Sin datos para el heatmap.", ha="center", va="center")
        return fig

    matrix = []
    query_labels = [q["id"] for q in report.queries]
    for mode in modes:
        row = report.modes[mode]
        per_q = {entry["id"]: float(entry[metric]) for entry in row.per_query}
        matrix.append([per_q.get(qid, 0.0) for qid in query_labels])

    im = ax.imshow(matrix, aspect="auto", vmin=0.0, vmax=1.0, cmap="viridis")
    ax.set_yticks(range(len(modes)))
    ax.set_yticklabels(modes)
    ax.set_xticks(range(len(query_labels)))
    ax.set_xticklabels(query_labels, rotation=90, fontsize=8)
    ax.set_title(f"{METRIC_LABELS[metric]} por query (top_k={report.config.top_k})")
    fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
    fig.tight_layout()
    return fig


def render_plots(report: EvaluationReport, output_dir: Path) -> list[Path]:
    """Render the standard set of plots into ``output_dir``.

    Returns the list of paths written so callers can wire them into
    docs or CI artefacts.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    fig = metric_bar_chart(report)
    bar_path = output_dir / "metrics_by_mode.png"
    fig.savefig(bar_path, dpi=150)
    plt.close(fig)
    paths.append(bar_path)

    for metric in ("P@k", "nDCG@k"):
        fig = per_query_heatmap(report, metric=metric)
        out = output_dir / f"heatmap_{metric.replace('@', '_at_').replace('/', '_')}.png"
        fig.savefig(out, dpi=150)
        plt.close(fig)
        paths.append(out)

    return paths
