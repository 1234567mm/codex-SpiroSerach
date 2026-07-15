import json
import unittest
from pathlib import Path

from jsonschema import validate

from spirosearch.artifacts import ARTIFACT_KIND_METADATA
from spirosearch.model_evaluation import evaluate_grouped_snapshot
from spirosearch.prediction_dataset import build_training_snapshot
from spirosearch.v22_scientific import build_v22_model_activation_report


class _LinearModel:
    def fit(self, X, y):
        pass

    def predict(self, X):
        return tuple(2.0 * row["x"] + 1.0 for row in X)

    def uncertainty(self, X):
        return tuple(0.5 for _ in X)


class _BadModel(_LinearModel):
    def predict(self, X):
        return tuple(100.0 for _ in X)


def _snapshot():
    return build_training_snapshot(
        [{"x": float(value)} for value in range(8)],
        [{"pce": 2.0 * value + 1.0} for value in range(8)],
        [f"material-{value}" for value in range(8)],
        [f"source-{value}" for value in range(8)],
        random_seed=7,
    )


class V22ModelActivationTests(unittest.TestCase):
    def test_activation_report_records_grouped_evaluation_and_registers_manifest_kind(self):
        evaluation = evaluate_grouped_snapshot(
            _snapshot(),
            objective_name="pce",
            model_factory=_LinearModel,
            model_version="linear-v1",
            surrogate_type="TEST_LINEAR",
            replay_status="non_regression",
        )
        report = build_v22_model_activation_report(
            evaluation,
            {
                "closure_gate_status": "pass",
                "retained_record_ids": ["i1", "i2"],
            },
            minimum_retained_records=2,
        )

        self.assertEqual(report["closure_gate_status"], "pass")
        self.assertEqual(report["activation_status"], "eligible")
        self.assertEqual(report["activation_reasons"], [])
        self.assertEqual(report["grouped_evaluation"]["split_policy"], "fold_id_grouped_cross_validation")
        self.assertIn("dummy", report["grouped_evaluation"]["baselines"])
        self.assertEqual(report["grouped_evaluation"]["replay_status"], "non_regression")
        self.assertEqual(report["disabled_model_state"]["downstream_consumer"], "v24_admission")
        self.assertTrue(report["disabled_model_state"]["may_rank_candidates"])
        self.assertIn("v22_model_activation_report", ARTIFACT_KIND_METADATA)
        validate(report, json.loads(Path("schemas/v22-model-activation-report.schema.json").read_text(encoding="utf-8")))

    def test_activation_report_disables_for_bad_model_and_insufficient_independent_data(self):
        evaluation = evaluate_grouped_snapshot(
            _snapshot(),
            objective_name="pce",
            model_factory=_BadModel,
            model_version="bad-v1",
            surrogate_type="TEST_BAD",
            replay_status="regression",
        )
        report = build_v22_model_activation_report(
            evaluation,
            {
                "closure_gate_status": "blocked",
                "retained_record_ids": ["i1"],
            },
            minimum_retained_records=2,
        )

        self.assertEqual(report["closure_gate_status"], "blocked")
        self.assertEqual(report["activation_status"], "disabled")
        self.assertFalse(report["disabled_model_state"]["may_rank_candidates"])
        self.assertIn("does_not_beat_dummy", report["activation_reasons"])
        self.assertIn("offline_replay_regressed", report["activation_reasons"])
        self.assertIn("insufficient_independent_data", report["activation_reasons"])
        self.assertIn("independent_validation_blocked", report["activation_reasons"])

    def test_activation_report_disables_tampered_replay(self):
        evaluation = evaluate_grouped_snapshot(
            _snapshot(),
            objective_name="pce",
            model_factory=_LinearModel,
            model_version="linear-v1",
            surrogate_type="TEST_LINEAR",
            replay_status="non_regression",
        )
        report = build_v22_model_activation_report(
            evaluation,
            {
                "closure_gate_status": "pass",
                "retained_record_ids": ["i1", "i2"],
            },
            minimum_retained_records=2,
            replay_verification_status="tampered",
        )

        self.assertEqual(report["activation_status"], "disabled")
        self.assertIn("offline_replay_tampered", report["activation_reasons"])


if __name__ == "__main__":
    unittest.main()
