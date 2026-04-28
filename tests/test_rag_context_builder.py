"""T063 — Tests del ContextBuilder."""
from src.api.schemas import DestinationResult
from src.rag.context_builder import build_context

_MAX_DESC = 400


def _dest(n: int, *, description: str | None = None) -> DestinationResult:
    return DestinationResult(
        id=f"dest-{n}",
        score=0.9,
        name=f"Destino {n}",
        country="España",
        description=description,
    )


def test_context_is_numbered():
    ctx = build_context([_dest(1), _dest(2)])
    assert "[1]" in ctx
    assert "[2]" in ctx


def test_context_includes_name_and_country():
    ctx = build_context([_dest(1)])
    assert "Destino 1" in ctx
    assert "España" in ctx


def test_context_truncates_long_description():
    long_desc = "x" * 800
    ctx = build_context([_dest(1, description=long_desc)])
    assert "x" * (_MAX_DESC + 1) not in ctx


def test_context_fallback_when_no_description():
    ctx = build_context([_dest(1, description=None)])
    assert "Destino 1" in ctx
    assert "España" in ctx


def test_context_empty_list_returns_empty_string():
    assert build_context([]) == ""


def test_context_order_matches_input():
    ctx = build_context([_dest(1), _dest(2), _dest(3)])
    pos1 = ctx.index("[1]")
    pos2 = ctx.index("[2]")
    pos3 = ctx.index("[3]")
    assert pos1 < pos2 < pos3
