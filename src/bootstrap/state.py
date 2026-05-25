"""Thread-safe progress tracker for the bootstrap pipeline.

A single process-wide :class:`BootstrapTracker` is exposed via
:func:`get_tracker`. The API endpoints read and write the same instance,
and the pipeline runner mutates it while progressing through phases.

Status transitions are linear: idle -> running -> done | error. A new
bootstrap can only start when the current status is idle, done or error
(the latter two are reset back to idle on the next start).
"""
from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass


@dataclass
class PhaseInfo:
    """Static metadata about a phase, declared up front so the UI can
    render the full list before the pipeline even starts."""

    key: str
    label: str


@dataclass
class BootstrapSnapshot:
    """Plain dict-friendly view of the tracker state for JSON serialization."""

    status: str
    phases: list[dict[str, str]]
    phase_index: int
    phase_key: str | None
    phase_label: str | None
    message: str
    percent: float
    log: list[str]
    error: str | None
    started_at: float | None
    finished_at: float | None


class BootstrapTracker:
    """Holds the live state of the bootstrap pipeline.

    Phases are declared via :meth:`begin_run`. Each call to
    :meth:`advance` jumps to the next phase. :meth:`update_message`
    refines the message inside the current phase (e.g. "embed 120/206").
    """

    _LOG_SIZE = 30

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._status: str = "idle"
        self._phases: list[PhaseInfo] = []
        self._phase_index: int = -1
        self._message: str = ""
        self._log: deque[str] = deque(maxlen=self._LOG_SIZE)
        self._error: str | None = None
        self._started_at: float | None = None
        self._finished_at: float | None = None

    # ---- lifecycle ----------------------------------------------------

    def can_start(self) -> bool:
        with self._lock:
            return self._status != "running"

    def begin_run(self, phases: list[PhaseInfo]) -> None:
        with self._lock:
            self._status = "running"
            self._phases = list(phases)
            self._phase_index = -1
            self._message = ""
            self._log.clear()
            self._error = None
            self._started_at = time.time()
            self._finished_at = None

    def advance(self, message: str = "") -> None:
        """Jump to the next phase, optionally seeding its message."""
        with self._lock:
            self._phase_index = min(self._phase_index + 1, len(self._phases) - 1)
            self._message = message
            if self._phase_index >= 0:
                phase = self._phases[self._phase_index]
                self._append_log(f"[{phase.key}] start")
                if message:
                    self._append_log(f"[{phase.key}] {message}")

    def update_message(self, message: str) -> None:
        with self._lock:
            self._message = message
            if self._phase_index >= 0:
                phase = self._phases[self._phase_index]
                self._append_log(f"[{phase.key}] {message}")

    def finish(self) -> None:
        with self._lock:
            self._status = "done"
            self._phase_index = len(self._phases) - 1
            self._message = "Bootstrap completed"
            self._finished_at = time.time()
            self._append_log("done")

    def fail(self, error: str) -> None:
        with self._lock:
            self._status = "error"
            self._error = error
            self._finished_at = time.time()
            self._append_log(f"ERROR: {error}")

    # ---- views --------------------------------------------------------

    def snapshot(self) -> BootstrapSnapshot:
        with self._lock:
            total = len(self._phases) or 1
            done_phases = max(self._phase_index + 1, 0)
            running_pct = (done_phases / total) * 100.0
            if self._status == "running":
                percent = running_pct
            elif self._status == "done":
                percent = 100.0
            elif self._status == "idle":
                percent = 0.0
            else:
                percent = running_pct
            current = (
                self._phases[self._phase_index]
                if 0 <= self._phase_index < len(self._phases)
                else None
            )
            return BootstrapSnapshot(
                status=self._status,
                phases=[{"key": p.key, "label": p.label} for p in self._phases],
                phase_index=self._phase_index,
                phase_key=current.key if current else None,
                phase_label=current.label if current else None,
                message=self._message,
                percent=round(percent, 1),
                log=list(self._log),
                error=self._error,
                started_at=self._started_at,
                finished_at=self._finished_at,
            )

    # ---- internals ----------------------------------------------------

    def _append_log(self, line: str) -> None:
        timestamp = time.strftime("%H:%M:%S")
        self._log.append(f"{timestamp} {line}")


_tracker = BootstrapTracker()


def get_tracker() -> BootstrapTracker:
    """Return the process-wide tracker singleton."""
    return _tracker
