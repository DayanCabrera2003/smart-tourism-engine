"""T121 - Prometheus instrumentation for the FastAPI service.

Exposes a ``/metrics`` endpoint with the standard text format that
Prometheus scrapers expect. We capture three signals out of the box:

- ``smart_tourism_requests_total``: counter of HTTP requests labeled
  by ``method``, ``path`` and ``status_code``. Lets you compute the
  hit rate and the error rate per endpoint.
- ``smart_tourism_request_duration_seconds``: latency histogram per
  endpoint. Use it to plot p50/p95/p99 in Grafana without keeping
  raw request logs.
- ``smart_tourism_cache_events_total``: counter for cache hits and
  misses. Buckets by ``cache`` (e.g. ``rag``) and ``event`` (``hit``
  or ``miss``). Other modules can call :func:`record_cache_event`
  to increment it.

The middleware deliberately uses ``request.scope.get("route")`` to
extract the template path (``/search/{slug}``) instead of the raw URL
so the label cardinality stays bounded; otherwise every unique URL
would inflate the registry.
"""
from __future__ import annotations

import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

__all__ = [
    "REQUEST_COUNTER",
    "REQUEST_DURATION",
    "CACHE_EVENTS",
    "PrometheusMiddleware",
    "install_metrics",
    "record_cache_event",
]


REQUEST_COUNTER = Counter(
    "smart_tourism_requests_total",
    "Total HTTP requests handled by the API.",
    labelnames=("method", "path", "status_code"),
)
REQUEST_DURATION = Histogram(
    "smart_tourism_request_duration_seconds",
    "End-to-end latency of HTTP requests in seconds.",
    labelnames=("method", "path"),
    # Buckets calibrated for an in-process API: most requests should
    # land under 250 ms, with embedder/Qdrant adding a few hundred.
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)
CACHE_EVENTS = Counter(
    "smart_tourism_cache_events_total",
    "Cache hits and misses across the system.",
    labelnames=("cache", "event"),
)


def _route_template(request: Request) -> str:
    """Best-effort template path for label stability.

    We prefer ``request.scope['route'].path`` (e.g. ``/search``) over
    ``request.url.path`` to keep cardinality bounded when routes have
    path parameters. Falls back to the raw path when the request did
    not match a known route (404).
    """
    route = request.scope.get("route")
    if route is not None and getattr(route, "path", None):
        return route.path
    return request.url.path


class PrometheusMiddleware(BaseHTTPMiddleware):
    """Increment counters and observe latency for each handled request."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        start = time.perf_counter()
        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception:
            elapsed = time.perf_counter() - start
            path = _route_template(request)
            REQUEST_COUNTER.labels(
                method=request.method, path=path, status_code="500"
            ).inc()
            REQUEST_DURATION.labels(method=request.method, path=path).observe(elapsed)
            raise
        elapsed = time.perf_counter() - start
        path = _route_template(request)
        REQUEST_COUNTER.labels(
            method=request.method, path=path, status_code=str(status_code)
        ).inc()
        REQUEST_DURATION.labels(method=request.method, path=path).observe(elapsed)
        return response


def record_cache_event(cache: str, event: str) -> None:
    """Record a cache hit or miss.

    ``cache`` identifies the cache (``rag``, ``embedder``, ...);
    ``event`` is ``"hit"`` or ``"miss"``. Other values are allowed but
    callers should agree on a small vocabulary to keep dashboards
    consistent.
    """
    CACHE_EVENTS.labels(cache=cache, event=event).inc()


def install_metrics(
    app: FastAPI,
    *,
    registry: CollectorRegistry = REGISTRY,
) -> None:
    """Register the middleware and the ``/metrics`` endpoint on ``app``.

    The registry is parameterized so tests can pass a fresh one and
    avoid leaking counter state between assertions.
    """
    app.add_middleware(PrometheusMiddleware)

    @app.get("/metrics", include_in_schema=False)
    def _metrics_endpoint() -> Response:  # pragma: no cover - thin wrapper
        return Response(
            content=generate_latest(registry),
            media_type=CONTENT_TYPE_LATEST,
        )
