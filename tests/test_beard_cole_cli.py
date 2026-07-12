import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from spirosearch.artifact_repository import JsonArtifactRepository
from spirosearch.artifact_validation import validate_artifact_run
from spirosearch.cli import main


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "beard_cole"


class BeardColeCliTests(unittest.TestCase):
    def test_beard_cole_import_writes_manifest_discovered_run_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "run"
            with patch(
                "sys.argv",
                [
                    "spirosearch",
                    "beard-cole-import",
                    "--source-file",
                    str(FIXTURE_DIR / "psc_records.json"),
                    "--source-manifest",
                    str(FIXTURE_DIR / "source-manifest.json"),
                    "--output-dir",
                    str(output_dir),
                ],
            ):
                self.assertEqual(main(), 0)

            repository = JsonArtifactRepository.from_output_dir(output_dir)
            manifest = repository.manifest()
            kinds = {artifact["kind"] for artifact in manifest["artifacts"]}
            self.assertEqual(
                kinds,
                {
                    "device_evidence",
                    "training_snapshot",
                    "data_quality_report",
                    "model_evaluation",
                    "acquisition_breakdown",
                },
            )
            self.assertTrue(all(artifact["sha256"] for artifact in manifest["artifacts"]))
            self.assertTrue(all(artifact["bytes"] > 0 for artifact in manifest["artifacts"]))

            device_evidence = repository.read_jsonl("device_evidence")
            self.assertTrue(device_evidence.available, device_evidence.unavailable)
            self.assertEqual(len(device_evidence.payload), 7)

            quality = repository.read_json("data_quality_report")
            self.assertTrue(quality.available, quality.unavailable)
            self.assertEqual(quality.payload["accepted_record_count"], 7)
            self.assertEqual(quality.payload["fold_leakage_count"], 0)

            evaluation = repository.read_json("model_evaluation")
            self.assertTrue(evaluation.available, evaluation.unavailable)
            self.assertEqual(evaluation.payload["activation_status"], "disabled")
            self.assertEqual(evaluation.payload["replay_status"], "non_regression")

            validation = validate_artifact_run(output_dir)
            self.assertEqual(validation.status, "valid", validation.to_dict())

    def test_beard_cole_import_requires_explicit_source_manifest_and_output_dir(self) -> None:
        with patch(
            "sys.argv",
            [
                "spirosearch",
                "beard-cole-import",
                "--source-file",
                str(FIXTURE_DIR / "psc_records.json"),
            ],
        ):
            with self.assertRaises(SystemExit):
                main()

    def test_validate_artifacts_cli_accepts_beard_cole_run(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "run"
            with patch(
                "sys.argv",
                [
                    "spirosearch",
                    "beard-cole-import",
                    "--source-file",
                    str(FIXTURE_DIR / "psc_records.json"),
                    "--source-manifest",
                    str(FIXTURE_DIR / "source-manifest.json"),
                    "--output-dir",
                    str(output_dir),
                ],
            ):
                self.assertEqual(main(), 0)

            with patch(
                "sys.argv",
                ["spirosearch", "validate-artifacts", "--output-dir", str(output_dir)],
            ):
                self.assertEqual(main(), 0)


if __name__ == "__main__":
    unittest.main()
