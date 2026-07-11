import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from spirosearch.acquisition_replay import evaluate_offline_replay
from spirosearch.artifact_repository import JsonArtifactRepository
from spirosearch.cli import main


def _candidates(model_wins=True):
    return [
        {"candidate_id": "a", "model_score": 0.9, "heuristic_score": 0.2, "observed_utility": 0.8 if model_wins else 0.1},
        {"candidate_id": "b", "model_score": 0.2, "heuristic_score": 0.9, "observed_utility": 0.4},
        {"candidate_id": "c", "model_score": 0.1, "heuristic_score": 0.1, "observed_utility": 0.2},
    ]


class AcquisitionReplayTests(unittest.TestCase):
    def test_replay_compares_observed_utility_on_same_candidate_pool(self):
        report = evaluate_offline_replay(
            _candidates(), request_id="request-1", model_version="model-v1", strategy="qlognehvi", batch_size=1
        )
        self.assertEqual(report["replay"]["status"], "non_regression")
        self.assertEqual(report["replay"]["model_selected_ids"], ["a"])
        self.assertEqual(report["replay"]["heuristic_selected_ids"], ["b"])
        self.assertGreater(report["replay"]["model_observed_utility"], report["replay"]["heuristic_observed_utility"])

    def test_replay_reports_regression_and_rejects_duplicate_candidates(self):
        report = evaluate_offline_replay(
            _candidates(model_wins=False), request_id="request-1", model_version="model-v1", strategy="qlognehvi", batch_size=1
        )
        self.assertEqual(report["replay"]["status"], "regression")
        duplicate = _candidates() + [_candidates()[0]]
        with self.assertRaisesRegex(ValueError, "duplicate"):
            evaluate_offline_replay(duplicate, request_id="r", model_version="m", strategy="qlognehvi")

    def test_acquisition_replay_cli_writes_manifest_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            directory = Path(temp_dir)
            input_path = directory / "replay-input.json"
            output_dir = directory / "run"
            input_path.write_text(
                json.dumps({
                    "request_id": "request-1",
                    "model_version": "model-v1",
                    "strategy": "qlognehvi",
                    "batch_size": 1,
                    "candidates": _candidates(),
                }),
                encoding="utf-8",
            )
            with patch("sys.argv", ["spirosearch", "acquisition-replay", "--input", str(input_path), "--output-dir", str(output_dir)]):
                self.assertEqual(main(), 0)

            result = JsonArtifactRepository.from_output_dir(output_dir).read_json("acquisition_breakdown")
            self.assertTrue(result.available, result.unavailable)
            self.assertEqual(result.payload["replay"]["status"], "non_regression")


if __name__ == "__main__":
    unittest.main()
