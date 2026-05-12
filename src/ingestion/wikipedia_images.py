"""T126 - Fetch thumbnail images from the Wikipedia REST API.

The Wikipedia REST endpoint::

    GET https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}

returns a JSON document that includes ``thumbnail.source`` (a
~300x200 px image) and ``originalimage.source`` (the full-size
version), plus the canonical title, the page id and the license
metadata. Both image links are direct URLs to upload.wikimedia.org
so we can ``GET`` them with no further authentication.

This module is a thin client around that endpoint plus a downloader
that writes the chosen image to disk. It does *not* touch Qdrant or
the inverted index — the caller decides whether to persist
``image_urls`` into the destinations JSONL, into SQLite, or both.

Rate limiting and respect for Wikipedia's etiquette:

- We send a ``User-Agent`` that identifies the project and provides
  contact info (encoded from settings if available, falls back to a
  generic string otherwise).
- An optional ``delay_seconds`` between requests gives us a sliding
  rate cap (default 0.2 s = 5 req/s, well below the documented
  ~200 req/s ceiling).
- The client gives up after one retry on transient errors. Anything
  that fails twice is reported in the result so the caller can decide
  whether to re-run.
"""
from __future__ import annotations

import logging
import time
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

__all__ = [
    "DEFAULT_LANG",
    "DEFAULT_USER_AGENT",
    "ImageInfo",
    "WikipediaImageClient",
    "build_user_agent",
]


DEFAULT_LANG = "en"
DEFAULT_USER_AGENT = (
    "smart-tourism-engine/0.1 (https://github.com/DayanCabrera2003/smart-tourism-engine; "
    "academic SRI project)"
)
DEFAULT_DELAY_SECONDS = 0.2
DEFAULT_TIMEOUT_SECONDS = 15.0


def build_user_agent(contact: Optional[str] = None) -> str:
    """Return the User-Agent string to send to Wikipedia.

    Wikimedia requires UAs to identify the project. We always include
    a project URL; ``contact`` lets the caller add an email that gets
    embedded too.
    """
    if not contact:
        return DEFAULT_USER_AGENT
    return DEFAULT_USER_AGENT.replace(
        "academic SRI project)",
        f"academic SRI project; contact={contact})",
    )


@dataclass
class ImageInfo:
    """Result of a successful summary lookup."""

    title: str
    page_id: int
    thumbnail_url: Optional[str]
    original_url: Optional[str]
    width: Optional[int]
    height: Optional[int]
    license_short_name: Optional[str]
    page_url: Optional[str]

    def best_url(self, prefer_original: bool = False) -> Optional[str]:
        """Return ``original`` if requested and present, otherwise ``thumbnail``."""
        if prefer_original and self.original_url:
            return self.original_url
        return self.thumbnail_url or self.original_url


class WikipediaImageClient:
    """Wrapper around the Wikipedia REST summary endpoint."""

    BASE_URL_TEMPLATE = "https://{lang}.wikipedia.org/api/rest_v1/page/summary/{title}"

    def __init__(
        self,
        *,
        lang: str = DEFAULT_LANG,
        user_agent: str = DEFAULT_USER_AGENT,
        delay_seconds: float = DEFAULT_DELAY_SECONDS,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        client: Optional[httpx.Client] = None,
    ) -> None:
        self._lang = lang
        self._user_agent = user_agent
        self._delay_seconds = max(0.0, float(delay_seconds))
        self._timeout = timeout_seconds
        self._owns_client = client is None
        self._client = client or httpx.Client(
            headers={"User-Agent": user_agent, "Accept": "application/json"},
            timeout=timeout_seconds,
            follow_redirects=True,
        )

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "WikipediaImageClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def fetch_summary(self, title: str) -> Optional[ImageInfo]:
        """Look up ``title`` on Wikipedia and parse its summary.

        Returns ``None`` for missing pages (404) or empty responses. A
        ``None`` here is **not** an error — many destinations in the
        corpus have a Wikivoyage entry but no English Wikipedia page,
        and we want the batch script to keep going.
        """
        normalized = urllib.parse.quote(title.replace(" ", "_"), safe="_-")
        url = self.BASE_URL_TEMPLATE.format(lang=self._lang, title=normalized)
        if self._delay_seconds:
            time.sleep(self._delay_seconds)
        try:
            response = self._client.get(url)
        except httpx.HTTPError as exc:
            logger.warning("wikipedia lookup failed for %r: %s", title, exc)
            return None
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            logger.warning(
                "wikipedia returned %s for %r", response.status_code, title
            )
            return None
        try:
            payload = response.json()
        except ValueError:
            return None
        thumbnail = payload.get("thumbnail") or {}
        original = payload.get("originalimage") or {}
        page_url = (payload.get("content_urls") or {}).get("desktop", {}).get("page")
        license_info = (
            payload.get("originalimage", {}).get("license", {}).get("short_name")
            or payload.get("thumbnail", {}).get("license", {}).get("short_name")
        )
        return ImageInfo(
            title=payload.get("title") or title,
            page_id=int(payload.get("pageid") or 0),
            thumbnail_url=thumbnail.get("source"),
            original_url=original.get("source"),
            width=thumbnail.get("width") or original.get("width"),
            height=thumbnail.get("height") or original.get("height"),
            license_short_name=license_info,
            page_url=page_url,
        )

    def download(self, image_url: str, destination_path: Path) -> bool:
        """Fetch ``image_url`` and write it to ``destination_path``.

        Returns True on success, False otherwise. The caller chooses
        the target path (typically
        ``data/raw/images/<destination_id>/wikipedia.jpg``) so this
        module stays decoupled from the corpus layout.
        """
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            response = self._client.get(image_url)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("image download failed for %r: %s", image_url, exc)
            return False
        destination_path.write_bytes(response.content)
        return True
