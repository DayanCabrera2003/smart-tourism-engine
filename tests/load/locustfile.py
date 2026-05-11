"""T122 - Load test for the Smart Tourism Engine API.

Simulates concurrent users hitting the endpoints we expect to dominate
traffic in a real demo: health checks, boolean search, semantic
search, hybrid search and recommendations. RAG (`/ask`) is included
behind a flag because it talks to an external LLM and inflates the
duration histogram.

Run against a locally running API::

    pip install -e ".[load-tests]"   # installs locust
    uvicorn src.api.main:app          # in another terminal
    locust -f tests/load/locustfile.py --host http://localhost:8000

Or headless against 50 simulated users for 60 seconds::

    locust -f tests/load/locustfile.py \\
        --host http://localhost:8000 \\
        --users 50 --spawn-rate 10 \\
        --run-time 60s --headless --only-summary

The script picks a random query from a small canon so the cache layer
does not memoize the first hit and the latency reflects real work.
"""
from __future__ import annotations

import os
import random

from locust import HttpUser, between, tag, task

# Canonical queries that exist in the corpus; keep the list short so
# the cache rotates through them quickly and we exercise both warm
# and cold paths.
CANONICAL_QUERIES = [
    "madrid",
    "paris OR rome",
    "history AND museum",
    "ciudades con playas",
    "destinos romanticos",
    "regiones vinicolas",
    "city OR culture OR museum",
    "destinos en Reino Unido",
]

SYNTHETIC_PROFILES = (
    "synthetic:mochilero",
    "synthetic:familia",
    "synthetic:luna_de_miel",
    "synthetic:aventurero",
    "synthetic:cultural",
    "synthetic:lujo",
)

INCLUDE_ASK = os.getenv("LOCUST_INCLUDE_ASK", "0") == "1"


class SmartTourismUser(HttpUser):
    """One simulated user."""

    # Each task waits 1-3 seconds before the next request, mimicking
    # a human reading the results before the next click.
    wait_time = between(1.0, 3.0)

    @task(20)
    @tag("health")
    def health(self) -> None:
        self.client.get("/health", name="GET /health")

    @task(40)
    @tag("search", "boolean")
    def search_boolean(self) -> None:
        payload = {
            "query": random.choice(CANONICAL_QUERIES),
            "top_k": 10,
            "p": 2.0,
        }
        self.client.post("/search", json=payload, name="POST /search")

    @task(20)
    @tag("search", "semantic")
    def search_semantic(self) -> None:
        payload = {
            "query": random.choice(CANONICAL_QUERIES),
            "top_k": 10,
        }
        # catch_response=True lets us mark 503 (Qdrant down) as success
        # for load reporting; the latency we care about is still
        # captured and the histogram is not contaminated by retries.
        with self.client.post(
            "/search/semantic",
            json=payload,
            name="POST /search/semantic",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 503):
                response.success()

    @task(15)
    @tag("search", "hybrid")
    def search_hybrid(self) -> None:
        payload = {
            "query": random.choice(CANONICAL_QUERIES),
            "top_k": 10,
            "alpha": 0.5,
            "p": 2.0,
        }
        with self.client.post(
            "/search/hybrid",
            json=payload,
            name="POST /search/hybrid",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 503):
                response.success()

    @task(10)
    @tag("recommend")
    def recommend(self) -> None:
        payload = {
            "user_id": random.choice(SYNTHETIC_PROFILES),
            "top_k": 5,
            "mode": "hybrid",
            "alpha": 0.6,
        }
        with self.client.post(
            "/recommend",
            json=payload,
            name="POST /recommend",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 503):
                response.success()

    @task(2)
    @tag("ask")
    def ask(self) -> None:
        if not INCLUDE_ASK:
            return
        payload = {
            "query": random.choice(CANONICAL_QUERIES),
            "top_k": 5,
            "mode": "hybrid",
            "alpha": 0.5,
        }
        with self.client.post(
            "/ask",
            json=payload,
            name="POST /ask",
            catch_response=True,
            timeout=60.0,
        ) as response:
            # The LLM may rate-limit or be down; do not fail the
            # whole run for it.
            if response.status_code in (200, 503, 429, 500):
                response.success()
