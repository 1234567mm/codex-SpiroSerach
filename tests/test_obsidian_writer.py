import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from spirosearch.artifacts import build_run_manifest, write_json_artifact, write_jsonl_artifact
from spirosearch.obsidian_writer import ObsidianWriter


class ObsidianWriterTests(unittest.TestCase):
    def test_writer_consumes_manifest_artifacts_and_upserts_notes(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            output_dir = root / "run"
            vault_dir = root / "obsidian"
            output_dir.mkdir()
            doi = "10.1234/obsidian"
            folder = hashlib.sha256(doi.casefold().encode("utf-8")).hexdigest()[:8]
            common = {
                "run_id": "obsidian-run",
                "input_hash": "input-hash",
                "generated_at": "2026-07-12T00:00:00+00:00",
                "producer_version": "obsidian-test",
            }
            artifacts = [
                write_json_artifact(
                    output_dir,
                    "paper-vault-summary.json",
                    {
                        "schema_version": "v18.paper_vault_summary.v1",
                        "paper_count": 1,
                        "papers": [
                            {
                                "doi": doi,
                                "paper_folder": folder,
                                "has_si": False,
                                "main_sha256": "a" * 64,
                                "si_sha256": None,
                                "license": "CC-BY-4.0",
                                "source_rights": "open fixture",
                            }
                        ],
                    },
                    kind="paper_vault_summary",
                    **common,
                ),
                write_jsonl_artifact(
                    output_dir,
                    "literature-claims.jsonl",
                    [
                        {
                            "schema_version": "v13.literature_claim.v1",
                            "claim_id": "claim-1",
                            "asset_id": "asset-1",
                            "chunk_id": "chunk-1",
                            "doi": doi,
                            "property": "homo_ev",
                            "value": -5.22,
                            "unit": "eV",
                            "text_sha256": "b" * 64,
                            "method": "regex_text_pattern",
                            "conditions": {"material": "Spiro-OMeTAD"},
                            "extractor_version": "REGEX",
                            "review_status": "needs_review",
                        }
                    ],
                    kind="literature_claims",
                    **common,
                ),
            ]
            build_run_manifest(artifacts, **common).write_json(output_dir)

            first = ObsidianWriter().write_from_repository(output_dir, vault_dir)
            second = ObsidianWriter().write_from_repository(output_dir, vault_dir)

            self.assertEqual(first["note_count"], second["note_count"])
            paper_notes = list((vault_dir / "papers").glob("*.md"))
            molecule_notes = list((vault_dir / "molecules").glob("*.md"))
            property_notes = list((vault_dir / "properties").glob("*.md"))
            self.assertEqual(len(paper_notes), 1)
            self.assertEqual(len(molecule_notes), 1)
            self.assertEqual(len(property_notes), 1)
            paper_text = paper_notes[0].read_text(encoding="utf-8")
            molecule_text = molecule_notes[0].read_text(encoding="utf-8")
            self.assertIn("claims_count: 1", paper_text)
            self.assertIn("[[Spiro-OMeTAD]]", paper_text)
            self.assertIn(f"[[{folder}]]", molecule_text)
            self.assertIn("No supplementary information provided.", paper_text)


if __name__ == "__main__":
    unittest.main()
