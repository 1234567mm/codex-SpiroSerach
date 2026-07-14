import json
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from jsonschema import Draft202012Validator

from spirosearch.artifact_validation import validate_artifact_run
from spirosearch.artifacts import build_run_manifest, write_json_artifact, write_jsonl_artifact
from spirosearch.cli import _main_validate_artifacts
from spirosearch.contracts import EXIT_SUCCESS, EXIT_VALIDATION_ERROR


def write_manifest(output_dir: Path, artifacts):
    manifest = build_run_manifest(
        artifacts,
        run_id="validation-run",
        input_hash="input-hash",
        generated_at="2026-07-09T00:00:00+00:00",
        producer_version="validation-test",
    ).to_dict()
    (output_dir / "run-manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return manifest


def scoring_view_payload():
    return {
        "schema_version": "v10.scoring_view.v1",
        "energy_facts": [
            {
                "evidence_id": "energy:mat:homo_ev",
                "material_id": "mat",
                "use_instance_id": "use:mat",
                "property_name": "homo_ev",
                "value_ev": -5.2,
                "unit": "eV",
                "method": "reported",
                "reference_scale": "vacuum",
                "computed": False,
                "quality": {
                    "evidence_id": "energy:mat:homo_ev",
                    "evidence_type": "energy_evidence",
                    "trust_level": "T4_literature_curated",
                    "curation_status": "curated",
                    "quality_score": 0.9,
                    "eligible_for_scoring": True,
                    "blocking_review_count": 0,
                    "blocking_review_ids": [],
                },
            }
        ],
    }


class ArtifactValidationLoopTests(unittest.TestCase):
    def test_valid_run_reports_manifest_artifact_and_join_key_checks(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            scoring = write_json_artifact(
                output_dir,
                "nested/scoring-view.json",
                scoring_view_payload(),
                kind="scoring_view",
                run_id="validation-run",
                input_hash="input-hash",
                generated_at="2026-07-09T00:00:00+00:00",
                producer_version="validation-test",
            )
            recommendations = write_json_artifact(
                output_dir,
                "recommendations.json",
                {"schema_version": "v4-runtime-recommendations-v1", "requests": []},
                kind="recommendations",
                run_id="validation-run",
                input_hash="input-hash",
                generated_at="2026-07-09T00:00:00+00:00",
                producer_version="validation-test",
            )
            write_manifest(output_dir, [recommendations, scoring])

            report = validate_artifact_run(output_dir)
            report_dict = report.to_dict()

            self.assertEqual(report.status, "valid")
            self.assertEqual(report.severity, "info")
            self.assertEqual(report.run_id, "validation-run")
            self.assertEqual(report_dict["schema_version"], "v11.artifact_validation.v1")
            self.assertEqual(report_dict["run_id"], "validation-run")
            self.assert_report_schema_valid(report_dict)
            self.assertEqual(report.summary["artifact_count"], 2)
            self.assertEqual(report.summary["available_artifact_count"], 2)
            self.assertEqual(report.summary["error_count"], 0)
            self.assertEqual(report.manifest["status"], "valid")
            self.assertTrue(report.manifest["available"])
            self.assertEqual([artifact.kind for artifact in report.artifacts], ["recommendations", "scoring_view"])
            scoring_result = next(artifact for artifact in report.artifacts if artifact.kind == "scoring_view")
            self.assertEqual(scoring_result.path, "nested/scoring-view.json")
            self.assertEqual(scoring_result.status, "valid")
            self.assertTrue(scoring_result.to_dict()["available"])
            self.assertEqual(scoring_result.to_dict()["join_keys"], ["candidate_id", "material_id", "evidence_id"])
            self.assertEqual({check.name: check.status for check in scoring_result.checks}["join_keys"], "pass")
            self.assertEqual({check.name: check.status for check in scoring_result.checks}["repository_read"], "pass")
            scoring_join = next(
                diagnostic
                for diagnostic in report_dict["join_diagnostics"]
                if diagnostic["kind"] == "scoring_view"
            )
            self.assertEqual(scoring_join["status"], "informational")
            self.assertEqual(scoring_join["missing_payload_keys"], ["candidate_id"])
            self.assertIn("canonical_evidence", scoring_join["notes"][0])
            json.dumps(report_dict, sort_keys=True)

    def test_screening_input_view_requires_own_declared_manifest_dependencies(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            artifact_args = {
                "run_id": "validation-run",
                "input_hash": "input-hash",
                "generated_at": "2026-07-09T00:00:00+00:00",
                "producer_version": "validation-test",
            }
            canonical = write_json_artifact(
                output_dir,
                "canonical-evidence.json",
                {
                    "schema_version": "v9.canonical_evidence.v1",
                    "candidate_count": 0,
                    "records": [],
                },
                kind="canonical_evidence",
                **artifact_args,
            )
            scoring = write_json_artifact(
                output_dir,
                "scoring-view.json",
                scoring_view_payload(),
                kind="scoring_view",
                **artifact_args,
            )
            review_queue = write_jsonl_artifact(
                output_dir,
                "review-queue.jsonl",
                [],
                kind="review_queue",
                **artifact_args,
            )
            review_events = write_jsonl_artifact(
                output_dir,
                "review-events.jsonl",
                [],
                kind="review_events",
                **artifact_args,
            )
            screening_payload = {
                "schema_version": "v19.screening_input_view.v1",
                "profile_version": "v12.htl_screening.v1",
                "candidates": [],
            }
            screening_schema = json.loads(
                Path("schemas/screening-input-view.schema.json").read_text(encoding="utf-8")
            )
            Draft202012Validator(screening_schema).validate(screening_payload)
            screening = write_json_artifact(
                output_dir,
                "screening-input-view.json",
                screening_payload,
                kind="screening_input_view",
                **artifact_args,
            )
            manifest = write_manifest(
                output_dir,
                [canonical, scoring, review_queue, review_events, screening],
            )

            screening_metadata = next(
                artifact
                for artifact in manifest["artifacts"]
                if artifact["kind"] == "screening_input_view"
            )
            self.assertEqual(
                screening_metadata["depends_on"],
                ["canonical_evidence", "scoring_view", "review_queue", "review_events"],
            )
            screening_metadata["depends_on"].remove("scoring_view")
            (output_dir / "run-manifest.json").write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            report = validate_artifact_run(output_dir)
            screening_result = next(
                artifact
                for artifact in report.artifacts
                if artifact.kind == "screening_input_view"
            )

            self.assertEqual(report.status, "invalid")
            self.assertEqual(screening_result.status, "unavailable")
            self.assertEqual(
                screening_result.unavailable["code"],
                "artifact_dependency_not_declared",
            )
            self.assertEqual(
                screening_result.unavailable["detail"],
                {"missing_kinds": ["scoring_view"]},
            )
            dependency_check = next(
                check
                for check in screening_result.checks
                if check.name == "declared_dependencies"
            )
            self.assertEqual(dependency_check.status, "fail")
            self.assertEqual(dependency_check.detail["missing_kinds"], ["scoring_view"])

    def test_hash_mismatch_is_reported_as_artifact_unavailable_without_hiding_manifest(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            artifact = write_json_artifact(
                output_dir,
                "scoring-view.json",
                scoring_view_payload(),
                kind="scoring_view",
                run_id="validation-run",
                input_hash="input-hash",
                generated_at="2026-07-09T00:00:00+00:00",
                producer_version="validation-test",
            )
            manifest = write_manifest(output_dir, [artifact])
            manifest["artifacts"][0]["sha256"] = "0" * 64
            (output_dir / "run-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            report = validate_artifact_run(output_dir)
            artifact_result = report.artifacts[0]

            self.assertEqual(report.status, "invalid")
            self.assertEqual(report.manifest["status"], "valid")
            self.assertEqual(artifact_result.status, "unavailable")
            self.assertEqual(artifact_result.unavailable["reason"], "artifact_sha256_mismatch")
            self.assertEqual(report.summary["error_count"], 1)

    def test_optional_missing_artifact_is_panel_local_unavailable_not_run_failure(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            write_manifest(output_dir, [])

            report = validate_artifact_run(output_dir, optional_artifacts={"conflict_events": "Conflict Panel"})
            optional = report.optional_artifacts[0]

            self.assertEqual(report.status, "degraded")
            self.assertEqual(report.severity, "warning")
            self.assertEqual(optional.kind, "conflict_events")
            self.assertEqual(optional.status, "unavailable")
            self.assertFalse(optional.required)
            self.assertEqual(optional.panel_id, "conflict_panel")
            self.assertEqual(optional.panel, "Conflict Panel")
            self.assertEqual(optional.unavailable["reason"], "artifact_not_declared")
            self.assertEqual(report.to_dict()["panels"][0]["panel_id"], "conflict_panel")
            self.assertEqual(report.to_dict()["panels"][0]["optional_kinds"], ["conflict_events"])
            self.assertEqual(report.to_dict()["panels"][0]["unavailable_kinds"], ["conflict_events"])
            self.assertEqual(report.summary["optional_unavailable_count"], 1)
            self.assertEqual(report.summary["warning_count"], 1)
            self.assertEqual(report.summary["error_count"], 0)

    def test_join_key_mismatch_is_structured_validation_error(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            artifact = write_json_artifact(
                output_dir,
                "scoring-view.json",
                scoring_view_payload(),
                kind="scoring_view",
                run_id="validation-run",
                input_hash="input-hash",
                generated_at="2026-07-09T00:00:00+00:00",
                producer_version="validation-test",
            )
            manifest = write_manifest(output_dir, [artifact])
            manifest["artifacts"][0]["join_keys"] = ["candidate_id"]
            (output_dir / "run-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            report = validate_artifact_run(output_dir)
            join_key_check = next(check for check in report.artifacts[0].checks if check.name == "join_keys")

            self.assertEqual(report.status, "invalid")
            self.assertEqual(report.artifacts[0].status, "invalid")
            self.assertEqual(join_key_check.status, "fail")
            self.assertEqual(join_key_check.detail["expected"], ["candidate_id", "material_id", "evidence_id"])
            self.assertEqual(join_key_check.detail["actual"], ["candidate_id"])

    def test_duplicate_manifest_kind_is_rejected_before_kind_keyed_read(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            first = write_json_artifact(
                output_dir,
                "scoring-view-a.json",
                scoring_view_payload(),
                kind="scoring_view",
                run_id="validation-run",
                input_hash="input-hash",
                generated_at="2026-07-09T00:00:00+00:00",
                producer_version="validation-test",
            )
            second = write_json_artifact(
                output_dir,
                "scoring-view-b.json",
                scoring_view_payload(),
                kind="scoring_view",
                run_id="validation-run",
                input_hash="input-hash",
                generated_at="2026-07-09T00:00:00+00:00",
                producer_version="validation-test",
            )
            write_manifest(output_dir, [first, second])

            report = validate_artifact_run(output_dir)

            self.assertEqual(report.status, "invalid")
            self.assertEqual([artifact.path for artifact in report.artifacts], ["scoring-view-a.json", "scoring-view-b.json"])
            self.assertEqual(report.summary["error_count"], 2)
            for artifact in report.artifacts:
                kind_check = next(check for check in artifact.checks if check.name == "manifest_kind_unique")
                self.assertEqual(artifact.status, "invalid")
                self.assertEqual(artifact.unavailable["reason"], "manifest_duplicate_kind")
                self.assertEqual(kind_check.status, "fail")
                self.assertEqual(kind_check.severity, "error")
            self.assertEqual(report.to_dict()["join_diagnostics"][0]["status"], "unavailable")

    def test_schema_failure_report_does_not_leak_payload_values(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            invalid_payload = scoring_view_payload()
            invalid_payload["schema_version"] = "secret-leak-value"
            artifact = write_json_artifact(
                output_dir,
                "scoring-view.json",
                invalid_payload,
                kind="scoring_view",
                run_id="validation-run",
                input_hash="input-hash",
                generated_at="2026-07-09T00:00:00+00:00",
                producer_version="validation-test",
            )
            write_manifest(output_dir, [artifact])

            report = validate_artifact_run(output_dir)
            report_dict = report.to_dict()
            unavailable = report_dict["artifacts"][0]["unavailable"]

            self.assertEqual(report.status, "invalid")
            self.assertEqual(unavailable["reason"], "schema_validation_failed")
            self.assertEqual(unavailable["detail"]["schema_ref"], "schemas/scoring-view.schema.json")
            self.assertEqual(unavailable["detail"]["json_path"], ["schema_version"])
            self.assertNotIn("message", unavailable["detail"])
            self.assertNotIn("secret-leak-value", json.dumps(report_dict, sort_keys=True))

    def test_missing_manifest_short_circuits_with_run_level_unavailable(self):
        with TemporaryDirectory() as temp_dir:
            report = validate_artifact_run(Path(temp_dir))

            self.assertEqual(report.status, "unavailable")
            self.assertEqual(report.severity, "critical")
            self.assertIsNone(report.run_id)
            self.assertEqual(report.manifest["status"], "unavailable")
            self.assertFalse(report.manifest["available"])
            self.assertEqual(report.manifest["unavailable"]["reason"], "manifest_missing")
            self.assertEqual(report.artifacts, ())
            self.assertEqual(report.summary["run_unavailable_count"], 1)

    def test_cli_validate_artifacts_writes_frontend_ready_json_report(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            artifact = write_json_artifact(
                output_dir,
                "scoring-view.json",
                scoring_view_payload(),
                kind="scoring_view",
                run_id="validation-run",
                input_hash="input-hash",
                generated_at="2026-07-09T00:00:00+00:00",
                producer_version="validation-test",
            )
            write_manifest(output_dir, [artifact])
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = _main_validate_artifacts(
                    [
                        "--output-dir",
                        str(output_dir),
                        "--optional-artifact",
                        "conflict_events=Conflict Panel",
                    ]
                )

            report = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, EXIT_SUCCESS)
            self.assertEqual(report["schema_version"], "v11.artifact_validation.v1")
            self.assert_report_schema_valid(report)
            self.assertEqual(report["status"], "degraded")
            self.assertEqual(report["severity"], "warning")
            self.assertEqual(report["artifacts"][0]["path"], "scoring-view.json")
            self.assertEqual(report["optional_artifacts"][0]["panel"], "Conflict Panel")

    def test_cli_validate_artifacts_returns_validation_error_for_invalid_run(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            artifact = write_json_artifact(
                output_dir,
                "scoring-view.json",
                scoring_view_payload(),
                kind="scoring_view",
                run_id="validation-run",
                input_hash="input-hash",
                generated_at="2026-07-09T00:00:00+00:00",
                producer_version="validation-test",
            )
            manifest = write_manifest(output_dir, [artifact])
            manifest["artifacts"][0]["sha256"] = "0" * 64
            (output_dir / "run-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            with redirect_stdout(StringIO()):
                exit_code = _main_validate_artifacts(["--output-dir", str(output_dir)])

            self.assertEqual(exit_code, EXIT_VALIDATION_ERROR)

    def assert_report_schema_valid(self, report):
        schema = json.loads(Path("schemas/artifact-validation-report.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(report)


if __name__ == "__main__":
    unittest.main()
