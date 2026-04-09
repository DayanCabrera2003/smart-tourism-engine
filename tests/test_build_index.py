"""T030 — Comando CLI build-index y función build_index."""
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.cli import app
from src.indexing.build_index import build_index


@pytest.fixture
def destinations_jsonl(tmp_path: Path) -> Path:
    """JSONL mínimo con dos destinos (descripciones en inglés, como en producción)."""
    path = tmp_path / "destinations.jsonl"
    docs = [
        {
            "id": "dest-001",
            "name": "Madrid",
            "description_normalized": "madrid capital tourism culture museums spain",
        },
        {
            "id": "dest-002",
            "name": "Barcelona",
            "description_normalized": "barcelona beach architecture tourism gaudi",
        },
    ]
    path.write_text("\n".join(json.dumps(d) for d in docs))
    return path


def test_build_index_returns_doc_count(destinations_jsonl, tmp_path):
    output = tmp_path / "index.pkl"
    count = build_index(destinations_jsonl, output)
    assert count == 2


def test_build_index_creates_file(destinations_jsonl, tmp_path):
    output = tmp_path / "index.pkl"
    build_index(destinations_jsonl, output)
    assert output.exists()


def test_build_index_file_is_loadable(destinations_jsonl, tmp_path):
    from src.indexing.inverted_index import InvertedIndex

    output = tmp_path / "index.pkl"
    build_index(destinations_jsonl, output)
    idx = InvertedIndex.load(output)
    assert idx.doc_count == 2


def test_build_index_terms_are_searchable(destinations_jsonl, tmp_path):
    from src.indexing.inverted_index import InvertedIndex
    from src.indexing.stemmer import stem_token

    output = tmp_path / "index.pkl"
    build_index(destinations_jsonl, output)
    idx = InvertedIndex.load(output)
    assert len(idx.vocabulary) > 0
    # "tourism" aparece en ambos destinos; verificamos su stem dinámicamente
    stem_tourism = stem_token("tourism", language="english")
    postings = idx.get_postings(stem_tourism)
    doc_ids = {p[0] for p in postings}
    assert "dest-001" in doc_ids
    assert "dest-002" in doc_ids


def test_build_index_computes_tfidf(destinations_jsonl, tmp_path):
    from src.indexing.inverted_index import InvertedIndex

    output = tmp_path / "index.pkl"
    build_index(destinations_jsonl, output)
    idx = InvertedIndex.load(output)
    assert idx.get_norm("dest-001") > 0
    assert idx.get_norm("dest-002") > 0


def test_build_index_missing_source_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        build_index(tmp_path / "no_existe.jsonl", tmp_path / "index.pkl")


# ── CLI integration ──────────────────────────────────────────────────────────

runner = CliRunner()


def test_cli_build_index_success(destinations_jsonl, tmp_path, monkeypatch):
    """El comando CLI sale con código 0 y crea el índice."""
    import src.cli as cli_module
    from src.config import Settings

    # Copiar el JSONL donde el CLI lo espera
    processed = tmp_path / "processed"
    processed.mkdir()
    import shutil

    shutil.copy(destinations_jsonl, processed / "destinations.jsonl")

    # Parchear settings en el módulo CLI (ya fue importado)
    monkeypatch.setattr(cli_module, "settings", Settings(DATA_DIR=tmp_path))

    result = runner.invoke(app, ["build-index"])
    assert result.exit_code == 0, result.output
    assert (processed / "index.pkl").exists()
