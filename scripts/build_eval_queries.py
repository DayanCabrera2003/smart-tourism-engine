"""T105 - Build evaluation queries.json from objective rules over the corpus.

The plan asks for "queries anotadas a mano por el equipo". We generate
the initial annotation algorithmically using verifiable rules so the
team can validate and edit the file afterwards instead of doing
boilerplate work. Each query records the rule that produced its ground
truth, so the methodology is auditable.

Annotation rules supported:

- ``country=X``: ground truth is every destination with ``country == X``.
- ``id=X``: ground truth is exactly the destination with id ``X``.
- ``ids=[X1, X2, ...]``: explicit list (for hand-curated queries).
- ``keyword=X``: ground truth is every destination whose description
  (lowercased) contains the word ``X`` as a whole word.
- ``keyword_in_country=X|C``: keyword ``X`` AND ``country == C``.
- ``keyword_any=X1,X2``: any of the listed keywords appears.

Regenerate after any change to the corpus so the ground truth stays
consistent::

    python scripts/build_eval_queries.py
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from src.config import settings

QUERY_SPECS: list[dict] = [
    {"id": "q01", "query": "Madrid", "language": "es", "rule": "id=wikivoyage-madrid"},
    {"id": "q02", "query": "Paris", "language": "es", "rule": "id=wikivoyage-paris"},
    {"id": "q03", "query": "Barcelona", "language": "es", "rule": "id=wikivoyage-barcelona"},
    {"id": "q04", "query": "ciudades en España", "language": "es", "rule": "country=Spain"},
    {"id": "q05", "query": "destinos en Francia", "language": "es", "rule": "country=France"},
    {"id": "q06", "query": "ciudades italianas", "language": "es", "rule": "country=Italy"},
    {"id": "q07", "query": "Germany cities", "language": "en", "rule": "country=Germany"},
    {"id": "q08", "query": "destinos en Japón", "language": "es", "rule": "country=Japan"},
    {
        "id": "q09",
        "query": "ciudades con playas",
        "language": "es",
        "rule": "keyword=beach",
    },
    {
        "id": "q10",
        "query": "destinos de montaña",
        "language": "es",
        "rule": "keyword=mountain",
    },
    {
        "id": "q11",
        "query": "museos y galerías",
        "language": "es",
        "rule": "keyword=museum",
    },
    {
        "id": "q12",
        "query": "ciudades históricas",
        "language": "es",
        "rule": "keyword_any=historic,historical",
    },
    {
        "id": "q13",
        "query": "catedrales medievales",
        "language": "es",
        "rule": "keyword_any=cathedral,medieval",
    },
    {"id": "q14", "query": "regiones vinícolas", "language": "es", "rule": "keyword=wine"},
    {
        "id": "q15",
        "query": "destinos en el desierto",
        "language": "es",
        "rule": "keyword=desert",
    },
    {
        "id": "q16",
        "query": "playas en España",
        "language": "es",
        "rule": "keyword_in_country=beach|Spain",
    },
    {
        "id": "q17",
        "query": "ciudades históricas en Italia",
        "language": "es",
        "rule": "keyword_in_country=historic|Italy",
    },
    {
        "id": "q18",
        "query": "destinos romanticos",
        "language": "es",
        "rule": "keyword=romantic",
    },
    {
        "id": "q19",
        "query": "destinos en Reino Unido",
        "language": "es",
        "rule": "country=United Kingdom",
    },
    {
        "id": "q20",
        "query": "Estados Unidos ciudades",
        "language": "es",
        "rule": "country=United States",
    },
    {
        "id": "q21",
        "query": "destinos en China",
        "language": "es",
        "rule": "country=China",
    },
    {
        "id": "q22",
        "query": "ciudades coloniales en Mexico",
        "language": "es",
        "rule": "keyword_in_country=colonial|Mexico",
    },
]


def _word_in_text(word: str, text: str) -> bool:
    """Match ``word`` as a whole token, case-insensitive."""
    return re.search(rf"\b{re.escape(word.lower())}\b", text.lower()) is not None


def _apply_rule(rule: str, corpus: list[dict]) -> list[str]:
    """Resolve a rule string into a list of destination ids."""
    if rule.startswith("id="):
        target = rule[len("id="):]
        return [r["id"] for r in corpus if r["id"] == target]
    if rule.startswith("ids="):
        wanted = {x.strip() for x in rule[len("ids="):].strip("[]").split(",")}
        return [r["id"] for r in corpus if r["id"] in wanted]
    if rule.startswith("country="):
        country = rule[len("country="):]
        return [r["id"] for r in corpus if r.get("country") == country]
    if rule.startswith("keyword_in_country="):
        spec = rule[len("keyword_in_country="):]
        keyword, country = spec.split("|", 1)
        return [
            r["id"]
            for r in corpus
            if r.get("country") == country
            and _word_in_text(keyword, r.get("description") or "")
        ]
    if rule.startswith("keyword_any="):
        keywords = [k.strip() for k in rule[len("keyword_any="):].split(",")]
        return [
            r["id"]
            for r in corpus
            if any(_word_in_text(k, r.get("description") or "") for k in keywords)
        ]
    if rule.startswith("keyword="):
        keyword = rule[len("keyword="):]
        return [
            r["id"]
            for r in corpus if _word_in_text(keyword, r.get("description") or "")
        ]
    raise ValueError(f"Unknown rule: {rule!r}")


def build_queries(corpus: list[dict]) -> dict:
    """Materialize the queries.json structure."""
    queries = []
    for spec in QUERY_SPECS:
        relevant = sorted(_apply_rule(spec["rule"], corpus))
        queries.append(
            {
                "id": spec["id"],
                "query": spec["query"],
                "language": spec["language"],
                "annotation_rule": spec["rule"],
                "relevant": relevant,
                "relevant_count": len(relevant),
            }
        )
    return {
        "metadata": {
            "version": "1.0",
            "total_queries": len(queries),
            "annotation_methodology": (
                "Ground truth derivado por reglas objetivas (country=, keyword=, "
                "id=). Cada entrada incluye su regla para auditoría. La revisión "
                "humana puede editar 'relevant' a mano si la regla genera ruido."
            ),
            "review_status": "pending_human_validation",
            "corpus_size": len(corpus),
        },
        "queries": queries,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=settings.DATA_DIR / "processed" / "destinations.jsonl",
        help="Ruta al JSONL del corpus.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=settings.DATA_DIR / "eval" / "queries.json",
        help="Ruta de salida del queries.json.",
    )
    args = parser.parse_args(argv)

    corpus = [json.loads(line) for line in args.source.open()]
    payload = build_queries(corpus)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    empty = [q["id"] for q in payload["queries"] if not q["relevant"]]
    print(f"Wrote {len(payload['queries'])} queries to {args.output}")
    if empty:
        print(f"WARNING: queries with empty ground truth: {empty}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
