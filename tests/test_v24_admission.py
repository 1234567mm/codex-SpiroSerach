import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from spirosearch.artifact_repository import JsonArtifactRepository
from spirosearch.artifacts import ARTIFACT_KIND_METADATA, build_run_manifest, write_json_artifact
from spirosearch.v24_admission import build_v24_admission_report


def _artifact(kind):
    return {"kind": kind, "path": f"{kind}.json", "sha256": "0" * 64}


def closure(status="pass", impact="models_enabled_for_v24_admission"):
    return {
        "schema_version": "v22.scientific_closure_report.v1",
        "closure_id": "closure-1",
        "closure_gate_status": status,
        "downstream_impact": impact,
    }


def activation(status="eligible", may_rank=True):
    return {
        "schema_version": "v22.model_activation_report.v1",
        "snapshot_id": "snapshot-1",
        "model_version": "model-v1",
        "activation_status": status,
        "activation_reasons": [] if status == "eligible" else ["insufficient_independent_data"],
        "disabled_model_state": {
            "status": status,
            "may_rank_candidates": may_rank,
            "downstream_consumer": "v24_admission",
        },
    }


def action_result(**overrides):
    payload = {
        "schema_version": "v23.action_result.v1",
        "request_id": "request-1",
        "action_type": "review_decision",
        "status": "accepted",
        "idempotency_key": "idem-1",
        "actor_id": "curator-a",
        "reason_code": "command_preconditions_passed",
        "message": "accepted",
        "output_artifacts": [],
    }
    payload.update(overrides)
    return payload


class V24AdmissionTests(unittest.TestCase):
    def test_disabled_v22_gates_block_v24_model_admission(self):
        report = build_v24_admission_report(
            scientific_closure_report=closure("blocked", "models_disabled_for_v24_admission"),
            model_activation_report=activation("disabled", False),
            command_results=[action_result()],
            command_audit_events=[],
            manifest_artifacts=[
                _artifact("v22_scientific_closure_report"),
                _artifact("v22_model_activation_report"),
                _artifact("v23_action_results"),
            ],
        )

        self.assertEqual(report["admission_status"], "blocked")
        self.assertIn("v22_scientific_closure_blocked", report["reason_codes"])
        self.assertIn("v22_model_activation_disabled", report["reason_codes"])
        self.assertIn("v24_admission_report", ARTIFACT_KIND_METADATA)

    def test_admission_consumes_command_results_as_audited_facts_not_raw_payloads(self):
        report = build_v24_admission_report(
            scientific_closure_report=closure(),
            model_activation_report=activation(),
            command_results=[action_result(payload={"provider_execution": {"unsafe": True}})],
            command_audit_events=[{"audit_event_id": "audit-1", "request_id": "request-1", "actor_id": "curator-a"}],
            manifest_artifacts=[
                _artifact("v22_scientific_closure_report"),
                _artifact("v22_model_activation_report"),
                _artifact("v23_action_results"),
                _artifact("v23_command_audit"),
            ],
        )

        self.assertEqual(report["admission_status"], "pass")
        self.assertEqual(report["command_facts"][0]["request_id"], "request-1")
        self.assertNotIn("provider_execution", json.dumps(report, sort_keys=True))

    def test_missing_closure_artifacts_fail_closed(self):
        report = build_v24_admission_report(
            scientific_closure_report=closure(),
            model_activation_report=activation(),
            command_results=[],
            command_audit_events=[],
            manifest_artifacts=[],
        )

        self.assertEqual(report["admission_status"], "blocked")
        self.assertIn("source_artifact_missing:v22_scientific_closure_report", report["reason_codes"])
        self.assertIn("source_artifact_missing:v22_model_activation_report", report["reason_codes"])

    def test_admission_report_is_manifest_discovered_and_schema_valid(self):
        payload = build_v24_admission_report(
            scientific_closure_report=closure(),
            model_activation_report=activation(),
            command_results=[action_result()],
            command_audit_events=[],
            manifest_artifacts=[
                _artifact("v22_scientific_closure_report"),
                _artifact("v22_model_activation_report"),
                _artifact("v23_action_results"),
            ],
        )
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            artifact = write_json_artifact(
                output_dir,
                "v24-admission-report.json",
                payload,
                kind="v24_admission_report",
                run_id="v24-run",
                input_hash="input-hash",
                generated_at="2026-07-16T00:00:00+00:00",
                producer_version="v24-test",
            )
            build_run_manifest(
                [artifact],
                run_id="v24-run",
                input_hash="input-hash",
                generated_at="2026-07-16T00:00:00+00:00",
                producer_version="v24-test",
            ).write_json(output_dir)

            result = JsonArtifactRepository(output_dir).read_json("v24_admission_report")

        self.assertTrue(result.available)
        self.assertEqual(result.schema_validation["status"], "valid")


if __name__ == "__main__":
    unittest.main()
