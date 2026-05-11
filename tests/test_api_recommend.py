"""T096 - integration tests for POST /recommend."""
from __future__ import annotations

from typing import Optional

from fastapi.testclient import TestClient

from src.api.main import app, get_destinations, get_recommendation_service
from src.recommendation.content_based import RecommendationHit
from src.recommendation.service import RecommendationOutcome
from src.recommendation.user_profile import UserProfile


class _FakeService:
    """Stub RecommendationService that records its inputs."""

    def __init__(self, outcome: RecommendationOutcome):
        self.outcome = outcome
        self.last_profile: Optional[UserProfile] = None
        self.last_top_k: Optional[int] = None
        self.last_mode: Optional[str] = None
        self.last_alpha: Optional[float] = None

    def recommend(
        self,
        profile: Optional[UserProfile],
        *,
        top_k: int,
        mode: str,
        alpha: float,
    ) -> RecommendationOutcome:
        self.last_profile = profile
        self.last_top_k = top_k
        self.last_mode = mode
        self.last_alpha = alpha
        return self.outcome


def _client(
    outcome: RecommendationOutcome,
    destinations: Optional[dict] = None,
) -> tuple[TestClient, _FakeService]:
    service = _FakeService(outcome)
    app.dependency_overrides[get_recommendation_service] = lambda: service
    app.dependency_overrides[get_destinations] = lambda: destinations or {}
    return TestClient(app), service


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_recommend_returns_ranked_destinations_for_synthetic_persona() -> None:
    hits: list[RecommendationHit] = [
        ("santorini-gr", 0.92, {"slug": "santorini-gr", "name": "Santorini"}),
        ("venice-it", 0.85, {"slug": "venice-it"}),
    ]
    outcome = RecommendationOutcome(hits, persona="synthetic:lujo")
    destinations = {
        "santorini-gr": {
            "name": "Santorini",
            "country": "Grecia",
            "description": "Isla mediterránea con casas blancas.",
            "image_urls": ["https://example.com/santorini.jpg"],
        }
    }
    client, service = _client(outcome, destinations=destinations)

    response = client.post(
        "/recommend",
        json={"user_id": "synthetic:lujo", "top_k": 2, "mode": "hybrid"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["persona"] == "synthetic:lujo"
    assert body["empty"] is False
    ids = [r["id"] for r in body["results"]]
    assert ids == ["santorini-gr", "venice-it"]
    assert body["results"][0]["country"] == "Grecia"

    assert service.last_profile is not None
    assert service.last_profile.id == "synthetic:lujo"
    assert service.last_top_k == 2
    assert service.last_mode == "hybrid"


def test_recommend_returns_empty_when_no_signal() -> None:
    outcome = RecommendationOutcome([], empty=True)
    client, _ = _client(outcome)
    response = client.post("/recommend", json={"top_k": 5})
    assert response.status_code == 200
    body = response.json()
    assert body["empty"] is True
    assert body["results"] == []
    assert body["persona"] is None


def test_recommend_passes_alpha_to_service() -> None:
    outcome = RecommendationOutcome([])
    client, service = _client(outcome)
    response = client.post(
        "/recommend",
        json={"user_id": "mochilero", "alpha": 0.2, "mode": "hybrid"},
    )
    assert response.status_code == 200
    assert service.last_alpha == 0.2


def test_recommend_rejects_invalid_mode() -> None:
    outcome = RecommendationOutcome([])
    client, _ = _client(outcome)
    response = client.post(
        "/recommend",
        json={"user_id": "mochilero", "mode": "nonsense"},
    )
    assert response.status_code == 422
