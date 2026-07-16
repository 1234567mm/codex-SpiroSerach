import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from spirosearch.artifact_repository import JsonArtifactRepository
from spirosearch.artifacts import ARTIFACT_KIND_METADATA, build_run_manifest, write_json_artifact
from spirosearch.v25_migration_policy import build_v25_migration_policy
from spirosearch.v25_recovery_runbook import build_v25_recovery_runbook
from spirosearch.v25_runtime_profile import build_v25_runtime_profile


class V25RecoveryRunbookTests(unittest.TestCase):
    def test_recovery_runbook_lists_release_backup_scope_and_no_hidden_credentials(self):
        runbook = build_v25_recovery_runbook(
            release_profile=build_v25_runtime_profile(),
            migration_policy=build_v25_migration_policy(
                release_profile=build_v25_runtime_profile(),
                manifest_artifacts=[],
            ),
            restored_artifacts=[
                {
                    "kind": "v25_release_profile",
                    "path": "v25-release-profile.json",
                    "expected_sha256": "a" * 64,
                    "actual_sha256": "a" * 64,
                    "schema_ref": "schemas/v25-release-profile.schema.json",
                }
            ],
        )

        self.assertEqual(runbook["schema_version"], "v25.recovery_runbook.v1")
        self.assertEqual(runbook["recovery_status"], "pass")
        self.assertEqual(runbook["external_credentials_required"], False)
        self.assertEqual(
            runbook["backup_scope"],
            ["run-manifest.json", "artifacts", "schemas", "command_outputs", "handoff_artifacts"],
        )
        self.assertIn("v25_recovery_runbook", ARTIFACT_KIND_METADATA)

    def test_restore_hash_mismatch_and_missing_schema_fail_closed(self):
        runbook = build_v25_recovery_runbook(
            release_profile=build_v25_runtime_profile(),
            migration_policy={"policy_id": "v25-migration-policy", "policy_status": "pass"},
            restored_artifacts=[
                {
                    "kind": "v25_release_profile",
                    "path": "v25-release-profile.json",
                    "expected_sha256": "a" * 64,
                    "actual_sha256": "b" * 64,
                    "schema_ref": "",
                }
            ],
        )

        self.assertEqual(runbook["recovery_status"], "blocked")
        self.assertIn("restore_hash_mismatch:v25_release_profile", runbook["reason_codes"])
        self.assertIn("restore_schema_missing:v25_release_profile", runbook["reason_codes"])

    def test_blocked_migration_policy_blocks_recovery(self):
        runbook = build_v25_recovery_runbook(
            release_profile=build_v25_runtime_profile(),
            migration_policy={"policy_id": "v25-migration-policy", "policy_status": "blocked"},
            restored_artifacts=[],
        )

        self.assertEqual(runbook["recovery_status"], "blocked")
        self.assertIn("migration_policy_blocked", runbook["reason_codes"])

    def test_recovery_runbook_is_manifest_discovered_and_schema_valid(self):
        payload = build_v25_recovery_runbook(
            release_profile=build_v25_runtime_profile(),
            migration_policy={"policy_id": "v25-migration-policy", "policy_status": "pass"},
            restored_artifacts=[],
        )
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            artifact = write_json_artifact(
                output_dir,
                "v25-recovery-runbook.json",
                payload,
                kind="v25_recovery_runbook",
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

            result = JsonArtifactRepository(output_dir).read_json("v25_recovery_runbook")

        self.assertTrue(result.available)
        self.assertEqual(result.schema_validation["status"], "valid")


if __name__ == "__main__":
    unittest.main()
