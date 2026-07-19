"""Tests for extraction_journal module."""

import hashlib
import json
import os
import tempfile
from pathlib import Path
from unittest import TestCase

from spirosearch.extraction_journal import (
    EXTRACTION_STATUSES,
    ExtractionCheckpoint,
    ExtractionJournal,
)


class TestExtractionCheckpoint(TestCase):
    def test_valid_statuses(self):
        for status in EXTRACTION_STATUSES:
            cp = ExtractionCheckpoint(doi="10.1234/test", status=status)
            assert cp.status == status

    def test_invalid_status_raises(self):
        with self.assertRaises(ValueError):
            ExtractionCheckpoint(doi="10.1234/test", status="invalid_status")

    def test_to_dict(self):
        cp = ExtractionCheckpoint(
            doi="10.1234/test",
            status="completed",
            claim_count=5,
            review_count=2,
            extractor_version="REGEX_V1",
        )
        d = cp.to_dict()
        assert d["schema_version"] == "v29.extraction_journal.v1"
        assert d["doi"] == "10.1234/test"
        assert d["status"] == "completed"
        assert d["claim_count"] == 5
        assert d["review_count"] == 2


class TestExtractionJournal(TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.journal = ExtractionJournal(self.tmpdir)

    def test_initialize_creates_journal(self):
        """Journal initialization should create the JSONL file."""
        # Create minimal PaperGroup-like data
        groups = _make_mock_groups(["10.1234/a", "10.1234/b"])
        self.journal.initialize(groups)
        assert self.journal.journal_path.exists()

    def test_initialize_sets_pending(self):
        """All DOIs should be set to 'pending' after initialization."""
        groups = _make_mock_groups(["10.1234/a", "10.1234/b"])
        self.journal.initialize(groups)
        state = self.journal._current_state()
        assert state["10.1234/a"].status == "pending"
        assert state["10.1234/b"].status == "pending"

    def test_mark_running_then_completed(self):
        """Full lifecycle: pending → running → completed."""
        groups = _make_mock_groups(["10.1234/a"])
        self.journal.initialize(groups)

        self.journal.mark_running("10.1234/a", extractor_version="REGEX_V1")
        state = self.journal._current_state()
        assert state["10.1234/a"].status == "running"
        assert state["10.1234/a"].pid == os.getpid()

        self.journal.mark_completed("10.1234/a", claim_count=3, review_count=1)
        state = self.journal._current_state()
        assert state["10.1234/a"].status == "completed"
        assert state["10.1234/a"].claim_count == 3

    def test_mark_failed(self):
        """Failed extraction should be tracked."""
        groups = _make_mock_groups(["10.1234/a"])
        self.journal.initialize(groups)
        self.journal.mark_running("10.1234/a")
        self.journal.mark_failed("10.1234/a", error="pdfplumber crashed")
        state = self.journal._current_state()
        assert state["10.1234/a"].status == "failed"
        assert state["10.1234/a"].error_message == "pdfplumber crashed"

    def test_mark_partial_failure(self):
        """Partial failure: main completed but SI failed."""
        groups = _make_mock_groups(["10.1234/a"])
        self.journal.initialize(groups)
        self.journal.mark_running("10.1234/a")
        self.journal.mark_failed("10.1234/a", error="SI PDF failed", partial=True,
                                 main_status="completed", si_status="failed")
        state = self.journal._current_state()
        assert state["10.1234/a"].status == "partial_failure"

    def test_mark_interrupted(self):
        """Interrupted DOIs should be detectable when PID is dead."""
        groups = _make_mock_groups(["10.1234/a"])
        self.journal.initialize(groups)
        self.journal.mark_running("10.1234/a")

        # Current process PID is alive, so detect_interrupted won't flag it
        # But the mechanism works correctly — verify with a dead PID test
        interrupted = self.journal.detect_interrupted()
        # Our own PID is valid, so no interrupted entries detected
        # This is the correct behavior — only dead PIDs trigger interrupted
        # (See test_detect_interrupted_with_dead_pid for actual detection)

    def test_detect_interrupted_with_dead_pid(self):
        """Detect interrupted when PID doesn't exist."""
        groups = _make_mock_groups(["10.1234/x"])
        self.journal.initialize(groups)

        # Manually write a running entry with a dead PID
        fake_checkpoint = ExtractionCheckpoint(
            doi="10.1234/x",
            status="running",
            pid=999999999,  # impossible PID
        )
        self.journal._append(fake_checkpoint)

        interrupted = self.journal.detect_interrupted()
        assert "10.1234/x" in interrupted

    def test_get_retry_candidates_failed(self):
        """Retry candidates should include failed and interrupted DOIs."""
        groups = _make_mock_groups(["10.1234/a", "10.1234/b"])
        self.journal.initialize(groups)

        self.journal.mark_running("10.1234/a")
        self.journal.mark_failed("10.1234/a", error="test error")

        # With failed_only=False, pending DOIs are also included
        # Since 10.1234/b is still pending, it's included too
        candidates = self.journal.get_retry_candidates(groups, failed_only=False)
        assert len(candidates) >= 1
        # With failed_only=True, only failed/interrupted DOIs
        candidates_failed = self.journal.get_retry_candidates(groups, failed_only=True)
        assert len(candidates_failed) == 1
        assert candidates_failed[0].doi == "10.1234/a"

    def test_get_retry_candidates_force_doi(self):
        """Force DOI should override completed status."""
        groups = _make_mock_groups(["10.1234/a", "10.1234/b"])
        self.journal.initialize(groups)
        # Complete both DOIs so they're not pending
        self.journal.mark_running("10.1234/a")
        self.journal.mark_completed("10.1234/a", claim_count=5)
        self.journal.mark_running("10.1234/b")
        self.journal.mark_completed("10.1234/b", claim_count=3)

        # Force re-extract only 10.1234/a
        candidates = self.journal.get_retry_candidates(
            groups,
            force_dois=("10.1234/a",),
            failed_only=True,  # only force_dois, no pending/failed
        )
        assert len(candidates) == 1
        assert candidates[0].doi == "10.1234/a"

    def test_summary_structure(self):
        """Summary should include status counts and per-DOI details."""
        groups = _make_mock_groups(["10.1234/a"])
        self.journal.initialize(groups)
        self.journal.mark_running("10.1234/a")
        self.journal.mark_completed("10.1234/a", claim_count=5)

        summary = self.journal.summary()
        assert summary["schema_version"] == "v29.extraction_journal_summary.v1"
        assert summary["total_dois"] == 1
        assert summary["status_counts"]["completed"] == 1
        assert len(summary["entries"]) == 1
        assert len(summary["doi_statuses"]) == 1

    def test_skip_already_completed(self):
        """Initialize should not overwrite existing completed entries."""
        groups = _make_mock_groups(["10.1234/a"])
        self.journal.initialize(groups)
        self.journal.mark_running("10.1234/a")
        self.journal.mark_completed("10.1234/a", claim_count=5)

        # Re-initialize — should not reset to pending
        self.journal.initialize(groups)
        state = self.journal._current_state()
        assert state["10.1234/a"].status == "completed"


# ---------------------------------------------------------------------------
# Helper to create mock PaperGroups for testing
# ---------------------------------------------------------------------------

def _make_mock_groups(dois: list[str]) -> tuple:
    """Create minimal PaperGroup-like objects for testing.

    Note: PaperGroup is frozen=True, so we need all fields.
    We use a simpler approach: just pass DOI strings and mock the scan.
    """
    from spirosearch.paper_vault import PaperGroup, PaperAttachment

    groups = []
    for doi in dois:
        folder_hash = hashlib.sha256(doi.strip().casefold().encode("utf-8")).hexdigest()[:8]
        groups.append(PaperGroup(
            paper_folder=folder_hash,
            doi=doi,
            main_pdf=Path("/fake") / folder_hash / "main.pdf",
            si_pdf=None,
            has_si=False,
            main_sha256="abc123" + "0" * 57,  # fake SHA256
            si_sha256=None,
            license="test-license",
            downloaded_at="2026-07-19",
            source_rights="test-rights",
            attachments=(
                PaperAttachment(
                    filename="main.pdf",
                    source_label="main",
                    path=Path("/fake") / folder_hash / "main.pdf",
                    sha256="abc123" + "0" * 57,
                    ocr_status="not_attempted",
                ),
            ),
        ))
    return tuple(groups)
