import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from spirosearch.artifact_repository import JsonArtifactRepository
from spirosearch.artifacts import ARTIFACT_KIND_METADATA, build_run_manifest, write_json_artifact
from spirosearch.v25_runtime_profile import build_v25_runtime_profile
from spirosearch.v25_security_audit import build_v25_security_audit


def _accepted_command(**overrides):
    payload = {
        "request_id": "request-1",
        "status": "accepted",
        "idempotency_key": "idem-1",
        "actor_id": "curator-a",
    }
    payload.update(overrides)
    return payload


class V25SecurityAuditTests(unittest.TestCase):
    def test_clean_release_surfaces_pass_security_audit(self):
        report = build_v25_security_audit(
            release_profile=build_v25_runtime_profile(),
            checked_paths=["artifacts/run-manifest.json", "viewer/index.html"],
            payload_samples=[{"field": "public"}],
            command_results=[_accepted_command()],
            command_audit_events=[{"audit_event_id": "audit-1", "request_id": "request-1", "actor_id": "curator-a"}],
            read_only_surface_checks=[{"surface": "viewer", "mutates_state": False}],
        )

        self.assertEqual(report["schema_version"], "v25.security_audit_report.v1")
        self.assertEqual(report["audit_status"], "pass")
        self.assertEqual(report["reason_codes"], [])
        self.assertIn("v25_security_audit_report", ARTIFACT_KIND_METADATA)

    def test_path_traversal_and_absolute_outputs_fail_closed(self):
        report = build_v25_security_audit(
            release_profile=build_v25_runtime_profile(),
            checked_paths=["../secret.txt", "C:/Users/wchao/token.txt"],
            payload_samples=[],
            command_results=[_accepted_command()],
            command_audit_events=[],
            read_only_surface_checks=[],
        )

        self.assertEqual(report["audit_status"], "blocked")
        self.assertIn("unsafe_path:../secret.txt", report["reason_codes"])
        self.assertIn("unsafe_path:C:/Users/wchao/token.txt", report["reason_codes"])

    def test_secret_like_payloads_are_redacted_and_blocked(self):
        report = build_v25_security_audit(
            release_profile=build_v25_runtime_profile(),
            checked_paths=[],
            payload_samples=[{"api_key": "sk-live-secret"}],
            command_results=[_accepted_command()],
            command_audit_events=[],
            read_only_surface_checks=[],
        )

        self.assertEqual(report["audit_status"], "blocked")
        self.assertIn("secret_like_payload_redacted", report["reason_codes"])
        self.assertNotIn("sk-live-secret", str(report))

    def test_commands_require_idempotency_actor_and_audit_attribution(self):
        report = build_v25_security_audit(
            release_profile=build_v25_runtime_profile(),
            checked_paths=[],
            payload_samples=[],
            command_results=[_accepted_command(idempotency_key="", actor_id="")],
            command_audit_events=[],
            read_only_surface_checks=[],
        )

        self.assertEqual(report["audit_status"], "blocked")
        self.assertIn("command_missing_idempotency:request-1", report["reason_codes"])
        self.assertIn("command_missing_actor:request-1", report["reason_codes"])
        self.assertIn("command_missing_audit_attribution:request-1", report["reason_codes"])

    def test_read_only_surface_mutation_fails_closed(self):
        report = build_v25_security_audit(
            release_profile=build_v25_runtime_profile(),
            checked_paths=[],
            payload_samples=[],
            command_results=[_accepted_command()],
            command_audit_events=[{"audit_event_id": "audit-1", "request_id": "request-1", "actor_id": "curator-a"}],
            read_only_surface_checks=[{"surface": "readonly_api", "mutates_state": True}],
        )

        self.assertEqual(report["audit_status"], "blocked")
        self.assertIn("read_only_surface_mutates_state:readonly_api", report["reason_codes"])

    def test_security_audit_report_is_manifest_discovered_and_schema_valid(self):
        payload = build_v25_security_audit(
            release_profile=build_v25_runtime_profile(),
            checked_paths=[],
            payload_samples=[],
            command_results=[_accepted_command()],
            command_audit_events=[{"audit_event_id": "audit-1", "request_id": "request-1", "actor_id": "curator-a"}],
            read_only_surface_checks=[],
        )
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            artifact = write_json_artifact(
                output_dir,
                "v25-security-audit-report.json",
                payload,
                kind="v25_security_audit_report",
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

            result = JsonArtifactRepository(output_dir).read_json("v25_security_audit_report")

        self.assertTrue(result.available)
        self.assertEqual(result.schema_validation["status"], "valid")


if __name__ == "__main__":
    unittest.main()
