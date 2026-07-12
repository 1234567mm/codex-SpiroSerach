import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from spirosearch.artifact_validation import validate_artifact_run
from spirosearch.cli import _main_paper_ingest
from spirosearch.contracts import EXIT_SUCCESS
from spirosearch.paper_vault import doi_folder_name


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_group(root: Path, doi: str) -> None:
    folder = root / doi_folder_name(doi)
    folder.mkdir(parents=True)
    main = b"The paper reports HOMO = -5.22 eV for Spiro-OMeTAD.\n"
    (folder / "main.pdf").write_bytes(main)
    (folder / "source-manifest.json").write_text(
        json.dumps(
            {
                "doi": doi,
                "main_sha256": _sha256(main),
                "si_sha256": None,
                "has_si": False,
                "license": "CC-BY-4.0",
                "downloaded_at": "2026-07-12T00:00:00+00:00",
                "source_rights": "open fixture",
            }
        ),
        encoding="utf-8",
    )


class PaperIngestCliTests(unittest.TestCase):
    def test_cli_runs_regex_ingest_and_optional_obsidian_writer(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            paper_dir = root / "papers"
            output_dir = root / "out"
            obsidian_dir = root / "obsidian"
            paper_dir.mkdir()
            _write_group(paper_dir, "10.1234/cli")

            exit_code = _main_paper_ingest(
                [
                    "--paper-dir",
                    str(paper_dir),
                    "--output-dir",
                    str(output_dir),
                    "--extractor",
                    "regex",
                    "--obsidian-dir",
                    str(obsidian_dir),
                ]
            )

            self.assertEqual(exit_code, EXIT_SUCCESS)
            self.assertEqual(validate_artifact_run(output_dir).status, "valid")
            manifest = json.loads((output_dir / "run-manifest.json").read_text(encoding="utf-8"))
            self.assertIn("obsidian_notes", {artifact["kind"] for artifact in manifest["artifacts"]})
            self.assertTrue(list((obsidian_dir / "papers").glob("*.md")))


if __name__ == "__main__":
    unittest.main()
