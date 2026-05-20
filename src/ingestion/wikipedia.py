"""T17 - Wikipedia ES client for the destination text source.

Pairs with :mod:`src.ingestion.wikidata`: for each Q-id we get from
Wikidata, this client fetches the corresponding Wikipedia ES article
extract (plain text, no markup) via the MediaWiki API. We prefer
``action=query&prop=extracts`` because it returns server-rendered
plain text and skips the headache of parsing raw wikitext.

The client caches every fetch on disk under
``data/raw/wikipedia_es/<title>.json`` so reruns are cheap and so we
can audit individual articles offline. A modest rate limit (100 ms
between calls) and the cooperative ``maxlag=5`` parameter keep us
well below MediaWiki's throttling thresholds.
"""
from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

__all__ = [
    "WikipediaClient",
    "DEFAULT_USER_AGENT",
    "DEFAULT_API_ENDPOINT_ES",
    "DEFAULT_API_ENDPOINT_EN",
]

DEFAULT_API_ENDPOINT_ES = "https://es.wikipedia.org/w/api.php"
DEFAULT_API_ENDPOINT_EN = "https://en.wikipedia.org/w/api.php"
DEFAULT_USER_AGENT = (
    "smart-tourism-engine/0.1 (https://github.com/dayancc/smart-tourism-engine) "
    "httpx/0.28"
)

# Regex pre-compiled once for the post-extract cleanup pass.
_BOILERPLATE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"==\s*Véase también\s*==.*$", re.DOTALL | re.IGNORECASE),
    re.compile(r"==\s*Referencias\s*==.*$", re.DOTALL | re.IGNORECASE),
    re.compile(r"==\s*Enlaces externos\s*==.*$", re.DOTALL | re.IGNORECASE),
    re.compile(r"==\s*See also\s*==.*$", re.DOTALL | re.IGNORECASE),
    re.compile(r"==\s*References\s*==.*$", re.DOTALL | re.IGNORECASE),
    re.compile(r"==\s*External links\s*==.*$", re.DOTALL | re.IGNORECASE),
)


class WikipediaClient:
    """Fetch plain-text extracts from Wikipedia with on-disk caching."""

    def __init__(
        self,
        *,
        cache_dir: Optional[Path] = None,
        endpoint_es: str = DEFAULT_API_ENDPOINT_ES,
        endpoint_en: str = DEFAULT_API_ENDPOINT_EN,
        user_agent: str = DEFAULT_USER_AGENT,
        timeout: float = 30.0,
        rate_limit_seconds: float = 0.1,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self._endpoint_es = endpoint_es
        self._endpoint_en = endpoint_en
        self._user_agent = user_agent
        self._timeout = timeout
        self._rate_limit_seconds = max(0.0, rate_limit_seconds)
        self._cache_dir = cache_dir
        if cache_dir is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)
        self._client = client
        self._owns_client = client is None
        self._last_call_at = 0.0

    def __enter__(self) -> "WikipediaClient":
        if self._client is None:
            self._client = httpx.Client(
                timeout=self._timeout,
                headers={"User-Agent": self._user_agent},
            )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def _ensure_client(self) -> httpx.Client:
        if self._client is None:
            self.__enter__()
        assert self._client is not None
        return self._client

    def _cache_path(self, title: str, language: str) -> Optional[Path]:
        if self._cache_dir is None:
            return None
        safe = re.sub(r"[^a-zA-Z0-9_.-]+", "_", title)
        return self._cache_dir / f"{language}_{safe}.json"

    def _sleep_if_needed(self) -> None:
        if self._rate_limit_seconds <= 0:
            return
        delta = time.monotonic() - self._last_call_at
        if delta < self._rate_limit_seconds:
            time.sleep(self._rate_limit_seconds - delta)
        self._last_call_at = time.monotonic()

    def fetch_extract(
        self,
        title: str,
        *,
        language: str = "es",
        force_refresh: bool = False,
    ) -> Optional[str]:
        """Return the plain-text extract for ``title`` in the given language.

        ``language`` accepts ``"es"`` and ``"en"`` (the corpus is
        currently scoped to those two). Caches the raw API JSON to
        disk per ``cache_dir``. Returns ``None`` if the page does not
        exist or returns no extract.
        """
        if language not in ("es", "en"):
            raise ValueError(f"Unsupported Wikipedia language: {language!r}")

        cache_path = self._cache_path(title, language)
        if cache_path is not None and cache_path.exists() and not force_refresh:
            try:
                payload = json.loads(cache_path.read_text(encoding="utf-8"))
                return _extract_from_payload(payload)
            except (json.JSONDecodeError, OSError):
                logger.warning("Cache hit but unreadable for %s/%s", language, title)

        endpoint = self._endpoint_es if language == "es" else self._endpoint_en
        params = {
            "action": "query",
            "format": "json",
            "prop": "extracts",
            "explaintext": "1",
            "exsectionformat": "plain",
            "titles": title,
            "redirects": "1",
            "maxlag": "5",
            "formatversion": "2",
        }

        client = self._ensure_client()
        self._sleep_if_needed()
        try:
            response = client.get(endpoint, params=params)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Wikipedia fetch failed for %s/%s: %s", language, title, exc)
            return None

        payload = response.json()
        if cache_path is not None:
            try:
                cache_path.write_text(
                    json.dumps(payload, ensure_ascii=False), encoding="utf-8"
                )
            except OSError as exc:
                logger.warning("Could not write cache for %s/%s: %s", language, title, exc)

        return _extract_from_payload(payload)


def _extract_from_payload(payload: dict) -> Optional[str]:
    """Pull the plain-text extract out of a MediaWiki API response.

    Returns ``None`` if the page is missing or has no extract. Also
    strips footer sections that are not useful for retrieval
    (References, See also, External links, and their Spanish
    counterparts).
    """
    pages = payload.get("query", {}).get("pages") or []
    if isinstance(pages, dict):
        pages = list(pages.values())
    for page in pages:
        if page.get("missing"):
            return None
        extract = page.get("extract")
        if extract:
            return _clean_extract(extract)
    return None


def _clean_extract(text: str) -> str:
    """Remove unhelpful sections at the tail of an extract.

    Wikipedia "See also" / "References" / "External links" sections
    are noise for retrieval — they consist of lists and link blobs.
    The MediaWiki API includes them in the plain extract; we strip
    them with simple regexes anchored at the section heading.
    """
    for pattern in _BOILERPLATE_PATTERNS:
        text = pattern.sub("", text)
    return text.strip()
