import json
import unittest
from pathlib import Path

from spirosearch.beard_cole_training import build_beard_cole_training_snapshot
from spirosearch.model_evaluation import evaluate_grouped_snapshot
from spirosearch.prediction_dataset import build_training_snapshot


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "beard_cole"


class _MeanModel:
    def fit(self, features, targets):
        self._mean = sum(targets) / len(targets)
        return self

    def predict(self, features):
        return [self._mean for _ in features]

    def uncertainty(self, features):
        return [1.0 for _ in features]


class _LowCoverageModel:
    def fit(self, features, targets):
        return self

    def predict(self, features):
        return [row["signal"] + (1.0 if row["signal"] == 4.0 else 0.0) for row in features]

    def uncertainty(self, features):
        return [0.1 for _ in features]


class _WideIntervalModel:
    def fit(self, features, targets):
        return self

    def predict(self, features):
        return [row["signal"] for row in features]

    def uncertainty(self, features):
        return [10.0 for _ in features]


def _synthetic_snapshot():
    return build_training_snapshot(
        [{"signal": 1.0}, {"signal": 2.0}, {"signal": 3.0}, {"signal": 4.0}],
        [{"pce": 1.0}, {"pce": 2.0}, {"pce": 3.0}, {"pce": 4.0}],
        ["m1", "m2", "m3", "m4"],
        ["s1", "s2", "s3", "s4"],
        source_row_ids=["r1", "r2", "r3", "r4"],
    )


def _beard_cole_training_result():
    records = json.loads((FIXTURE_DIR / "psc_records.json").read_text(encoding="utf-8"))
    manifest = json.loads((FIXTURE_DIR / "source-manifest.json").read_text(encoding="utf-8"))
    return build_beard_cole_training_snapshot(records, manifest)


class BeardColeModelGateTests(unittest.TestCase):
    def test_v17_gate_requires_coverage_at_least_085(self) -> None:
        result = evaluate_grouped_snapshot(
            _synthetic_snapshot(),
            objective_name="pce",
            model_factory=_LowCoverageModel,
            model_version="low-coverage-v1",
            surrogate_type="TEST_LOW_COVERAGE",
            replay_status="non_regression",
        )

        self.assertEqual(result.calibration["coverage_95"], 0.75)
        self.assertEqual(result.activation_status, "disabled")
        self.assertIn("uncertainty_not_calibrated", result.activation_reasons)

    def test_v17_gate_blocks_known_leakage_and_unresolved_reviews(self) -> None:
        result = evaluate_grouped_snapshot(
            _synthetic_snapshot(),
            objective_name="pce",
            model_factory=_WideIntervalModel,
            model_version="blocked-v1",
            surrogate_type="TEST_BLOCKED",
            replay_status="non_regression",
            data_leakage_count=1,
            blocking_review_count=2,
        )

        self.assertEqual(result.activation_status, "disabled")
        self.assertIn("data_leakage_detected", result.activation_reasons)
        self.assertIn("blocking_reviews_unresolved", result.activation_reasons)

    def test_beard_cole_fixture_stays_disabled_with_non_regression_replay_status(self) -> None:
        training = _beard_cole_training_result()

        result = evaluate_grouped_snapshot(
            training.snapshot,
            objective_name="pce",
            model_factory=_MeanModel,
            model_version="beard-cole-mean-v1",
            surrogate_type="TEST_MEAN",
            replay_status="non_regression",
            data_leakage_count=training.quality_report.fold_leakage_count,
            blocking_review_count=0,
        )

        self.assertEqual(training.quality_report.fold_leakage_count, 0)
        self.assertEqual(result.replay_status, "non_regression")
        self.assertEqual(result.activation_status, "disabled")
        self.assertTrue(result.activation_reasons)


if __name__ == "__main__":
    unittest.main()
