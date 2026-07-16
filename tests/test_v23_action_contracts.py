import json
import unittest
from pathlib import Path

from jsonschema import ValidationError, validate

from spirosearch.v23_command import ActionRequest, ActionResult


class V23ActionContractTests(unittest.TestCase):
    def test_action_request_requires_actor_reason_idempotency_source_and_preconditions(self):
        request = ActionRequest(
            action_type="review_decision",
            actor_id="curator-a",
            role="curator",
            reason="resolve accepted evidence",
            idempotency_key="idem-1",
            expected_run_id="run-1",
            expected_input_hash="input-hash",
            expected_target_version="review-item-v1",
            payload={"review_item_id": "review-1", "decision": "resolve"},
        )
        payload = request.to_dict()

        self.assertEqual(payload["schema_version"], "v23.action_request.v1")
        self.assertEqual(payload["request_id"], request.request_id)
        self.assertEqual(ActionRequest.from_mapping(payload).to_dict(), payload)
        validate(payload, self._schema("v23-action-request.schema.json"))

    def test_action_request_rejects_unknown_action_and_out_of_scope_payload(self):
        with self.assertRaisesRegex(ValueError, "unknown action_type"):
            ActionRequest(
                action_type="provider_execution",
                actor_id="curator-a",
                role="curator",
                reason="bad",
                idempotency_key="idem-1",
                expected_run_id="run-1",
                expected_input_hash="input-hash",
                expected_target_version="v1",
                payload={},
            )
        with self.assertRaisesRegex(ValueError, "out-of-scope"):
            ActionRequest(
                action_type="review_decision",
                actor_id="curator-a",
                role="curator",
                reason="bad",
                idempotency_key="idem-1",
                expected_run_id="run-1",
                expected_input_hash="input-hash",
                expected_target_version="v1",
                payload={"model_training": {}},
            )

    def test_action_request_schema_rejects_missing_idempotency_and_unknown_action(self):
        payload = ActionRequest(
            action_type="recompute_request",
            actor_id="operator-a",
            role="operator",
            reason="refresh derived artifacts",
            idempotency_key="idem-2",
            expected_run_id="run-1",
            expected_input_hash="input-hash",
            expected_target_version="marker-v1",
            payload={"recompute_marker_id": "marker-1"},
        ).to_dict()
        schema = self._schema("v23-action-request.schema.json")

        missing = dict(payload)
        missing.pop("idempotency_key")
        with self.assertRaises(ValidationError):
            validate(missing, schema)
        unknown = dict(payload)
        unknown["action_type"] = "experiment_dispatch"
        with self.assertRaises(ValidationError):
            validate(unknown, schema)

    def test_action_result_distinguishes_all_terminal_and_replay_states(self):
        schema = self._schema("v23-action-result.schema.json")
        statuses = ["accepted", "rejected", "conflict", "timeout", "cancelled", "partial_failure", "replayed"]
        for status in statuses:
            result = ActionResult(
                request_id=f"request-{status}",
                action_type="review_decision",
                status=status,
                idempotency_key=f"idem-{status}",
                actor_id="curator-a",
                reason_code=f"{status}_reason",
                message=f"{status} message",
                output_artifacts=({"kind": "review_events", "path": "review-events.jsonl"},),
            ).to_dict()
            validate(result, schema)

    def _schema(self, name):
        return json.loads(Path("schemas", name).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
