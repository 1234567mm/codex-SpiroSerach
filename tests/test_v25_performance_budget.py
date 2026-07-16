import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from spirosearch.artifact_repository import JsonArtifactRepository
from spirosearch.artifacts import ARTIFACT_KIND_METADATA, build_run_manifest, write_json_artifact
from spirosearch.v25_performance_budget import build_v25_performance_budget_report
from spirosearch.v25_runtime_profile import build_v25_runtime_profile


class V25PerformanceBudgetTests(unittest.TestCase):
    def test_budget_passes_when_measurements_are_under_limits(self):
        report = build_v25_performance_budget_report(
            release_profile=build_v25_runtime_profile(),
            measurements={
                "artifact_repository_read_ms": 12,
                "project_summary_ms": 25,
                "viewer_payload_kb": 128,
            },
        )

        self.assertEqual(report["schema_version"], "v25.performance_budget_report.v1")
        self.assertEqual(report["budget_status"], "pass")
        self.assertEqual(report["reason_codes"], [])
        self.assertIn("v25_performance_budget_report", ARTIFACT_KIND_METADATA)

    def test_budget_failure_is_explicit_for_over_limit_measurements(self):
        report = build_v25_performance_budget_report(
            release_profile=build_v25_runtime_profile(),
            measurements={
                "artifact_repository_read_ms": 1200,
                "project_summary_ms": 25,
                "viewer_payload_kb": 128,
            },
        )

        self.assertEqual(report["budget_status"], "blocked")
        self.assertIn("budget_exceeded:artifact_repository_read_ms", report["reason_codes"])
        self.assertEqual(report["measurements"][0]["status"], "blocked")

    def test_missing_measurement_fails_closed(self):
        report = build_v25_performance_budget_report(
            release_profile=build_v25_runtime_profile(),
            measurements={"artifact_repository_read_ms": 12},
        )

        self.assertEqual(report["budget_status"], "blocked")
        self.assertIn("measurement_missing:project_summary_ms", report["reason_codes"])
        self.assertIn("measurement_missing:viewer_payload_kb", report["reason_codes"])

    def test_performance_budget_report_is_manifest_discovered_and_schema_valid(self):
        payload = build_v25_performance_budget_report(
            release_profile=build_v25_runtime_profile(),
            measurements={
                "artifact_repository_read_ms": 12,
                "project_summary_ms": 25,
                "viewer_payload_kb": 128,
            },
        )
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            artifact = write_json_artifact(
                output_dir,
                "v25-performance-budget-report.json",
                payload,
                kind="v25_performance_budget_report",
                run_id="v25-run",
                input_hash="input-hash",
                generated_at="2026-07-16T00:00:00+00:00",
                producer_version="v25-test",
            )
            build_run_manifest(
                [artifact],
                run_id="v25-run",
                input_hash="input-hash",
                generated_at="2026-07-16T00:00:00+00:00",
                producer_version="v25-test",
            ).write_json(output_dir)

            result = JsonArtifactRepository(output_dir).read_json("v25_performance_budget_report")

        self.assertTrue(result.available)
        self.assertEqual(result.schema_validation["status"], "valid")


if __name__ == "__main__":
    unittest.main()
