import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from spirosearch.artifact_repository import JsonArtifactRepository
from spirosearch.artifact_validation import validate_artifact_run
from spirosearch.paper_ingest import PdfTextParser, run_paper_ingest
from spirosearch.paper_vault import doi_folder_name


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_text_pdf_group(root: Path, doi: str, *, has_si: bool = True) -> Path:
    folder = root / doi_folder_name(doi)
    folder.mkdir(parents=True)
    main = b"Title: Fixture Paper\nThe HTL material Spiro-OMeTAD has HOMO = -5.22 eV measured in text.\n"
    si = b"Supplemental table reports PCE = 22.4% for Spiro-OMeTAD.\n"
    (folder / "main.pdf").write_bytes(main)
    if has_si:
        (folder / "si.pdf").write_bytes(si)
    manifest = {
        "doi": doi,
        "main_sha256": _sha256(main),
        "si_sha256": _sha256(si) if has_si else None,
        "has_si": has_si,
        "license": "CC-BY-4.0",
        "downloaded_at": "2026-07-12T00:00:00+00:00",
        "source_rights": "open fixture",
    }
    (folder / "source-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return folder


class PaperIngestTests(unittest.TestCase):
    def test_text_backed_pdf_parser_maps_to_raw_document_chunks(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            folder = _write_text_pdf_group(root, "10.1234/parser", has_si=False)
            group = next(iter(__import__("spirosearch.paper_vault").paper_vault.PaperVault(root).scan()))

            document = PdfTextParser().parse(group.paper_folder, group.doi, folder / "main.pdf", source="main")

            self.assertEqual(document.doi, "10.1234/parser")
            self.assertEqual(document.artifact_type, "pdf")
            self.assertEqual(document.chunks[0].page, 1)
            self.assertIn("HOMO", document.chunks[0].text)
            self.assertIn("source=main", document.chunks[0].span)

    def test_run_paper_ingest_writes_manifest_discovered_artifacts(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "papers"
            output_dir = Path(temp_dir) / "out"
            root.mkdir()
            _write_text_pdf_group(root, "10.1234/ingest", has_si=True)

            result = run_paper_ingest(root, output_dir, extractor="regex", use_legacy_parser=True)

            self.assertEqual(result["paper_count"], 1)
            manifest = json.loads((output_dir / "run-manifest.json").read_text(encoding="utf-8"))
            kinds = {artifact["kind"] for artifact in manifest["artifacts"]}
            self.assertEqual(
                kinds,
                {
                    "literature_claims",
                    "paper_cross_ref_report",
                    "extraction_journal",
                    "extraction_journal_status",
                    "paper_vault_summary",
                    "review_queue",
                    "source_assets",
                },
            )
            self.assertEqual(validate_artifact_run(output_dir).status, "valid")

            repository = JsonArtifactRepository.from_output_dir(output_dir)
            claims = repository.read_jsonl("literature_claims")
            reviews = repository.read_jsonl("review_queue")
            journal_status = repository.read_jsonl("extraction_journal_status")
            vault_summary = repository.read_json("paper_vault_summary")

            self.assertTrue(claims.available)
            self.assertGreaterEqual(len(claims.records), 2)
            # V30: regex confidence now includes context bonus; some claims may be accepted
            review_statuses = {record["review_status"] for record in claims.records}
            self.assertTrue(
                review_statuses.issubset({"needs_review", "accepted"}),
                f"unexpected review statuses: {review_statuses}"
            )
            self.assertTrue(all(record["method"] == "regex_text_pattern" for record in claims.records))
            self.assertTrue(reviews.available)
            # V30: only claims below confidence_threshold enter review queue
            self.assertGreaterEqual(len(reviews.records), 1)
            self.assertTrue(journal_status.available)
            self.assertGreaterEqual(len(journal_status.records), 2)
            self.assertTrue(vault_summary.available)
            self.assertEqual(vault_summary.payload["papers"][0]["paper_folder"], doi_folder_name("10.1234/ingest"))


if __name__ == "__main__":
    unittest.main()
