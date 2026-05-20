"""T11 - Evaluation runner for the search modes.

Computes Precision@10, Recall@10, MRR and nDCG@10 for each query in
``data/eval/queries_v2.json`` across the three search modes
(``boolean``, ``semantic``, ``hybrid``), and prints a per-query and
aggregate table.

The lexical (``boolean``) mode runs locally against the on-disk
inverted index and does not need Qdrant. Semantic and hybrid require
Qdrant up at the URL configured in :mod:`src.config`.

Usage:

    python scripts/evaluate.py
    python scripts/evaluate.py --modes boolean
    python scripts/evaluate.py --modes boolean semantic hybrid \\
        --output data/eval/results.csv

Designed to be runnable both as a script and as a module so it can
slot into CI later.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import pickle
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from src.config import settings


@dataclass(frozen=True)
class QueryRecord:
    id: str
    query: str
    language: str
    relevant: frozenset[str]
    relevant_count: int


def load_eval_set(path: Path) -> list[QueryRecord]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    out: list[QueryRecord] = []
    for q in payload["queries"]:
        out.append(
            QueryRecord(
                id=q["id"],
                query=q["query"],
                language=q.get("language", "es"),
                relevant=frozenset(q["relevant"]),
                relevant_count=q.get("relevant_count", len(q["relevant"])),
            )
        )
    return out


# ── Metric helpers ────────────────────────────────────────────────────────────


def precision_at_k(retrieved: list[str], relevant: frozenset[str], k: int) -> float:
    """Precision@K following the standard IR definition (divide by ``k``).

    Dividing by ``len(head)`` would inflate the score for queries that
    return fewer than ``k`` documents (a 3-out-of-3 perfect retrieval
    would read as P@10=1.0 instead of 0.3). The standard P@K is always
    ``relevant_retrieved / k``.
    """
    if k <= 0:
        return 0.0
    head = retrieved[:k]
    hit = sum(1 for d in head if d in relevant)
    return hit / k


def recall_at_k(retrieved: list[str], relevant: frozenset[str], k: int) -> float:
    if not relevant:
        return 0.0
    head = retrieved[:k]
    hit = sum(1 for d in head if d in relevant)
    return hit / len(relevant)


def reciprocal_rank(retrieved: list[str], relevant: frozenset[str]) -> float:
    for i, d in enumerate(retrieved, start=1):
        if d in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(retrieved: list[str], relevant: frozenset[str], k: int) -> float:
    head = retrieved[:k]
    dcg = 0.0
    for i, d in enumerate(head, start=1):
        if d in relevant:
            dcg += 1.0 / math.log2(i + 1)
    # Ideal: all relevant docs ranked at the top
    ideal_count = min(k, len(relevant))
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_count + 1))
    return dcg / idcg if idcg > 0 else 0.0


# ── Retriever wrappers ────────────────────────────────────────────────────────


def _build_destinations_map() -> dict[str, dict[str, object]]:
    """Lightweight in-memory copy of SQLite payload used by geo filter."""
    from sqlalchemy import select

    from src.ingestion.store import Session, destinations

    with Session() as session:
        rows = session.execute(select(destinations)).mappings().all()
    return {row["id"]: dict(row) for row in rows}


def _build_reranker_from_destinations(
    destinations: dict[str, dict[str, object]],
):
    """Mirror of src.api.main._build_reranker so evaluation reflects the API."""
    from src.retrieval.freshness import freshness_score
    from src.retrieval.reranker import Reranker

    popularity: dict[str, float] = {}
    freshness: dict[str, float] = {}
    for doc_id, meta in destinations.items():
        pop = meta.get("popularity")
        if isinstance(pop, (int, float)):
            popularity[doc_id] = float(pop)
        fetched = meta.get("fetched_at")
        if fetched is not None:
            try:
                freshness[doc_id] = freshness_score(
                    fetched.isoformat() if hasattr(fetched, "isoformat") else fetched
                )
            except (TypeError, ValueError):
                pass
    return Reranker(popularity=popularity, freshness=freshness)


def _cross_encode_pairs(
    query: str,
    pairs: list[tuple[str, float]],
    destinations: dict[str, dict[str, object]],
    cross_encoder,
    *,
    top_n: int = 50,
    blend: float = 0.5,
) -> list[tuple[str, float]]:
    """Mirror of src.api.main._maybe_cross_encode (blended)."""
    if not pairs or cross_encoder is None:
        return pairs
    head = pairs[:top_n]
    tail = pairs[top_n:]
    candidates: list[tuple[str, str]] = []
    for doc_id, _score in head:
        meta = destinations.get(doc_id) or {}
        name = str(meta.get("name") or doc_id)
        desc = str(meta.get("description") or "")[:512]
        text = f"{name}. {desc}" if desc else name
        candidates.append((doc_id, text))
    ce_scores = dict(cross_encoder.rerank(query, candidates))
    blended: list[tuple[str, float]] = []
    blend_c = max(0.0, min(1.0, blend))
    for doc_id, bi_score in head:
        ce = ce_scores.get(doc_id, 0.0)
        blended.append((doc_id, (1.0 - blend_c) * bi_score + blend_c * ce))
    blended.sort(key=lambda hit: hit[1], reverse=True)
    return blended + tail


def make_boolean_runner(
    p: float = 2.0, use_reranker: bool = False
) -> Callable[[str], list[str]]:
    from src.retrieval.extended_boolean import ExtendedBoolean
    from src.retrieval.geo_filter import apply_country_filter

    index_path: Path = settings.DATA_DIR / "processed" / "index.pkl"
    if not index_path.exists():
        raise FileNotFoundError(
            f"No inverted index at {index_path}. Run `python -m src.cli build-index` first."
        )
    with index_path.open("rb") as fh:
        index = pickle.load(fh)
    destinations = _build_destinations_map()
    retriever = ExtendedBoolean(p=p)
    reranker = _build_reranker_from_destinations(destinations) if use_reranker else None

    def run(query: str) -> list[str]:
        hits = retriever.search(query, index, top_k=200)
        hits_country = [
            (doc_id, score, (destinations.get(doc_id) or {}).get("country"))
            for doc_id, score in hits
        ]
        filtered = apply_country_filter(
            hits_country, query, country_getter=lambda h: h[2]
        )
        pairs = [(doc_id, score) for doc_id, score, _ in filtered]
        if reranker is not None and pairs:
            pairs = reranker.rerank(pairs)
        return [doc_id for doc_id, _ in pairs[:10]]

    return run


def _build_cross_encoder_if_enabled(use_cross_encoder: bool):
    if not use_cross_encoder:
        return None
    from src.retrieval.cross_encoder_reranker import CrossEncoderReranker

    return CrossEncoderReranker()


def make_semantic_runner(
    use_reranker: bool = False,
    use_cross_encoder: bool = False,
    expand: bool = True,
) -> Callable[[str], list[str]]:
    from src.indexing.embed_destinations import DEFAULT_COLLECTION
    from src.indexing.embedder import TextEmbedder
    from src.indexing.vector_store import VectorStore
    from src.retrieval.bilingual_query import expand_query
    from src.retrieval.geo_filter import filter_search_hits

    embedder = TextEmbedder()
    store = VectorStore()
    destinations = _build_destinations_map()
    reranker = _build_reranker_from_destinations(destinations) if use_reranker else None
    ce = _build_cross_encoder_if_enabled(use_cross_encoder)

    def run(query: str) -> list[str]:
        expanded = expand_query(query) if expand else query
        vector = embedder.embed(expanded, mode="query")
        raw = store.search(DEFAULT_COLLECTION, vector, top_k=200)
        filtered = filter_search_hits(raw, query)
        pairs = [
            (str(payload.get("slug") or pid), float(score))
            for pid, score, payload in filtered
        ]
        pairs = _cross_encode_pairs(query, pairs, destinations, ce)
        if reranker is not None and pairs:
            pairs = reranker.rerank(pairs)
        return [doc_id for doc_id, _ in pairs[:10]]

    return run


def make_hybrid_runner(
    alpha: float = 0.4,
    p: float = 2.0,
    use_reranker: bool = False,
    use_cross_encoder: bool = False,
    expand: bool = True,
) -> Callable[[str], list[str]]:
    from src.indexing.embed_destinations import DEFAULT_COLLECTION
    from src.indexing.embedder import TextEmbedder
    from src.indexing.vector_store import VectorStore
    from src.retrieval.bilingual_query import expand_query
    from src.retrieval.extended_boolean import ExtendedBoolean
    from src.retrieval.geo_filter import apply_country_filter
    from src.retrieval.hybrid import HybridRetriever

    index_path: Path = settings.DATA_DIR / "processed" / "index.pkl"
    with index_path.open("rb") as fh:
        index = pickle.load(fh)
    destinations = _build_destinations_map()
    embedder = TextEmbedder()
    store = VectorStore()
    extended = ExtendedBoolean(p=p)
    hybrid = HybridRetriever(
        extended=extended,
        embedder=embedder,
        store=store,
        collection=DEFAULT_COLLECTION,
        alpha=alpha,
    )
    reranker = _build_reranker_from_destinations(destinations) if use_reranker else None
    ce = _build_cross_encoder_if_enabled(use_cross_encoder)

    def run(query: str) -> list[str]:
        expanded = expand_query(query) if expand else query
        hits = hybrid.search(expanded, index, top_k=200)
        hits_country = [
            (doc_id, score, (destinations.get(doc_id) or {}).get("country"))
            for doc_id, score in hits
        ]
        filtered = apply_country_filter(
            hits_country, query, country_getter=lambda h: h[2]
        )
        pairs = [(doc_id, score) for doc_id, score, _ in filtered]
        pairs = _cross_encode_pairs(query, pairs, destinations, ce)
        if reranker is not None and pairs:
            pairs = reranker.rerank(pairs)
        return [doc_id for doc_id, _ in pairs[:10]]

    return run


def make_semantic_ce_runner() -> Callable[[str], list[str]]:
    """Convenience runner: semantic + cross-encoder + reranker."""
    return make_semantic_runner(use_reranker=True, use_cross_encoder=True)


def make_hybrid_ce_runner() -> Callable[[str], list[str]]:
    """Convenience runner: hybrid + cross-encoder + reranker."""
    return make_hybrid_runner(use_reranker=True, use_cross_encoder=True)


_RUNNERS: dict[str, Callable[[], Callable[[str], list[str]]]] = {
    "boolean": make_boolean_runner,
    "semantic": make_semantic_runner,
    "hybrid": make_hybrid_runner,
    "semantic_ce": make_semantic_ce_runner,
    "hybrid_ce": make_hybrid_ce_runner,
}


# ── Evaluation core ───────────────────────────────────────────────────────────


def evaluate_mode(
    name: str,
    run: Callable[[str], list[str]],
    eval_set: list[QueryRecord],
    k: int = 10,
) -> list[dict]:
    rows: list[dict] = []
    for q in eval_set:
        retrieved = run(q.query)
        rows.append(
            {
                "mode": name,
                "id": q.id,
                "query": q.query,
                "language": q.language,
                "relevant_count": q.relevant_count,
                "p@10": precision_at_k(retrieved, q.relevant, k),
                "r@10": recall_at_k(retrieved, q.relevant, k),
                "mrr": reciprocal_rank(retrieved, q.relevant),
                "ndcg@10": ndcg_at_k(retrieved, q.relevant, k),
                "top10": retrieved,
            }
        )
    return rows


def aggregate(rows: list[dict]) -> dict[str, float]:
    if not rows:
        return {"p@10": 0.0, "r@10": 0.0, "mrr": 0.0, "ndcg@10": 0.0}
    n = len(rows)
    return {
        "p@10": sum(r["p@10"] for r in rows) / n,
        "r@10": sum(r["r@10"] for r in rows) / n,
        "mrr": sum(r["mrr"] for r in rows) / n,
        "ndcg@10": sum(r["ndcg@10"] for r in rows) / n,
    }


def print_summary(modes_rows: dict[str, list[dict]]) -> None:
    print()
    print(f"{'mode':<12} {'P@10':>7} {'R@10':>7} {'MRR':>7} {'nDCG@10':>9}")
    print("-" * 48)
    for mode, rows in modes_rows.items():
        agg = aggregate(rows)
        print(
            f"{mode:<12} "
            f"{agg['p@10']:>7.3f} {agg['r@10']:>7.3f} "
            f"{agg['mrr']:>7.3f} {agg['ndcg@10']:>9.3f}"
        )


def write_csv(path: Path, modes_rows: dict[str, list[dict]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "mode",
        "id",
        "query",
        "language",
        "relevant_count",
        "p@10",
        "r@10",
        "mrr",
        "ndcg@10",
        "top10",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for rows in modes_rows.values():
            for row in rows:
                # Serialize the list of doc ids as a JSON string so the
                # CSV stays one row per query.
                row_csv = {**row, "top10": json.dumps(row["top10"])}
                writer.writerow(row_csv)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--queries",
        type=Path,
        default=Path("data/eval/queries_v2.json"),
        help="Path to the eval queries JSON.",
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=sorted(_RUNNERS),
        default=["boolean", "semantic", "hybrid"],
        help="Which search modes to evaluate.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional CSV file to dump per-query results.",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=10,
        help="Cut-off used for precision/recall/nDCG (default: 10).",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    eval_set = load_eval_set(args.queries)
    if not eval_set:
        print("No queries found in eval set.", file=sys.stderr)
        return 1

    modes_rows: dict[str, list[dict]] = {}
    for mode in args.modes:
        builder = _RUNNERS[mode]
        try:
            run = builder()
        except Exception as exc:  # pragma: no cover - reported to operator
            print(f"[{mode}] runner unavailable: {exc}", file=sys.stderr)
            continue
        modes_rows[mode] = evaluate_mode(mode, run, eval_set, k=args.k)

    print_summary(modes_rows)

    if args.output is not None and modes_rows:
        write_csv(args.output, modes_rows)
        print(f"\nPer-query rows written to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
