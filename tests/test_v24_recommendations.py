import unittest

from spirosearch.artifacts import ARTIFACT_KIND_METADATA
from spirosearch.v24_recommendations import build_v24_recommendation_artifacts


def loop_state(status="admitted"):
    return {
        "schema_version": "v24.loop_state.v1",
        "loop_state_id": "loop-1",
        "project_id": "project-1",
        "round_id": "round-1",
        "loop_status": status,
        "predecessor_run": {"run_id": "run-23", "input_hash": "input-23"},
        "candidate_pool": {"artifact_kind": "screening_input_view", "snapshot_id": "pool-1"},
        "training_snapshot": {"artifact_kind": "training_snapshot", "snapshot_id": "train-1"},
        "model_evaluation": {"artifact_kind": "v22_model_activation_report", "model_version": "model-v1"},
        "acquisition_policy": {"policy_id": "policy-1", "strategy": "heuristic", "batch_size": 2},
        "budget": {"currency": "USD", "max_experiments": 2, "max_cost": 100.0},
        "ledger": {"artifact_kind": "ledger", "ledger_id": "ledger-1"},
        "admission": {"admission_id": "admission-1", "admission_status": "pass" if status == "admitted" else "blocked", "reason_codes": []},
    }


def candidate(candidate_id, score, status="eligible"):
    return {
        "candidate_id": candidate_id,
        "material_id": f"mat-{candidate_id}",
        "use_instance_id": f"use-{candidate_id}",
        "candidate_version": "v1",
        "acquisition_score": score,
        "estimated_cost": 20.0,
        "status": status,
    }


class V24RecommendationTests(unittest.TestCase):
    def test_recommendations_are_deterministic_and_requests_include_lineage(self):
        candidates = [candidate("b", 0.5), candidate("a", 0.9), candidate("c", 0.1)]

        first = build_v24_recommendation_artifacts(loop_state(), candidates)
        second = build_v24_recommendation_artifacts(loop_state(), reversed(candidates))

        self.assertEqual(first, second)
        self.assertEqual([item["candidate_id"] for item in first["recommendations"]["items"]], ["a", "b"])
        request = first["experiment_requests"]["requests"][0]
        self.assertEqual(request["candidate_id"], "a")
        self.assertEqual(request["lineage"]["loop_state_id"], "loop-1")
        self.assertEqual(request["lineage"]["model_version"], "model-v1")
        self.assertEqual(request["budget"]["currency"], "USD")
        self.assertIn("v24_recommendations", ARTIFACT_KIND_METADATA)
        self.assertIn("v24_experiment_requests", ARTIFACT_KIND_METADATA)

    def test_duplicate_candidate_selection_is_blocked(self):
        with self.assertRaisesRegex(ValueError, "duplicate candidate_id"):
            build_v24_recommendation_artifacts(loop_state(), [candidate("a", 0.9), candidate("a", 0.8)])

    def test_blocked_loop_state_produces_no_experiment_requests(self):
        result = build_v24_recommendation_artifacts(loop_state("blocked"), [candidate("a", 0.9)])

        self.assertEqual(result["recommendations"]["status"], "blocked")
        self.assertEqual(result["recommendations"]["items"], [])
        self.assertEqual(result["experiment_requests"]["requests"], [])

    def test_ineligible_candidates_are_not_requested(self):
        result = build_v24_recommendation_artifacts(
            loop_state(),
            [candidate("a", 0.9, status="observed"), candidate("b", 0.8)],
        )

        self.assertEqual([item["candidate_id"] for item in result["recommendations"]["items"]], ["b"])
        self.assertEqual([item["candidate_id"] for item in result["experiment_requests"]["requests"]], ["b"])


if __name__ == "__main__":
    unittest.main()
