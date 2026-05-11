"""T097 - Tests for the synthetic profile onboarding helpers."""
from __future__ import annotations

import pytest

from src.ui.app import (
    PROFILE_SESSION_KEY,
    is_onboarding_complete,
    selected_profile_user_id,
    store_selected_profile,
    synthetic_profile_description,
    synthetic_profile_label,
)


def test_is_onboarding_complete_returns_false_for_empty_state() -> None:
    assert is_onboarding_complete({}) is False


def test_is_onboarding_complete_returns_true_after_storing_profile() -> None:
    state: dict = {}
    store_selected_profile(state, "mochilero")
    assert is_onboarding_complete(state) is True


def test_store_selected_profile_rejects_unknown_id() -> None:
    with pytest.raises(ValueError):
        store_selected_profile({}, "tourist-not-listed")


def test_selected_profile_user_id_adds_synthetic_prefix() -> None:
    state: dict = {}
    store_selected_profile(state, "lujo")
    assert selected_profile_user_id(state) == "synthetic:lujo"


def test_selected_profile_user_id_returns_none_when_unset() -> None:
    assert selected_profile_user_id({}) is None


def test_synthetic_profile_label_returns_human_label() -> None:
    assert synthetic_profile_label("luna_de_miel") == "Luna de miel"
    # Unknown ids fall back to the id itself rather than raising.
    assert synthetic_profile_label("custom") == "custom"


def test_synthetic_profile_description_is_non_empty_for_personas() -> None:
    for persona_id in ("mochilero", "familia", "luna_de_miel", "aventurero", "cultural", "lujo"):
        assert synthetic_profile_description(persona_id).strip()


def test_storing_profile_writes_session_key() -> None:
    state: dict = {}
    store_selected_profile(state, "mochilero")
    assert state[PROFILE_SESSION_KEY] == "mochilero"
