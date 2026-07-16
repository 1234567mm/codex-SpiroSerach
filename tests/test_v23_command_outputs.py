import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from spirosearch.artifact_repository import JsonArtifactRepository
from spirosearch.artifacts import build_run_manifest, write_json_artifact
from spirosearch.mcp.registry import ToolNotFoundError
from spirosearch.mcp.server import create_readonly_run_registry, create_v23_command_registry
from spirosearch.v23_command import ActionRequest, ActionResult
from spirosearch.v23_command_outputs import write_command_output_artifacts


def action_result(action_type="review_decision", status="accepted"):
    return ActionResult(
        request_id=f"request-{action_type}-{status}",
        action_type=action_type,
        status=status,
        idempotency_key=f"idem-{action_type}-{status}",
        actor_id="curator-a" if action_type == "review_decision" else "operator-a",
        reason_code="command_preconditions_passed" if status == "accepted" else status,
        message=f"{status} command result",
    )


def review_request_payload(**overrides):
    values = {
        "action_type": "review_decision",
        "actor_id": "curator-a",
        "role": "curator",
        "reason": "resolve review item",
        "idempotency_key": "idem-review-e2e",
        "expected_run_id": "run-1",
        "expected_input_hash": "input-hash",
        "expected_target_version": "target-v1",
        "payload": {"review_item_id": "review-1", "decision": "resolve"},
    }
    values.update(overrides)
    return ActionRequest(**values).to_dict()


def action_result_from_payload(payload):
    return ActionResult(
        request_id=payload["request_id"],
        action_type=payload["action_type"],
        status=payload["status"],
        idempotency_key=payload["idempotency_key"],
        actor_id=payload["actor_id"],
        reason_code=payload["reason_code"],
        message=payload["message"],
        output_artifacts=tuple(payload.get("output_artifacts", ())),
    )


