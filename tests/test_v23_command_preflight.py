import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from spirosearch.artifacts import build_run_manifest, write_json_artifact
from spirosearch.v23_command import preflight_commandable_run


def write_manifest(output_dir: Path, artifacts):
    manifest = build_run_manifest(
        artifacts,
        run_id="commandable-run",
        input_hash="input-hash",
        generated_at="2026-07-16T00:00:00+00:00",
        producer_version="v23-test",
    ).to_dict()
    (output_dir / "run-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return manifest


class V23CommandPreflightTests(unittest.TestCase):
    def test_manifest_native_run_is_commandable_when_expected_source_matches(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            artifact = write_json_artifact(
                output_dir,
                "review-summary.json",
                {
                    "schema_version": "v10.review_summary.v1",
                    "run_id": "commandable-run",
                    "generated_at": "2026-07-16T00:00:00+00:00",
                    "review_count": 0,
                    "event_count": 0,
                    "applied_event_count": 0,
                    "open_blocking_count": 0,
                    "resolved_count": 0,
                    "rejected_count": 0,
                    "by_resolution_status": {},
                    "by_reason_code": {},
                    "by_assigned_queue": {},
                    "by_severity": {},
                    "review_item_ids": [],
                    "review_event_ids": [],
                    "recompute_marker_ids": [],
                },
                kind="review_summary",
                run_id="commandable-run",
                input_hash="input-hash",
                generated_at="2026-07-16T00:00:00+00:00",
                producer_version="v23-test",
            )
            write_manifest(output_dir, [artifact])

            result = preflight_commandable_run(
                output_dir,
                expected_run_id="commandable-run",
                expected_input_hash="input-hash",
            )

        self.assertEqual(result["status"], "pass")
        self.assertTrue(result["commandable"])
        self.assertEqual(result["run_id"], "commandable-run")

    def test_preflight_rejects_legacy_pipeline_manifest(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            (output_dir / "run-manifest.json").write_text(
                json.dumps({
                    "created_at_utc": "2026-07-16T00:00:00+00:00",
                    "formula_version": "legacy",
                    "hard_filter_version": "legacy",
                    "input_digest": "abc",
                    "run_id": "legacy-run",
                }),
                encoding="utf-8",
            )

            result = preflight_commandable_run(output_dir)

        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["commandable"])
        self.assertEqual(result["reason_code"], "legacy_pipeline_manifest")

    def test_preflight_rejects_missing_unsafe_and_stale_sources_without_writing(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            before = set(output_dir.rglob("*"))

            missing = preflight_commandable_run(output_dir)
            unsafe = preflight_commandable_run(output_dir, manifest_path="../run-manifest.json")
            after = set(output_dir.rglob("*"))

        self.assertEqual(before, after)
        self.assertEqual(missing["reason_code"], "manifest_missing")
        self.assertEqual(unsafe["reason_code"], "manifest_path_unsafe")

        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            write_manifest(output_dir, [])

            stale_run = preflight_commandable_run(output_dir, expected_run_id="old-run")
            stale_hash = preflight_commandable_run(output_dir, expected_input_hash="old-hash")

        self.assertEqual(stale_run["reason_code"], "stale_source_run")
        self.assertEqual(stale_hash["reason_code"], "stale_input_hash")


if __name__ == "__main__":
    unittest.main()
