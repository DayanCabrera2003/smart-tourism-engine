"""T073 + T079 — Cliente Tavily para busqueda web fallback con rate limiting."""
from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from threading import Lock
from typing import Any

import httpx

__all__ = ["RateLimiter", "TavilyClient", "WebResult"]

_TAVILY_ENDPOINT = "https://api.tavily.com/search"


@dataclass
class WebResult:
    """Resultado crudo de Tavily."""

    title: str
    snippet: str
    url: str


class RateLimiter:
    """Token-bucket por ventana deslizante (T079)."""

    def __init__(self, max_calls: int, period_seconds: float) -> None:
        self._max_calls = max_calls
        self._period = period_seconds
        self._calls: deque[float] = deque()
        self._lock = Lock()

    def is_allowed(self) -> bool:
        now = time.monotonic()
        with self._lock:
            while self._calls and self._calls[0] < now - self._period:
                self._calls.popleft()
            if len(self._calls) >= self._max_calls:
                return False
            self._calls.append(now)
            return True


class TavilyClient:
    """Envuelve la API REST de Tavily con rate limiting integrado."""

    def __init__(
        self,
        api_key: str,
        *,
        max_calls_per_minute: int = 20,
    ) -> None:
        self._api_key = api_key
        self._rate_limiter = RateLimiter(
            max_calls=max_calls_per_minute,
            period_seconds=60.0,
        )

    def search(self, query: str, *, max_results: int = 5) -> list[WebResult]:
        """Consulta Tavily y devuelve resultados parseados.

        Lanza RuntimeError si el rate limit esta agotado.
        Devuelve lista vacia si la llamada HTTP falla.
        """
        if not self._rate_limiter.is_allowed():
            raise RuntimeError(
                "Tavily rate limit alcanzado. Intenta de nuevo en un minuto."
            )
        payload: dict[str, Any] = {
            "api_key": self._api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
        }
        try:
            response = httpx.post(_TAVILY_ENDPOINT, json=payload, timeout=10.0)
            response.raise_for_status()
            data = response.json()
        except httpx.HTTPStatusError:
            return []

        return [
            WebResult(
                title=item.get("title", ""),
                snippet=item.get("content", ""),
                url=item.get("url", ""),
            )
            for item in data.get("results", [])
        ]
