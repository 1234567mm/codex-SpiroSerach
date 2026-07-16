import hashlib
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from spirosearch.artifact_repository import JsonArtifactRepository
from spirosearch.artifacts import build_run_manifest, write_json_artifact
from spirosearch.v23_command import ActionResult
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


if __name__ == "__main__":
    unittest.main()
