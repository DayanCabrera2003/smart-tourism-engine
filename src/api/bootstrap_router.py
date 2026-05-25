"""FastAPI endpoints for the bootstrap pipeline.

Exposed routes:

* ``GET  /bootstrap/needed``       — should the UI prompt the user?
* ``GET  /bootstrap/status``       — current snapshot of the tracker
* ``POST /bootstrap/start``        — kick off the pipeline in a worker thread
* ``POST /bootstrap/reset/indexes``— drop Qdrant + index.pkl
* ``POST /bootstrap/reset/all``    — drop everything (forces a re-crawl)

The pipeline runs on a background thread so the API stays responsive
during the 5-30 minute embed/crawl phases. After the thread finishes
(success or failure) the per-route ``lru_cache`` instances in
``src.api.main`` are busted so the next request reads fresh data.
"""
from __future__ import annotations

from typing import Callable, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.bootstrap import pipeline, reset, state

router = APIRouter(prefix="/bootstrap", tags=["bootstrap"])

# Cache-busting hook installed by ``src.api.main`` on app startup. The
# router cannot import main directly without creating a cycle, so the
# wiring goes the other way.
_cache_buster: Optional[Callable[[], None]] = None


def register_cache_buster(callback: Callable[[], None]) -> None:
    """Allow the API to plug its cache-clearing function."""
    global _cache_buster
    _cache_buster = callback


def _bust_caches() -> None:
    if _cache_buster is not None:
        _cache_buster()


class NeededResponse(BaseModel):
    needed: bool
    reasons: list[str]


class StatusResponse(BaseModel):
    status: str
    phases: list[dict]
    phase_index: int
    phase_key: str | None
    phase_label: str | None
    message: str
    percent: float
    log: list[str]
    error: str | None


class StartResponse(BaseModel):
    status: str  # "started" or "already_running"


class ResetResponse(BaseModel):
    collections_dropped: list[str]
    files_removed: list[str]
    directories_emptied: list[str]


@router.get("/needed", response_model=NeededResponse)
def bootstrap_needed() -> NeededResponse:
    needed, reasons = pipeline.is_bootstrap_needed()
    return NeededResponse(needed=needed, reasons=reasons)


@router.get("/status", response_model=StatusResponse)
def bootstrap_status() -> StatusResponse:
    snap = state.get_tracker().snapshot()
    return StatusResponse(
        status=snap.status,
        phases=snap.phases,
        phase_index=snap.phase_index,
        phase_key=snap.phase_key,
        phase_label=snap.phase_label,
        message=snap.message,
        percent=snap.percent,
        log=snap.log,
        error=snap.error,
    )


@router.post("/start", response_model=StartResponse)
def bootstrap_start() -> StartResponse:
    tracker = state.get_tracker()
    if not tracker.can_start():
        return StartResponse(status="already_running")
    pipeline.run_in_thread(tracker, on_done=_bust_caches)
    return StartResponse(status="started")


@router.post("/reset/indexes", response_model=ResetResponse)
def bootstrap_reset_indexes() -> ResetResponse:
    tracker = state.get_tracker()
    if not tracker.can_start():
        raise HTTPException(
            status_code=409,
            detail="bootstrap is running; wait for it to finish before resetting",
        )
    report = reset.reset_indexes()
    _bust_caches()
    return ResetResponse(
        collections_dropped=report.collections_dropped,
        files_removed=report.files_removed,
        directories_emptied=report.directories_emptied,
    )


@router.post("/reset/all", response_model=ResetResponse)
def bootstrap_reset_all() -> ResetResponse:
    tracker = state.get_tracker()
    if not tracker.can_start():
        raise HTTPException(
            status_code=409,
            detail="bootstrap is running; wait for it to finish before resetting",
        )
    report = reset.reset_all()
    _bust_caches()
    return ResetResponse(
        collections_dropped=report.collections_dropped,
        files_removed=report.files_removed,
        directories_emptied=report.directories_emptied,
    )
