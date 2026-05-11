"""T098 - Tests for the 'Recomendado para ti' client helper."""
from __future__ import annotations

from typing import Optional

from fastapi.testclient import TestClient

from src.api.main import app, get_destinations, get_recommendation_service
from src.recommendation.content_based import RecommendationHit
from src.recommendation.service import RecommendationOutcome
from src.recommendation.user_profile import UserProfile
from src.ui.app import fetch_recommendations


class _StubService:
    def __init__(self, outcome: RecommendationOutcome) -> None:
        self.outcome = outcome
        self.last_profile: Optional[UserProfile] = None
        self.last_mode: Optional[str] = None
        self.last_top_k: Optional[int] = None

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
        return self.outcome


def teardown_function() -> None:
    app.dependency_overrides.clear()


def test_fetch_recommendations_parses_response_from_endpoint() -> None:
    hits: list[RecommendationHit] = [
        ("dest-a", 0.91, {"slug": "dest-a", "name": "Destino A"}),
    ]
    outcome = RecommendationOutcome(hits, persona="synthetic:lujo")
    service = _StubService(outcome)
    destinations = {
        "dest-a": {
            "name": "Destino A",
            "country": "Italia",
            "description": "Lago de fondo y arquitectura clásica.",
            "image_urls": [],
        }
    }
    app.dependency_overrides[get_recommendation_service] = lambda: service
    app.dependency_overrides[get_destinations] = lambda: destinations
    client = TestClient(app)

    response = fetch_recommendations(
        "synthetic:lujo",
        interests=["spa"],
        history=[],
        top_k=1,
        client=client,
    )
    assert response.persona == "synthetic:lujo"
    assert response.empty is False
    assert len(response.results) == 1
    assert response.results[0].id == "dest-a"
    assert response.results[0].country == "Italia"

    assert service.last_top_k == 1
    assert service.last_profile is not None
    assert service.last_profile.id == "synthetic:lujo"
    assert "spa" in service.last_profile.interests


def test_fetch_recommendations_returns_empty_outcome() -> None:
    outcome = RecommendationOutcome([], empty=True)
    service = _StubService(outcome)
    app.dependency_overrides[get_recommendation_service] = lambda: service
    app.dependency_overrides[get_destinations] = lambda: {}
    client = TestClient(app)

    response = fetch_recommendations("synthetic:mochilero", client=client)
    assert response.empty is True
    assert response.results == []


def test_fetch_recommendations_defaults_to_hybrid_mode() -> None:
    outcome = RecommendationOutcome([])
    service = _StubService(outcome)
    app.dependency_overrides[get_recommendation_service] = lambda: service
    app.dependency_overrides[get_destinations] = lambda: {}
    client = TestClient(app)

    fetch_recommendations("synthetic:cultural", client=client)
    assert service.last_mode == "hybrid"
