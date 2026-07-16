import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from spirosearch.artifact_repository import JsonArtifactRepository
from spirosearch.artifacts import ARTIFACT_KIND_METADATA, build_run_manifest, write_json_artifact
from spirosearch.v25_release_checklist import build_v25_release_checklist


def _evidence(status_key, status="pass", **extra):
    payload = {status_key: status}
    payload.update(extra)
    return payload


class V25ReleaseChecklistTests(unittest.TestCase):
    def test_release_checklist_passes_with_all_required_evidence_and_full_gate(self):
        checklist = build_v25_release_checklist(
            release_profile=_evidence("profile_status", "pass", profile_id="v25-supported-runtime"),
            migration_policy=_evidence("policy_status", "pass", policy_id="v25-migration-policy"),
            security_audit=_evidence("audit_status", "pass", security_audit_id="v25-security-audit"),
            performance_budget=_evidence("budget_status", "pass", performance_budget_id="v25-performance-budget"),
            recovery_runbook=_evidence("recovery_status", "pass", recovery_runbook_id="v25-recovery-runbook"),
            final_gate={
                "command": "$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v",
                "result": "pending_until_main_merge",
            },
        )

        self.assertEqual(checklist["schema_version"], "v25.release_checklist.v1")
        self.assertEqual(checklist["release_status"], "pass")
        self.assertEqual(checklist["reason_codes"], [])
        self.assertEqual(checklist["claims"]["external_scientific_validation_claimed"], False)
        self.assertEqual(checklist["claims"]["direct_lab_dispatch_claimed"], False)
        self.assertIn("v25_release_checklist", ARTIFACT_KIND_METADATA)

    def test_blocked_upstream_evidence_blocks_release(self):
        checklist = build_v25_release_checklist(
            release_profile=_evidence("profile_status", "pass", profile_id="v25-supported-runtime"),
            migration_policy=_evidence("policy_status", "blocked", policy_id="v25-migration-policy"),
            security_audit=_evidence("audit_status", "pass", security_audit_id="v25-security-audit"),
            performance_budget=_evidence("budget_status", "pass", performance_budget_id="v25-performance-budget"),
            recovery_runbook=_evidence("recovery_status", "pass", recovery_runbook_id="v25-recovery-runbook"),
            final_gate={"command": "cmd", "result": "pending_until_main_merge"},
        )

        self.assertEqual(checklist["release_status"], "blocked")
        self.assertIn("upstream_blocked:migration_policy", checklist["reason_codes"])

    def test_missing_full_gate_command_blocks_release(self):
        checklist = build_v25_release_checklist(
            release_profile=_evidence("profile_status", "pass", profile_id="v25-supported-runtime"),
            migration_policy=_evidence("policy_status", "pass", policy_id="v25-migration-policy"),
            security_audit=_evidence("audit_status", "pass", security_audit_id="v25-security-audit"),
            performance_budget=_evidence("budget_status", "pass", performance_budget_id="v25-performance-budget"),
            recovery_runbook=_evidence("recovery_status", "pass", recovery_runbook_id="v25-recovery-runbook"),
            final_gate={"command": "", "result": ""},
        )

        self.assertEqual(checklist["release_status"], "blocked")
        self.assertIn("final_gate_missing", checklist["reason_codes"])

    def test_release_checklist_is_manifest_discovered_and_schema_valid(self):
        payload = build_v25_release_checklist(
            release_profile=_evidence("profile_status", "pass", profile_id="v25-supported-runtime"),
            migration_policy=_evidence("policy_status", "pass", policy_id="v25-migration-policy"),
            security_audit=_evidence("audit_status", "pass", security_audit_id="v25-security-audit"),
            performance_budget=_evidence("budget_status", "pass", performance_budget_id="v25-performance-budget"),
            recovery_runbook=_evidence("recovery_status", "pass", recovery_runbook_id="v25-recovery-runbook"),
            final_gate={"command": "cmd", "result": "pending_until_main_merge"},
        )
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            artifact = write_json_artifact(
                output_dir,
                "v25-release-checklist.json",
                payload,
                kind="v25_release_checklist",
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

            result = JsonArtifactRepository(output_dir).read_json("v25_release_checklist")

        self.assertTrue(result.available)
        self.assertEqual(result.schema_validation["status"], "valid")


if __name__ == "__main__":
    unittest.main()
