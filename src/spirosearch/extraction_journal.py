"""Append-only extraction state tracker for paper ingest pipeline.

This module implements a paper_extraction_status journal that enables
checkpoint/resume, crash detection, and per-DOI status tracking.  The
journal is a JSONL file where each line records a state transition for
a specific DOI.

Status model: pending → running → completed | skipped | partial_failure | failed
Interrupted: detected at next launch when a DOI is 'running' but the
  lock file's PID no longer exists.

CLI integration: --resume, --failed-only, --force-doi <doi>.

No scoring, recommendation, or decision logic is emitted from this module.
"""

from __future__ import annotations

import json
import os
import time
import ctypes
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from spirosearch.paper_vault import PaperGroup


# ---------------------------------------------------------------------------
# Status model
# ---------------------------------------------------------------------------

EXTRACTION_STATUSES = (
    "pending",
    "running",
    "completed",
    "skipped",
    "partial_failure",
    "failed",
    "interrupted",
)


# ---------------------------------------------------------------------------
# Checkpoint record
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExtractionCheckpoint:
    """A single state transition record for a DOI."""

    doi: str
    status: str
    started_at: str | None = None       # ISO 8601
    completed_at: str | None = None     # ISO 8601
    main_status: str | None = None      # pending/completed/failed/skipped
    si_status: str | None = None        # pending/completed/failed/skipped/null
    claim_count: int = 0
    review_count: int = 0
    error_message: str | None = None
    extractor_version: str | None = None
    input_hash: str | None = None       # DOI + PDF hash composite
    pid: int | None = None              # process ID when status=running

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "v29.extraction_journal.v1",
            "doi": self.doi,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "main_status": self.main_status,
            "si_status": self.si_status,
            "claim_count": self.claim_count,
            "review_count": self.review_count,
            "error_message": self.error_message,
            "extractor_version": self.extractor_version,
            "input_hash": self.input_hash,
            "pid": self.pid,
        }

    def __post_init__(self) -> None:
        if self.status not in EXTRACTION_STATUSES:
            raise ValueError(f"unknown extraction status: {self.status}")


# ---------------------------------------------------------------------------
# Journal
# ---------------------------------------------------------------------------

