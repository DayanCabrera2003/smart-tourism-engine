"""T032 — Esqueleto del Modelo Booleano Extendido (p-norm)."""
import pytest

from src.retrieval.extended_boolean import ExtendedBoolean

# ── Constructor ───────────────────────────────────────────────────────────────

def test_default_p_value():
    eb = ExtendedBoolean()
    assert eb.p == 2.0


def test_custom_p_value():
    eb = ExtendedBoolean(p=5.0)
    assert eb.p == 5.0


def test_p_must_be_positive():
    with pytest.raises(ValueError):
        ExtendedBoolean(p=0.0)


def test_p_must_be_greater_than_zero():
    with pytest.raises(ValueError):
        ExtendedBoolean(p=-1.0)


# ── score stub ────────────────────────────────────────────────────────────────

def test_score_returns_zero_stub():
    """Por ahora score() devuelve 0 (esqueleto, implementación en T033/T034)."""
    eb = ExtendedBoolean(p=2.0)
    assert eb.score("turismo AND playa", "doc1") == 0.0


def test_score_return_type_is_float():
    eb = ExtendedBoolean(p=2.0)
    result = eb.score("turismo", "doc1")
    assert isinstance(result, float)
