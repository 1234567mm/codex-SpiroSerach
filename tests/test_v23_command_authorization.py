import unittest

from spirosearch.v23_command import ActionRequest, CommandPreconditionEvaluator


def review_request(**overrides):
    values = {
        "action_type": "review_decision",
        "actor_id": "curator-a",
        "role": "curator",
        "reason": "resolve review item",
        "idempotency_key": "idem-1",
        "expected_run_id": "run-1",
        "expected_input_hash": "input-hash",
        "expected_target_version": "target-v1",
        "payload": {"review_item_id": "review-1", "decision": "resolve"},
    }
    values.update(overrides)
    return ActionRequest(**values)


class V23CommandAuthorizationTests(unittest.TestCase):
    def test_unauthorized_role_fails_closed_without_outputs(self):
        evaluator = CommandPreconditionEvaluator()

        result = evaluator.evaluate(
            review_request(role="operator"),
            current_run_id="run-1",
            current_input_hash="input-hash",
            current_target_version="target-v1",
        )

        self.assertEqual(result.status, "rejected")
        self.assertEqual(result.reason_code, "unauthorized_role")
        self.assertEqual(result.output_artifacts, ())

    def test_duplicate_idempotency_key_replays_original_identical_result(self):
        evaluator = CommandPreconditionEvaluator()
        request = review_request()

        original = evaluator.evaluate(
            request,
            current_run_id="run-1",
            current_input_hash="input-hash",
            current_target_version="target-v1",
        )
        replay = evaluator.evaluate(
            request,
            current_run_id="run-1",
            current_input_hash="input-hash",
            current_target_version="target-v2",
        )

        self.assertEqual(original.status, "accepted")
        self.assertEqual(replay.to_dict(), original.to_dict())

    def test_reused_idempotency_key_with_different_payload_conflicts(self):
        evaluator = CommandPreconditionEvaluator()
        request = review_request(idempotency_key="idem-shared")
        changed = review_request(
            idempotency_key="idem-shared",
            payload={"review_item_id": "review-2", "decision": "resolve"},
        )

        original = evaluator.evaluate(
            request,
            current_run_id="run-1",
            current_input_hash="input-hash",
            current_target_version="target-v1",
        )
        conflict = evaluator.evaluate(
            changed,
            current_run_id="run-1",
            current_input_hash="input-hash",
            current_target_version="target-v1",
        )
        replay = evaluator.evaluate(
            request,
            current_run_id="run-1",
            current_input_hash="input-hash",
            current_target_version="target-v1",
        )

        self.assertEqual(conflict.status, "conflict")
        self.assertEqual(conflict.reason_code, "idempotency_key_conflict")
        self.assertEqual(conflict.output_artifacts, ())
        self.assertEqual(replay.to_dict(), original.to_dict())

    def test_stale_source_or_target_version_conflicts_without_outputs(self):
        evaluator = CommandPreconditionEvaluator()

        cases = [
            (review_request(idempotency_key="idem-stale-run", expected_run_id="old-run"), "stale_source_run"),
            (review_request(idempotency_key="idem-stale-hash", expected_input_hash="old-hash"), "stale_input_hash"),
            (review_request(idempotency_key="idem-stale-version", expected_target_version="old-version"), "stale_target_version"),
        ]
        for request, reason_code in cases:
            with self.subTest(reason_code=reason_code):
                result = evaluator.evaluate(
                    request,
                    current_run_id="run-1",
                    current_input_hash="input-hash",
                    current_target_version="target-v1",
                )

                self.assertEqual(result.status, "conflict")
                self.assertEqual(result.reason_code, reason_code)
                self.assertEqual(result.output_artifacts, ())


if __name__ == "__main__":
    unittest.main()