class ExtractionJournal:
    """Append-only extraction state tracker.

    The journal file is a JSONL where each line is a ExtractionCheckpoint
    record.  A companion lock file (.{journal_name}.lock) records the PID
    of the currently running process for crash detection.

    Usage:
        journal = ExtractionJournal(Path("outputs/extraction-journal"))
        journal.initialize(groups)    # sets all DOIs to 'pending'
        journal.mark_running(doi)     # before extraction starts
        journal.mark_completed(doi, claim_count=5, review_count=2)
        # ... or journal.mark_failed(doi, error="pdfplumber crashed")
        # On next launch:
        interrupted = journal.detect_interrupted()
        journal.mark_interrupted(interrupted_dois)
    """

    def __init__(self, journal_dir: str | Path) -> None:
        self.journal_dir = Path(journal_dir)
        self.journal_dir.mkdir(parents=True, exist_ok=True)
        self.journal_path = self.journal_dir / "paper_extraction_status.jsonl"
        self.lock_path = self.journal_dir / ".extraction_journal.lock"

    # --- Initialization --------------------------------------------------

    def initialize(self, groups: tuple[PaperGroup, ...]) -> None:
        """Set all DOIs from PaperVault scan to 'pending'.

        If the journal already exists, this does NOT overwrite it;
        it only adds DOIs that are not yet tracked.
        """
        existing = self._current_state()
        for group in groups:
            if group.doi not in existing:
                self._append(ExtractionCheckpoint(
                    doi=group.doi,
                    status="pending",
                    pid=None,
                ))

    # --- State transitions ------------------------------------------------

    def mark_running(self, doi: str, *, extractor_version: str | None = None) -> None:
        """Mark a DOI as 'running' with current PID."""
        self._write_lock(doi)
        self._append(ExtractionCheckpoint(
            doi=doi,
            status="running",
            started_at=_now_iso(),
            pid=os.getpid(),
            extractor_version=extractor_version,
        ))

    def mark_completed(
        self,
        doi: str,
        *,
        claim_count: int = 0,
        review_count: int = 0,
        main_status: str = "completed",
        si_status: str | None = "completed",
        extractor_version: str | None = None,
    ) -> None:
        """Mark a DOI as 'completed' after successful extraction."""
        self._clear_lock(doi)
        self._append(ExtractionCheckpoint(
            doi=doi,
            status="completed",
            completed_at=_now_iso(),
            claim_count=claim_count,
            review_count=review_count,
            main_status=main_status,
            si_status=si_status,
            extractor_version=extractor_version,
            pid=None,
        ))

    def mark_failed(
        self,
        doi: str,
        *,
        error: str,
        partial: bool = False,
        main_status: str | None = None,
        si_status: str | None = None,
    ) -> None:
        """Mark a DOI as 'failed' or 'partial_failure'."""
        self._clear_lock(doi)
        status = "partial_failure" if partial else "failed"
        self._append(ExtractionCheckpoint(
            doi=doi,
            status=status,
            completed_at=_now_iso(),
            error_message=error,
            main_status=main_status,
            si_status=si_status,
            pid=None,
        ))

    def mark_skipped(self, doi: str, *, reason: str = "already_completed") -> None:
        """Mark a DOI as 'skipped' (already extracted)."""
        self._append(ExtractionCheckpoint(
            doi=doi,
            status="skipped",
            completed_at=_now_iso(),
            error_message=reason,
            pid=None,
        ))

    def mark_interrupted(self, dois: Iterable[str]) -> None:
        """Mark DOIs as 'interrupted' after detecting stale 'running'."""
        for doi in dois:
            self._clear_lock(doi)
            self._append(ExtractionCheckpoint(
                doi=doi,
                status="interrupted",
                error_message="process_crashed_or_killed",
                pid=None,
            ))

    # --- Crash detection --------------------------------------------------

    def detect_interrupted(self) -> tuple[str, ...]:
        """Identify DOIs stuck in 'running' whose PID no longer exists.

        Returns DOIs that should be marked as 'interrupted'.
        """
        current = self._current_state()
        interrupted: list[str] = []
        for doi, checkpoint in current.items():
            if checkpoint.status != "running":
                continue
            pid = checkpoint.pid
            if pid is None:
                interrupted.append(doi)
                continue
            if not _pid_exists(pid):
                interrupted.append(doi)
        return tuple(interrupted)

    # --- Retry selection --------------------------------------------------

    def get_retry_candidates(
        self,
        groups: tuple[PaperGroup, ...],
        *,
        force_dois: tuple[str, ...] = (),
        failed_only: bool = False,
    ) -> tuple[PaperGroup, ...]:
        """Return PaperGroups that need re-extraction.

        By default, returns failed + interrupted + force_dois.
        With failed_only=True, returns only failed + interrupted.
        Without any filters, also includes pending.
        """
        current = self._current_state()
        retry_dois: set[str] = set()

        # Always include force_dois
        retry_dois.update(force_dois)

        # Include failed, interrupted, and (optionally) pending
        for doi, checkpoint in current.items():
            if checkpoint.status in ("failed", "interrupted", "partial_failure"):
                retry_dois.add(doi)
            elif not failed_only and checkpoint.status == "pending":
                retry_dois.add(doi)

        # Filter groups by retry set
        return tuple(g for g in groups if g.doi in retry_dois)

    # --- Summary for frontend ---------------------------------------------

    def summary(self) -> dict[str, Any]:
        """Return a summary dict suitable for the artifact viewer."""
        current = self._current_state()
        counts: dict[str, int] = {}
        for status in EXTRACTION_STATUSES:
            counts[status] = 0
        entries: list[dict[str, Any]] = []
        for doi, checkpoint in sorted(current.items()):
            counts[checkpoint.status] = counts.get(checkpoint.status, 0) + 1
            entries.append({
                "schema_version": "v29.extraction_journal.v1",
                "doi": doi,
                "status": checkpoint.status,
                "claim_count": checkpoint.claim_count,
                "review_count": checkpoint.review_count,
                "main_status": checkpoint.main_status,
                "si_status": checkpoint.si_status,
                "extractor_version": checkpoint.extractor_version,
                "error_message": checkpoint.error_message,
            })
        return {
            "schema_version": "v29.extraction_journal_summary.v1",
            "total_dois": len(current),
            "status_counts": counts,
            "entries": entries,
            "doi_statuses": entries,
        }

    # --- Internal helpers -------------------------------------------------

    def _current_state(self) -> dict[str, ExtractionCheckpoint]:
        """Read the journal and return the latest state per DOI."""
        state: dict[str, ExtractionCheckpoint] = {}
        if not self.journal_path.exists():
            return state
        for line in self.journal_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            payload = json.loads(line)
            payload.pop("schema_version", None)
            checkpoint = ExtractionCheckpoint(**payload)
            state[checkpoint.doi] = checkpoint  # latest entry wins
        return state

    def _append(self, checkpoint: ExtractionCheckpoint) -> None:
        """Append a checkpoint record to the JSONL journal."""
        line = json.dumps(checkpoint.to_dict(), separators=(",", ":")) + "\n"
        self.journal_path.write_text(
            self.journal_path.read_text(encoding="utf-8") + line if self.journal_path.exists() else line,
            encoding="utf-8",
        )

    def _doi_lock_path(self, doi: str) -> Path:
        """Get a filesystem-safe lock path for the given DOI."""
        # Replace dots and slashes with underscores to avoid path issues
        safe_name = doi.replace(".", "_").replace("/", "_").replace("\\", "_")
        return self.journal_dir / f".lock.{safe_name}"

    def _write_lock(self, doi: str) -> None:
        """Write a PID lock file for the given DOI."""
        lock_content = json.dumps({
            "doi": doi,
            "pid": os.getpid(),
            "started_at": _now_iso(),
        })
        doi_lock = self._doi_lock_path(doi)
        doi_lock.write_text(lock_content, encoding="utf-8")

    def _clear_lock(self, doi: str) -> None:
        """Remove the PID lock file for the given DOI."""
        doi_lock = self._doi_lock_path(doi)
        if doi_lock.exists():
            doi_lock.unlink()


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    """Return current UTC time as ISO 8601 string."""
    from datetime import UTC, datetime
    return datetime.now(UTC).isoformat()


def _pid_exists(pid: int) -> bool:
    """Check if a process with the given PID still exists."""
    if os.name == "nt":
        return _pid_exists_windows(pid)
    try:
        os.kill(pid, 0)  # signal 0 does not kill, just checks existence
        return True
    except OSError:
        return False


def _pid_exists_windows(pid: int) -> bool:
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return False
    try:
        exit_code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)
