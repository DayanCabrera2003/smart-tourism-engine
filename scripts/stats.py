"""
Estadísticas del corpus de destinos turísticos.
Lee desde SQLite (primary) con fallback a JSONL.
"""
import json
from collections import Counter

from src.config import settings


def stats_from_sqlite():
    from sqlalchemy import create_engine, text

    db_path = settings.DATA_DIR / "processed" / "destinations.db"
    if not db_path.exists():
        return None

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM destinations")).scalar()
        if total == 0:
            return None

        rows = conn.execute(
            text("SELECT country, source, description, tags FROM destinations")
        ).fetchall()

    countries = Counter()
    sources = Counter()
    desc_lengths = []
    tag_counts = []

    for country, source, description, tags_json in rows:
        countries[country or "Unknown"] += 1
        sources[source or "Unknown"] += 1
        desc_lengths.append(len(description or ""))
        try:
            tag_counts.append(len(json.loads(tags_json or "[]")))
        except (json.JSONDecodeError, TypeError):
            tag_counts.append(0)

    return {
        "total": total,
        "countries": dict(countries.most_common(10)),
        "sources": dict(sources.most_common()),
        "avg_desc_chars": sum(desc_lengths) / total,
        "avg_tags": sum(tag_counts) / total,
        "num_countries": len(countries),
    }


def stats_from_jsonl():
    processed_file = settings.DATA_DIR / "processed" / "destinations.jsonl"
    if not processed_file.exists():
        return None

    destinations = []
    with open(processed_file, "r", encoding="utf-8") as f:
        for line in f:
            destinations.append(json.loads(line))

    total = len(destinations)
    if total == 0:
        return None

    countries = Counter(d.get("country", "Unknown") for d in destinations)
    sources = Counter(d.get("source", "Unknown") for d in destinations)
    desc_lengths = [len(d.get("description", "")) for d in destinations]
    tag_counts = [len(d.get("tags", [])) for d in destinations]

    return {
        "total": total,
        "countries": dict(countries.most_common(10)),
        "sources": dict(sources.most_common()),
        "avg_desc_chars": sum(desc_lengths) / total,
        "avg_tags": sum(tag_counts) / total,
        "num_countries": len(countries),
    }


def main():
    stats = stats_from_sqlite()
    source_label = "SQLite"
    if stats is None:
        stats = stats_from_jsonl()
        source_label = "JSONL"

    if stats is None:
        print("Error: No se encontró ninguna fuente de datos (SQLite ni JSONL).")
        return

    print(f"=== Estadísticas del Corpus ({source_label}) ===")
    print(f"Total de destinos      : {stats['total']}")
    print(f"Países cubiertos       : {stats['num_countries']}")
    print(f"Longitud media desc.   : {stats['avg_desc_chars']:.0f} caracteres")
    print(f"Etiquetas medias/dest. : {stats['avg_tags']:.1f}")
    print()
    print("Top países:")
    for country, count in stats["countries"].items():
        print(f"  {country:<30} {count}")
    print()
    print("Fuentes:")
    for src, count in stats["sources"].items():
        print(f"  {src:<30} {count}")
    print("=" * 45)


if __name__ == "__main__":
    main()
