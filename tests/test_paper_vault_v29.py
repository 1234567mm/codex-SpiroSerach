"""Tests for paper_vault V29 multi-SI support."""

import hashlib
import json
import tempfile
from pathlib import Path
from unittest import TestCase

from spirosearch.paper_vault import (
    MANIFEST_SCHEMA_VERSION,
    PaperAttachment,
    PaperGroup,
    PaperVault,
    doi_folder_name,
)


class TestDoiFolderName(TestCase):
    def test_basic_doi(self):
        result = doi_folder_name("10.1038/s41586-024-12345")
        assert len(result) == 8
        assert all(c in "0123456789abcdef" for c in result)

    def test_casefold_normalization(self):
        """DOI case should be normalized for hashing."""
        upper = doi_folder_name("10.1038/ABC123")
        lower = doi_folder_name("10.1038/abc123")
        assert upper == lower


class TestPaperAttachment(TestCase):
    def test_attachment_fields(self):
        att = PaperAttachment(
            filename="si-1.pdf",
            source_label="si-1",
            path=Path("/test/si-1.pdf"),
            sha256="a" * 64,
            ocr_status="not_attempted",
        )
        assert att.filename == "si-1.pdf"
        assert att.source_label == "si-1"
        assert att.ocr_status == "not_attempted"


class TestPaperVaultLegacyManifest(TestCase):
    """Test backward compatibility with legacy source-manifest.json format."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_scan_legacy_manifest(self):
        """Legacy manifest (no schema_version) should still work."""
        doi = "10.1038/test123"
        folder = doi_folder_name(doi)
        paper_dir = Path(self.tmpdir) / folder
        paper_dir.mkdir()

        # Create a minimal PDF (not a real one, just bytes)
        main_pdf = paper_dir / "main.pdf"
        pdf_hash = hashlib.sha256(b"fake pdf content").hexdigest()
        main_pdf.write_bytes(b"fake pdf content")

        manifest = {
            "doi": doi,
            "main_sha256": pdf_hash,
            "si_sha256": None,
            "has_si": False,
            "license": "test-license",
            "downloaded_at": "2026-07-19",
            "source_rights": "test-rights",
        }
        (paper_dir / "source-manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        vault = PaperVault(self.tmpdir)
        groups = vault.scan()
        assert len(groups) == 1
        assert groups[0].doi == doi
        assert groups[0].has_si is False
        assert groups[0].manifest_schema_version == "legacy"

    def test_scan_legacy_manifest_with_si(self):
        """Legacy manifest with single SI should populate attachments."""
        doi = "10.1038/si-test"
        folder = doi_folder_name(doi)
        paper_dir = Path(self.tmpdir) / folder
        paper_dir.mkdir()

        main_pdf = paper_dir / "main.pdf"
        si_pdf = paper_dir / "si.pdf"
        main_hash = hashlib.sha256(b"main content").hexdigest()
        si_hash = hashlib.sha256(b"si content").hexdigest()
        main_pdf.write_bytes(b"main content")
        si_pdf.write_bytes(b"si content")

        manifest = {
            "doi": doi,
            "main_sha256": main_hash,
            "si_sha256": si_hash,
            "has_si": True,
            "license": "test-license",
            "downloaded_at": "2026-07-19",
            "source_rights": "test-rights",
        }
        (paper_dir / "source-manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        vault = PaperVault(self.tmpdir)
        groups = vault.scan()
        assert len(groups) == 1
        assert groups[0].has_si is True
        assert groups[0].si_pdf is not None
        assert len(groups[0].attachments) == 2  # main + si


class TestPaperVaultV29Manifest(TestCase):
    """Test V29 source-manifest.json with schema_version and si_files array."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def test_scan_v29_manifest_multi_si(self):
        """V29 manifest with si_files array should populate multiple attachments."""
        doi = "10.1038/multi-si"
        folder = doi_folder_name(doi)
        paper_dir = Path(self.tmpdir) / folder
        paper_dir.mkdir()

        main_pdf = paper_dir / "main.pdf"
        si1_pdf = paper_dir / "si-1.pdf"
        si2_pdf = paper_dir / "si-synthesis.pdf"
        main_hash = hashlib.sha256(b"main").hexdigest()
        si1_hash = hashlib.sha256(b"si1").hexdigest()
        si2_hash = hashlib.sha256(b"si2").hexdigest()
        main_pdf.write_bytes(b"main")
        si1_pdf.write_bytes(b"si1")
        si2_pdf.write_bytes(b"si2")

        manifest = {
            "schema_version": "v29.source_manifest.v1",
            "doi": doi,
            "main_sha256": main_hash,
            "license": "CC-BY-4.0",
            "downloaded_at": "2026-07-19T12:00:00+00:00",
            "source_rights": "open-access",
            "si_files": [
                {"filename": "si-1.pdf", "source_label": "si-1", "sha256": si1_hash},
                {"filename": "si-synthesis.pdf", "source_label": "si-synthesis", "sha256": si2_hash, "ocr_status": "not_attempted"},
            ],
        }
        (paper_dir / "source-manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        vault = PaperVault(self.tmpdir)
        groups = vault.scan()
        assert len(groups) == 1
        assert groups[0].manifest_schema_version == "v29.source_manifest.v1"
        assert len(groups[0].attachments) == 3  # main + si-1 + si-synthesis
        assert groups[0].attachments[0].source_label == "main"
        assert groups[0].attachments[1].source_label == "si-1"
        assert groups[0].attachments[2].source_label == "si-synthesis"

    def test_scan_v29_manifest_no_si(self):
        """V29 manifest with empty si_files should have has_si=False."""
        doi = "10.1038/no-si"
        folder = doi_folder_name(doi)
        paper_dir = Path(self.tmpdir) / folder
        paper_dir.mkdir()

        main_pdf = paper_dir / "main.pdf"
        main_hash = hashlib.sha256(b"main").hexdigest()
        main_pdf.write_bytes(b"main")

        manifest = {
            "schema_version": "v29.source_manifest.v1",
            "doi": doi,
            "main_sha256": main_hash,
            "license": "CC-BY-4.0",
            "downloaded_at": "2026-07-19",
            "source_rights": "open-access",
            "si_files": [],
        }
        (paper_dir / "source-manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8"
        )

        vault = PaperVault(self.tmpdir)
        groups = vault.scan()
        assert len(groups) == 1
        assert groups[0].has_si is False
        assert len(groups[0].attachments) == 1  # just main

    def test_to_summary_includes_attachments(self):
        """PaperGroup.to_summary should include V29 attachment info."""
        group = PaperGroup(
            paper_folder="test1234",
            doi="10.1234/test",
            main_pdf=Path("/fake/main.pdf"),
            si_pdf=Path("/fake/si.pdf"),
            has_si=True,
            main_sha256="a" * 64,
            si_sha256="b" * 64,
            license="CC-BY-4.0",
            downloaded_at="2026-07-19",
            source_rights="open-access",
            attachments=(
                PaperAttachment("main.pdf", "main", Path("/fake/main.pdf"), "a" * 64, "not_attempted"),
                PaperAttachment("si.pdf", "si", Path("/fake/si.pdf"), "b" * 64, "not_attempted"),
            ),
        )
        summary = group.to_summary()
        assert summary["attachment_count"] == 2
        assert len(summary["attachments"]) == 2
        assert summary["manifest_schema_version"] == MANIFEST_SCHEMA_VERSION
