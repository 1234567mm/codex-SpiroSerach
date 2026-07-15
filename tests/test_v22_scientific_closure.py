import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from jsonschema import ValidationError, validate

from spirosearch.artifact_validation import validate_artifact_run
from spirosearch.artifacts import ARTIFACT_KIND_METADATA, build_run_manifest, write_json_artifact
from spirosearch.v22_scientific import build_v22_scientific_closure_report


def _artifact(kind):
    return {
        "kind": kind,
        "path": f"{kind}.json",
        "sha256": "0" * 64,
    }


class V22ScientificClosureTests(unittest.TestCase):
    def test_closure_report_links_every_gate_to_manifest_artifacts_and_disables_models(self):
        report = build_v22_scientific_closure_report(
            quality_report={"closure_gate_status": "pass"},
            zero_leakage_report={"closure_gate_status": "pass", "checks": []},
            independent_snapshot_report={
                "closure_gate_status": "blocked",
                "diagnostics": [{"reason_code": "independent_set_below_minimum"}],
            },
            model_activation_report={
                "activation_status": "disabled",
                "activation_reasons": ["insufficient_independent_data"],
                "grouped_evaluation": {
                    "calibration": {"coverage_95": 1.0},
                    "replay_status": "non_regression",
                    "folds": [{"fold_id": 0}, {"fold_id": 1}],
                },
            },
            manifest_artifacts=[
                _artifact("production_beard_cole_snapshot"),
                _artifact("v22_quality_report"),
                _artifact("v22_zero_leakage_report"),
                _artifact("v22_independent_snapshot_report"),
                _artifact("v22_model_activation_report"),
            ],
        )

        self.assertEqual(report["closure_gate_status"], "blocked")
        self.assertEqual(report["validation_scope"]["software_validation"]["status"], "pass")
        self.assertEqual(report["validation_scope"]["scientific_validation"]["status"], "blocked")
        self.assertFalse(report["claims"]["scientific_validation_claimed"])
        self.assertFalse(report["claims"]["model_activation_claimed"])
        self.assertEqual(report["claims"]["accepted_dataset_scope"], "production_snapshot")
        self.assertIn("models_disabled_for_v24_admission", report["downstream_impact"])
        self.assertTrue(all(gate["source_artifacts"] for gate in report["gates"]))
        self.assertIn("v22_scientific_closure_report", ARTIFACT_KIND_METADATA)
        validate(report, self._schema())

    def test_closure_schema_rejects_overclaimed_blocked_report(self):
        report = build_v22_scientific_closure_report(
            quality_report={"closure_gate_status": "blocked"},
            zero_leakage_report={"closure_gate_status": "pass", "checks": []},
            independent_snapshot_report={"closure_gate_status": "blocked", "diagnostics": []},
            model_activation_report={
                "activation_status": "disabled",
                "activation_reasons": ["independent_validation_blocked"],
                "grouped_evaluation": {"calibration": {}, "replay_status": "unavailable", "folds": []},
            },
            manifest_artifacts=[
                _artifact("production_beard_cole_snapshot"),
                _artifact("v22_quality_report"),
                _artifact("v22_zero_leakage_report"),
                _artifact("v22_independent_snapshot_report"),
                _artifact("v22_model_activation_report"),
            ],
        )
        report["claims"]["scientific_validation_claimed"] = True

        with self.assertRaises(ValidationError):
            validate(report, self._schema())

    def test_closure_artifact_validates_through_manifest(self):
        payload = build_v22_scientific_closure_report(
            quality_report={"closure_gate_status": "pass"},
            zero_leakage_report={"closure_gate_status": "pass", "checks": []},
            independent_snapshot_report={"closure_gate_status": "pass", "diagnostics": [], "retained_record_ids": ["i1"]},
            model_activation_report={
                "activation_status": "eligible",
                "activation_reasons": [],
                "grouped_evaluation": {
                    "calibration": {"coverage_95": 1.0},
                    "replay_status": "non_regression",
                    "folds": [{"fold_id": 0}, {"fold_id": 1}],
                },
            },
            manifest_artifacts=[
                _artifact("production_beard_cole_snapshot"),
                _artifact("v22_quality_report"),
                _artifact("v22_zero_leakage_report"),
                _artifact("v22_independent_snapshot_report"),
                _artifact("v22_model_activation_report"),
            ],
        )
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            artifact = write_json_artifact(
                output_dir,
                "v22-scientific-closure-report.json",
                payload,
                kind="v22_scientific_closure_report",
                run_id="v22-closure",
                input_hash="input-hash",
                generated_at="2026-07-15T00:00:00+00:00",
                producer_version="test",
            )
            manifest = build_run_manifest(
                [artifact],
                run_id="v22-closure",
                input_hash="input-hash",
                generated_at="2026-07-15T00:00:00+00:00",
                producer_version="test",
            ).to_dict()
            (output_dir / "run-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            validation_report = validate_artifact_run(output_dir)

        self.assertEqual(validation_report.status, "valid")

    def _schema(self):
        return json.loads(Path("schemas/v22-scientific-closure-report.schema.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
