import unittest

from spirosearch.v24_loop_controls import build_v24_loop_controls_report


def loop_state():
    return {
        "loop_state_id": "loop-1",
        "model_evaluation": {"model_version": "model-v1"},
        "admission": {"admission_id": "admission-1"},
        "budget": {"max_cost": 50.0, "max_experiments": 2},
    }


def recommendations():
    return {
        "recommendation_set_id": "rec-1",
        "items": [{"candidate_id": "a"}, {"candidate_id": "b"}],
    }


def requests(*items):
    return {
        "request_set_id": "req-1",
        "requests": list(items or [
            {"request_id": "r-a", "candidate_id": "a", "budget": {"estimated_cost": 20.0}, "lineage": {"model_version": "model-v1"}},
            {"request_id": "r-b", "candidate_id": "b", "budget": {"estimated_cost": 20.0}, "lineage": {"model_version": "model-v1"}},
        ]),
    }


class V24LoopControlsTests(unittest.TestCase):
    def test_replay_control_hash_is_deterministic_for_same_inputs(self):
        first = build_v24_loop_controls_report(
            loop_state(),
            recommendations(),
            requests(),
            current_model_version="model-v1",
            current_admission_id="admission-1",
        )
        second = build_v24_loop_controls_report(
            loop_state(),
            recommendations(),
            requests(),
            current_model_version="model-v1",
            current_admission_id="admission-1",
        )

        self.assertEqual(first, second)
        self.assertEqual(first["control_status"], "pass")

    def test_budget_overrun_and_duplicates_fail_closed(self):
        report = build_v24_loop_controls_report(
            loop_state(),
            recommendations(),
            requests(
                {"request_id": "r-a", "candidate_id": "a", "budget": {"estimated_cost": 40.0}, "lineage": {"model_version": "model-v1"}},
                {"request_id": "r-a2", "candidate_id": "a", "budget": {"estimated_cost": 40.0}, "lineage": {"model_version": "model-v1"}},
            ),
            current_model_version="model-v1",
            current_admission_id="admission-1",
        )

        self.assertEqual(report["control_status"], "blocked")
        self.assertIn("budget_overrun", report["reason_codes"])
        self.assertIn("duplicate_candidate_request", report["reason_codes"])
        self.assertEqual(report["request_generation_allowed"], False)

    def test_stale_model_or_admission_blocks_generation(self):
        report = build_v24_loop_controls_report(
            loop_state(),
            recommendations(),
            requests(),
            current_model_version="model-v2",
            current_admission_id="admission-2",
        )

        self.assertIn("stale_model_version", report["reason_codes"])
        self.assertIn("stale_admission_report", report["reason_codes"])
        self.assertFalse(report["request_generation_allowed"])

    def test_future_observation_leakage_blocks_prior_decision(self):
        report = build_v24_loop_controls_report(
            loop_state(),
            recommendations(),
            requests(),
            current_model_version="model-v1",
            current_admission_id="admission-1",
            observations=[{"request_id": "r-a", "candidate_id": "a", "observed_at": "future"}],
        )

        self.assertEqual(report["control_status"], "blocked")
        self.assertIn("future_observation_leakage", report["reason_codes"])


if __name__ == "__main__":
    unittest.main()
