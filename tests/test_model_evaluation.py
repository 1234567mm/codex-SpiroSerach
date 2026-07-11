import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from spirosearch.acquisition_replay import evaluate_offline_replay
from spirosearch.artifact_repository import JsonArtifactRepository
from spirosearch.cli import main
from spirosearch.contracts import EXIT_VALIDATION_ERROR
from spirosearch.model_evaluation import evaluate_grouped_snapshot
from spirosearch.prediction_dataset import build_training_snapshot


class _LinearModel:
    def fit(self, X, y):
        self._fitted = True

    def predict(self, X):
        return tuple(2.0 * row["x"] + 1.0 for row in X)

    def uncertainty(self, X):
        return tuple(0.5 for _ in X)


class _BadModel(_LinearModel):
    def predict(self, X):
        return tuple(100.0 for _ in X)


class _OneFoldRegressionModel(_LinearModel):
    def predict(self, X):
        return tuple(12.0 if row["x"] == 7.0 else 2.0 * row["x"] + 1.0 for row in X)


def _snapshot():
    return build_training_snapshot(
        [{"x": float(value)} for value in range(8)],
        [{"pce": 2.0 * value + 1.0} for value in range(8)],
        [f"material-{value}" for value in range(8)],
        [f"source-{value}" for value in range(8)],
        random_seed=7,
    )


class ModelEvaluationTests(unittest.TestCase):
    def test_grouped_evaluation_reports_baselines_calibration_and_eligibility(self):
        result = evaluate_grouped_snapshot(
            _snapshot(),
            objective_name="pce",
            model_factory=_LinearModel,
            model_version="linear-v1",
            surrogate_type="TEST_LINEAR",
            replay_status="non_regression",
        )

        payload = result.to_dict()
        self.assertEqual(payload["schema_version"], "v13.model_evaluation.v1")
        self.assertEqual(payload["activation_status"], "eligible")
        self.assertEqual(payload["activation_reasons"], [])
        self.assertLess(payload["metrics"]["rmse"], payload["baselines"]["dummy"]["rmse"])
        self.assertIn("heuristic", payload["baselines"])
        self.assertEqual(payload["calibration"]["coverage_95"], 1.0)
        self.assertGreaterEqual(len(payload["folds"]), 2)

    def test_evaluation_disables_regressing_model_with_reasons(self):
        result = evaluate_grouped_snapshot(
            _snapshot(),
            objective_name="pce",
            model_factory=_BadModel,
            model_version="bad-v1",
            surrogate_type="TEST_BAD",
            replay_status="regression",
        )

        self.assertEqual(result.activation_status, "disabled")
        self.assertIn("does_not_beat_dummy", result.activation_reasons)
        self.assertIn("offline_replay_regressed", result.activation_reasons)

    def test_evaluation_requires_every_fold_to_beat_baselines(self):
        result = evaluate_grouped_snapshot(
            _snapshot(),
            objective_name="pce",
            model_factory=_OneFoldRegressionModel,
            model_version="partial-regression-v1",
            surrogate_type="TEST_PARTIAL_REGRESSION",
            replay_status="non_regression",
        )

        self.assertEqual(result.activation_status, "disabled")
        self.assertTrue(
            any(reason.endswith("does_not_beat_heuristic") for reason in result.activation_reasons)
        )

    def test_evaluation_rejects_missing_target_and_too_few_folds(self):
        with self.assertRaisesRegex(ValueError, "objective"):
            evaluate_grouped_snapshot(
                _snapshot(),
                objective_name="stability",
                model_factory=_LinearModel,
                model_version="linear-v1",
                surrogate_type="TEST_LINEAR",
            )

    def test_model_evaluate_cli_writes_manifest_discovered_disabled_report(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            snapshot_path = directory / "input-snapshot.json"
            output_dir = directory / "run"
            snapshot_path.write_text(json.dumps(_snapshot().to_dict()), encoding="utf-8")
            with patch(
                "sys.argv",
                [
                    "spirosearch",
                    "model-evaluate",
                    "--snapshot",
                    str(snapshot_path),
                    "--objective",
                    "pce",
                    "--model",
                    "heuristic",
                    "--model-version",
                    "heuristic-v1",
                    "--output-dir",
                    str(output_dir),
                ],
            ):
                self.assertEqual(main(), 0)

            repository = JsonArtifactRepository.from_output_dir(output_dir)
            evaluation = repository.read_json("model_evaluation")
            self.assertTrue(evaluation.available, evaluation.unavailable)
            self.assertEqual(evaluation.payload["activation_status"], "disabled")
            self.assertIn("offline_replay_unavailable", evaluation.payload["activation_reasons"])
            self.assertTrue(repository.read_json("training_snapshot").available)

    def test_model_evaluate_cli_rejects_tampered_replay_status(self):
        replay = evaluate_offline_replay(
            [
                {
                    "candidate_id": "candidate-a",
                    "model_score": 2.0,
                    "heuristic_score": 1.0,
                    "observed_utility": 0.0,
                },
                {
                    "candidate_id": "candidate-b",
                    "model_score": 1.0,
                    "heuristic_score": 2.0,
                    "observed_utility": 1.0,
                },
            ],
            request_id="replay-1",
            model_version="heuristic-v1",
            strategy="heuristic",
        )
        self.assertEqual(replay["replay"]["status"], "regression")
        replay["replay"]["status"] = "non_regression"

        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            snapshot_path = directory / "input-snapshot.json"
            replay_path = directory / "replay.json"
            snapshot_path.write_text(json.dumps(_snapshot().to_dict()), encoding="utf-8")
            replay_path.write_text(json.dumps(replay), encoding="utf-8")
            with patch(
                "sys.argv",
                [
                    "spirosearch",
                    "model-evaluate",
                    "--snapshot",
                    str(snapshot_path),
                    "--objective",
                    "pce",
                    "--model",
                    "heuristic",
                    "--model-version",
                    "heuristic-v1",
                    "--replay-report",
                    str(replay_path),
                    "--output-dir",
                    str(directory / "run"),
                ],
            ):
                self.assertEqual(main(), EXIT_VALIDATION_ERROR)


if __name__ == "__main__":
    unittest.main()
