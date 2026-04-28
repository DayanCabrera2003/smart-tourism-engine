"""T062 — Tests de la plantilla de prompt RAG."""
from src.rag.prompts import build_prompt


def test_prompt_contains_query():
    prompt = build_prompt("¿dónde ir en verano?", "[1] Ibiza\n    Isla con playas")
    assert "¿dónde ir en verano?" in prompt


def test_prompt_contains_context():
    prompt = build_prompt("query", "[1] Barcelona\n    Ciudad costera")
    assert "[1] Barcelona" in prompt


def test_prompt_instructs_citations():
    prompt = build_prompt("query", "contexto")
    assert "[1]" in prompt or "referencias" in prompt.lower() or "cit" in prompt.lower()


def test_prompt_instructs_no_invent():
    prompt = build_prompt("query", "contexto")
    lower = prompt.lower()
    assert "únicamente" in lower or "solo" in lower


def test_prompt_no_sufficient_info_instruction():
    prompt = build_prompt("query", "contexto")
    assert "No tengo suficiente información" in prompt
