"""Tests for T092 - synthetic profile catalog."""
from __future__ import annotations

import pytest

from src.recommendation.synthetic_profiles import (
    SYNTHETIC_PROFILE_DESCRIPTIONS,
    SYNTHETIC_PROFILES,
    get_synthetic_profile,
    list_synthetic_profile_ids,
)

EXPECTED_PROFILE_IDS = {
    "mochilero",
    "familia",
    "luna_de_miel",
    "aventurero",
    "cultural",
    "lujo",
}


def test_six_profiles_are_defined() -> None:
    assert set(SYNTHETIC_PROFILES.keys()) == EXPECTED_PROFILE_IDS
    assert len(SYNTHETIC_PROFILES) == 6


def test_each_profile_has_description() -> None:
    assert set(SYNTHETIC_PROFILE_DESCRIPTIONS.keys()) == EXPECTED_PROFILE_IDS
    for description in SYNTHETIC_PROFILE_DESCRIPTIONS.values():
        assert description.strip(), "description must be non-empty"


def test_each_profile_has_at_least_three_interests() -> None:
    for profile_id, profile in SYNTHETIC_PROFILES.items():
        assert len(profile.interests) >= 3, (
            f"{profile_id} should have at least 3 interests"
        )


def test_get_synthetic_profile_returns_copy() -> None:
    first = get_synthetic_profile("mochilero")
    second = get_synthetic_profile("mochilero")
    # Same content but distinct objects so mutations are local.
    assert first == second
    assert first is not second
    first.history.append("any-id")
    assert second.history == []


def test_get_synthetic_profile_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_synthetic_profile("does-not-exist")


def test_list_synthetic_profile_ids_is_stable_order() -> None:
    ids = list_synthetic_profile_ids()
    # Order must be deterministic so UI presents profiles in a stable order.
    assert ids == list_synthetic_profile_ids()
    assert set(ids) == EXPECTED_PROFILE_IDS


def test_profile_ids_use_synthetic_namespace() -> None:
    for profile_id, profile in SYNTHETIC_PROFILES.items():
        assert profile.id == f"synthetic:{profile_id}"
        assert profile.name == profile_id
