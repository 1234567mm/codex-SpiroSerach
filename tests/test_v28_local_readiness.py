import unittest

from spirosearch.v28_local_readiness import (
    build_v28_incident_checklist,
    build_v28_local_rehearsal_report,
)


class V28LocalReadinessTests(unittest.TestCase):
    def test_incident_checklist_is_local_only_and_fail_closed(self):
        checklist = build_v28_incident_checklist(
            release_profile_id="local-v28",
            restore_checks=[{"kind": "run-manifest", "status": "pass", "path": "run-manifest.json"}],
            dependency_scan_status="skipped_local_only",
            rollback_procedure_documented=True,
        )
        self.assertEqual(checklist["status"], "pass")
        self.assertFalse(checklist["hosted_deployment"])
        self.assertFalse(checklist["external_credentials_required"])

        blocked = build_v28_incident_checklist(
            release_profile_id="local-v28",
            restore_checks=[{"kind": "run-manifest", "status": "blocked"}],
            dependency_scan_status="failed",
            rollback_procedure_documented=False,
        )
        self.assertEqual(blocked["status"], "blocked")
        self.assertTrue(any(code.startswith("restore_check_failed") for code in blocked["reason_codes"]))

    def test_local_rehearsal_report_blocks_on_any_failed_step(self):
        report = build_v28_local_rehearsal_report(
            start_sha="abc",
            install_status="pass",
            test_gate_status="pass",
            screening_run_path="outputs/screening",
            artifact_validation_status="pass",
            viewer_status="pass",
            restore_status="blocked",
            elapsed_minutes=12.5,
            failures=["restore_hash_mismatch"],
        )
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["hosted_deployment"])


if __name__ == "__main__":
    unittest.main()
