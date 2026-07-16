import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from spirosearch.artifact_repository import JsonArtifactRepository
from spirosearch.artifacts import ARTIFACT_KIND_METADATA, build_run_manifest, write_json_artifact
from spirosearch.v25_migration_policy import build_v25_migration_policy
from spirosearch.v25_runtime_profile import build_v25_runtime_profile


def _manifest_artifact(kind, schema_ref=None):
    metadata = ARTIFACT_KIND_METADATA[kind]
    return {
        "kind": kind,
        "path": f"{kind}.json",
        "sha256": "0" * 64,
        "schema_ref": metadata["schema_ref"] if schema_ref is None else schema_ref,
    }


class V25MigrationPolicyTests(unittest.TestCase):
    def test_policy_passes_supported_schema_refs_from_registry(self):
        report = build_v25_migration_policy(
            release_profile=build_v25_runtime_profile(),
            manifest_artifacts=[
                _manifest_artifact("v25_release_profile"),
                _manifest_artifact("v24_stop_continue_report"),
            ],
        )

        self.assertEqual(report["schema_version"], "v25.migration_policy.v1")
        self.assertEqual(report["policy_status"], "pass")
        self.assertEqual(report["reason_codes"], [])
        self.assertIn("v25_release_profile", report["supported_artifact_kinds"])

    def test_missing_required_schema_ref_fails_closed(self):
        report = build_v25_migration_policy(
            release_profile=build_v25_runtime_profile(),
            manifest_artifacts=[_manifest_artifact("v25_release_profile", schema_ref="")],
        )

        self.assertEqual(report["policy_status"], "blocked")
        self.assertIn("missing_schema_ref:v25_release_profile", report["reason_codes"])

    def test_schema_ref_mismatch_fails_closed_without_relaxing_fixture(self):
        report = build_v25_migration_policy(
            release_profile=build_v25_runtime_profile(),
            manifest_artifacts=[
                _manifest_artifact("v25_release_profile", schema_ref="schemas/legacy-release-profile.schema.json")
            ],
        )

        self.assertEqual(report["policy_status"], "blocked")
        self.assertIn("unsupported_schema_ref:v25_release_profile", report["reason_codes"])

    def test_migration_policy_is_manifest_discovered_and_schema_valid(self):
        payload = build_v25_migration_policy(
            release_profile=build_v25_runtime_profile(),
            manifest_artifacts=[_manifest_artifact("v25_release_profile")],
        )
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            artifact = write_json_artifact(
                output_dir,
                "v25-migration-policy.json",
                payload,
                kind="v25_migration_policy",
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

            result = JsonArtifactRepository(output_dir).read_json("v25_migration_policy")

        self.assertTrue(result.available)
        self.assertEqual(result.schema_validation["status"], "valid")


if __name__ == "__main__":
    unittest.main()
