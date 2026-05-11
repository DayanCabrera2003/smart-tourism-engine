"""T108 - Evaluation runner: load queries, run modes, compute metrics.

The runner is decoupled from any specific retriever so the CLI and the
tests can drop in fake implementations. The contract is::

    runner(query: str, top_k: int) -> list[str]   # destination ids

For each mode we plug a different callable:

- ``boolean``: Extended Boolean (p-norm) against the inverted index.
- ``semantic``: dense embeddings via Qdrant.
- ``hybrid``: linear combination of the two.

If a mode's prerequisites are unavailable (e.g. Qdrant down for the
semantic branch), the runner records that mode as ``unavailable`` in
the report instead of crashing. That way the CLI always produces a
usable comparison even with a degraded environment.
"""
from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from src.evaluation.metrics import (
    average_precision,
    f1_at_k,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
)

__all__ = [
    "RetrieverFn",
    "EvaluationConfig",
    "ModeReport",
    "EvaluationReport",
    "load_queries",
    "evaluate_mode",
    "evaluate",
]


RetrieverFn = Callable[[str, int], list[str]]


@dataclass
class EvaluationConfig:
    """Static configuration applied to every mode."""

    top_k: int = 10
    queries_path: Optional[Path] = None


@dataclass
class ModeReport:
    """Per-mode aggregated metrics plus per-query detail."""

    mode: str
    available: bool = True
    error: Optional[str] = None
    per_query: list[dict] = field(default_factory=list)
    precision_at_k: float = 0.0
    recall_at_k: float = 0.0
    f1_at_k: float = 0.0
    map_: float = 0.0
    mrr: float = 0.0
    ndcg_at_k: float = 0.0

    def as_summary(self) -> dict[str, float | str | bool | None]:
        return {
            "mode": self.mode,
            "available": self.available,
            "error": self.error,
            "P@k": round(self.precision_at_k, 4),
            "R@k": round(self.recall_at_k, 4),
            "F1@k": round(self.f1_at_k, 4),
            "MAP": round(self.map_, 4),
            "MRR": round(self.mrr, 4),
            "nDCG@k": round(self.ndcg_at_k, 4),
        }


@dataclass
class EvaluationReport:
    """Whole evaluation: config + one report per mode."""

    config: EvaluationConfig
    queries: list[dict]
    modes: dict[str, ModeReport]

    def to_table(self) -> list[dict]:
        return [report.as_summary() for report in self.modes.values()]

    def to_json(self) -> dict:
        return {
            "config": {
                "top_k": self.config.top_k,
                "queries_path": (
                    str(self.config.queries_path)
                    if self.config.queries_path
                    else None
                ),
            },
            "num_queries": len(self.queries),
            "modes": {
                name: {
                    "available": rep.available,
                    "error": rep.error,
                    "metrics": rep.as_summary(),
                    "per_query": rep.per_query,
                }
                for name, rep in self.modes.items()
            },
        }


def load_queries(path: Path) -> list[dict]:
    """Load and validate the ``queries.json`` produced by T105.

    Raises ``ValueError`` if the file lacks the ``queries`` list or any
    entry is missing the required keys (``id``, ``query``, ``relevant``).
    """
    data = json.loads(path.read_text())
    if "queries" not in data or not isinstance(data["queries"], list):
        raise ValueError(f"{path}: missing 'queries' list")
    for entry in data["queries"]:
        for key in ("id", "query", "relevant"):
            if key not in entry:
                raise ValueError(
                    f"{path}: query {entry.get('id', '?')} missing '{key}'"
                )
    return data["queries"]


def evaluate_mode(
    mode: str,
    retriever: RetrieverFn,
    queries: list[dict],
    top_k: int,
) -> ModeReport:
    """Run ``retriever`` for every query and aggregate metrics.

    ``retriever`` is called once per query with ``(query_text, top_k)``
    and must return an ordered list of destination ids. Any exception
    bubbles up as ``available=False`` so the caller can skip the mode
    in the final comparison table without losing the partial work.
    """
    report = ModeReport(mode=mode)
    per_query_pr: list[float] = []
    per_query_rc: list[float] = []
    per_query_f1: list[float] = []
    per_query_ap: list[float] = []
    per_query_rr: list[float] = []
    per_query_ndcg: list[float] = []

    for entry in queries:
        relevant = set(entry["relevant"])
        try:
            retrieved = retriever(entry["query"], top_k)
        except Exception as exc:  # pragma: no cover - integration
            report.available = False
            report.error = f"{type(exc).__name__}: {exc}"
            return report
        p = precision_at_k(retrieved, relevant, top_k)
        r = recall_at_k(retrieved, relevant, top_k)
        f = f1_at_k(retrieved, relevant, top_k)
        ap = average_precision(retrieved, relevant)
        rr = reciprocal_rank(retrieved, relevant)
        nd = ndcg_at_k(retrieved, relevant, top_k)
        per_query_pr.append(p)
        per_query_rc.append(r)
        per_query_f1.append(f)
        per_query_ap.append(ap)
        per_query_rr.append(rr)
        per_query_ndcg.append(nd)
        report.per_query.append(
            {
                "id": entry["id"],
                "query": entry["query"],
                "retrieved": retrieved,
                "relevant_count": len(relevant),
                "P@k": round(p, 4),
                "R@k": round(r, 4),
                "F1@k": round(f, 4),
                "AP": round(ap, 4),
                "RR": round(rr, 4),
                "nDCG@k": round(nd, 4),
            }
        )

    if per_query_pr:
        report.precision_at_k = statistics.mean(per_query_pr)
        report.recall_at_k = statistics.mean(per_query_rc)
        report.f1_at_k = statistics.mean(per_query_f1)
        report.map_ = statistics.mean(per_query_ap)
        report.mrr = statistics.mean(per_query_rr)
        report.ndcg_at_k = statistics.mean(per_query_ndcg)
    return report


def evaluate(
    retrievers: dict[str, RetrieverFn],
    queries: list[dict],
    config: EvaluationConfig,
) -> EvaluationReport:
    """Run every mode against the query set and assemble the report.

    Modes whose retriever raises during construction or evaluation are
    recorded as ``available=False`` so the comparison table keeps a
    placeholder row instead of going missing.
    """
    modes: dict[str, ModeReport] = {}
    for mode, retriever in retrievers.items():
        modes[mode] = evaluate_mode(mode, retriever, queries, config.top_k)
    return EvaluationReport(config=config, queries=queries, modes=modes)
