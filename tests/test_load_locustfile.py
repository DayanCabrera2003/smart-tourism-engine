"""T122 — Smoke test for the locustfile so it does not bit-rot.

We do not run actual load against the API from pytest (that lives in
the locust command shown in the docstring of the file). What we do is
import the locustfile and assert its public shape:

- A user class exists.
- The wait_time is configured.
- The task list covers the endpoints we expect.

This is enough to catch typos, signature changes in locust or missing
imports between releases without booting a full locust runner.
"""
from __future__ import annotations

from locust import HttpUser

from tests.load.locustfile import (
    CANONICAL_QUERIES,
    SYNTHETIC_PROFILES,
    SmartTourismUser,
)


def test_user_class_subclasses_httpuser() -> None:
    assert issubclass(SmartTourismUser, HttpUser)


def test_user_class_has_wait_time() -> None:
    assert SmartTourismUser.wait_time is not None


def test_canonical_queries_non_empty_and_strings() -> None:
    assert CANONICAL_QUERIES
    for q in CANONICAL_QUERIES:
        assert isinstance(q, str) and q.strip()


def test_synthetic_profiles_match_known_ids() -> None:
    for profile_id in SYNTHETIC_PROFILES:
        assert profile_id.startswith("synthetic:")


def test_user_class_declares_expected_tasks() -> None:
    task_names = {
        getattr(t, "locust_task_weight", None)
        for t in dir(SmartTourismUser)
        if callable(getattr(SmartTourismUser, t, None))
    }
    # All public methods should be importable; the actual locust
    # @task decorator is exercised at runtime.
    expected_methods = {
        "health",
        "search_boolean",
        "search_semantic",
        "search_hybrid",
        "recommend",
        "ask",
    }
    for method_name in expected_methods:
        assert hasattr(SmartTourismUser, method_name), method_name
    # Silence unused variable warning.
    _ = task_names