class V23CommandOutputTests(unittest.TestCase):
    def test_accepted_review_decision_appends_attributable_audit_event(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            artifacts = write_command_output_artifacts(
                output_dir,
                action_result("review_decision", "accepted"),
                run_id="run-1",
                input_hash="input-hash",
                generated_at="2026-07-16T00:00:00+00:00",
                producer_version="v23-test",
            )
            build_run_manifest(
                artifacts,
                run_id="run-1",
                input_hash="input-hash",
                generated_at="2026-07-16T00:00:00+00:00",
                producer_version="v23-test",
            ).write_json(output_dir)

            repository = JsonArtifactRepository(output_dir)
            audit = repository.read_jsonl("v23_command_audit")
            action_results = repository.read_jsonl("v23_action_results")

        self.assertTrue(audit.available)
        self.assertTrue(action_results.available)
        self.assertEqual(audit.records[0]["actor_id"], "curator-a")
        self.assertEqual(audit.records[0]["action_type"], "review_decision")
        self.assertEqual(audit.records[0]["status"], "accepted")
        self.assertEqual(audit.records[0]["attribution"]["actor_id"], "curator-a")

    def test_accepted_recompute_request_writes_manifest_discovered_job_status(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)

            artifacts = write_command_output_artifacts(
                output_dir,
                action_result("recompute_request", "accepted"),
                run_id="run-1",
                input_hash="input-hash",
                generated_at="2026-07-16T00:00:00+00:00",
                producer_version="v23-test",
            )
            build_run_manifest(
                artifacts,
                run_id="run-1",
                input_hash="input-hash",
                generated_at="2026-07-16T00:00:00+00:00",
                producer_version="v23-test",
            ).write_json(output_dir)

            status = JsonArtifactRepository(output_dir).read_json("v23_recompute_job_status")

        self.assertTrue(status.available)
        self.assertEqual(status.payload["request_id"], "request-recompute_request-accepted")
        self.assertEqual(status.payload["job_status"], "queued")
        self.assertEqual(status.payload["retry_state"]["attempt"], 0)

    def test_old_run_artifacts_remain_immutable_when_command_outputs_are_added(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            old_artifact = write_json_artifact(
                output_dir,
                "scoring-view.json",
                {"schema_version": "v10.scoring_view.v1", "energy_facts": []},
                kind="scoring_view",
                run_id="run-1",
                input_hash="input-hash",
                generated_at="2026-07-16T00:00:00+00:00",
                producer_version="v23-test",
            )
            before = (output_dir / "scoring-view.json").read_bytes()

            new_artifacts = write_command_output_artifacts(
                output_dir,
                action_result("review_decision", "accepted"),
                run_id="run-1",
                input_hash="input-hash",
                generated_at="2026-07-16T00:00:00+00:00",
                producer_version="v23-test",
            )

            after = (output_dir / "scoring-view.json").read_bytes()

        self.assertEqual(after, before)
        self.assertEqual(old_artifact.sha256, hashlib.sha256(after).hexdigest())
        self.assertTrue(any(artifact.kind == "v23_action_results" for artifact in new_artifacts))

    def test_recompute_terminal_statuses_are_explicit(self):
        for status, job_status in [
            ("timeout", "timeout"),
            ("cancelled", "cancelled"),
            ("partial_failure", "partial_failure"),
        ]:
            with self.subTest(status=status):
                with TemporaryDirectory() as temp_dir:
                    output_dir = Path(temp_dir)
                    artifacts = write_command_output_artifacts(
                        output_dir,
                        action_result("recompute_request", status),
                        run_id="run-1",
                        input_hash="input-hash",
                        generated_at="2026-07-16T00:00:00+00:00",
                        producer_version="v23-test",
                    )
                    build_run_manifest(
                        artifacts,
                        run_id="run-1",
                        input_hash="input-hash",
                        generated_at="2026-07-16T00:00:00+00:00",
                        producer_version="v23-test",
                    ).write_json(output_dir)

                    payload = JsonArtifactRepository(output_dir).read_json("v23_recompute_job_status").payload

                self.assertEqual(payload["job_status"], job_status)
                self.assertIn(status, json.dumps(payload, sort_keys=True))

    def test_e2e_security_replay_and_outputs_do_not_silently_change_state(self):
        with TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            registry = create_v23_command_registry(
                current_run_id="run-1",
                current_input_hash="input-hash",
                current_target_version="target-v1",
            )
            readonly_registry = create_readonly_run_registry(output_dir)

            accepted = registry.call_tool("submit_review_decision", review_request_payload(), actor="MCPClient")
            replay = registry.call_tool("submit_review_decision", review_request_payload(), actor="MCPClient")
            conflict = registry.call_tool(
                "submit_review_decision",
                review_request_payload(payload={"review_item_id": "review-2", "decision": "resolve"}),
                actor="MCPClient",
            )
            unauthorized = registry.call_tool(
                "submit_review_decision",
                review_request_payload(idempotency_key="idem-unauthorized", role="operator"),
                actor="MCPClient",
            )
            stale = registry.call_tool(
                "submit_review_decision",
                review_request_payload(idempotency_key="idem-stale", expected_target_version="target-v0"),
                actor="MCPClient",
            )

            self.assertEqual(replay, accepted)
            self.assertEqual(conflict["status"], "conflict")
            self.assertEqual(unauthorized["status"], "rejected")
            self.assertEqual(stale["status"], "conflict")
            self.assertEqual(conflict["output_artifacts"], [])
            self.assertEqual(unauthorized["output_artifacts"], [])
            self.assertEqual(stale["output_artifacts"], [])
            self.assertEqual(list(output_dir.rglob("*")), [])
            with self.assertRaises(ToolNotFoundError):
                readonly_registry.call_tool("submit_review_decision", review_request_payload(), actor="MCPClient")

            artifacts = write_command_output_artifacts(
                output_dir,
                action_result_from_payload(accepted),
                run_id="run-1",
                input_hash="input-hash",
                generated_at="2026-07-16T00:00:00+00:00",
                producer_version="v23-test",
            )
            build_run_manifest(
                artifacts,
                run_id="run-1",
                input_hash="input-hash",
                generated_at="2026-07-16T00:00:00+00:00",
                producer_version="v23-test",
            ).write_json(output_dir)
            audit = JsonArtifactRepository(output_dir).read_jsonl("v23_command_audit")

        self.assertTrue(audit.available)
        self.assertEqual(audit.records[0]["request_id"], accepted["request_id"])
        self.assertEqual(audit.records[0]["attribution"]["actor_id"], "curator-a")


if __name__ == "__main__":
    unittest.main()
