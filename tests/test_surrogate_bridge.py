import json
import subprocess
import sys
import unittest

from spirosearch.surrogate_bridge import BRIDGE_SCHEMA_VERSION, _handle


class SurrogateBridgeHandleTests(unittest.TestCase):
    def test_stop_action(self):
        response = _handle({"action": "stop", "model_id": "m"})
        self.assertTrue(response["ok"])
        self.assertEqual(response["action"], "stop")

    def test_unknown_action_fails_closed(self):
        response = _handle({"action": "explode", "model_id": "m"})
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "unknown_action")

    def test_missing_model_id_fails_closed(self):
        response = _handle({"action": "predict"})
        self.assertFalse(response["ok"])
        self.assertEqual(response["error_code"], "model_id_required")

    def test_fit_without_sklearn_fails_closed_with_actionable_error(self):
        # With the optional [ml] group absent, fit must fail closed with an
        # actionable error instead of crashing the bridge process.
        response = _handle({"action": "fit", "model_id": "m", "X": [{"homo_ev": -5.1}], "y": [1.0]})
        if response["ok"]:
            self.assertEqual(response["schema_version"], BRIDGE_SCHEMA_VERSION)
            self.assertIn("fit_result", response)
            self.assertIn("provenance", response)
            return
        self.assertEqual(response["error_code"], "unsupported_surrogate")
        self.assertIn("scikit-learn", response["message"])

    def test_fit_then_predict_with_ml(self):
        # Full fit -> predict chain against real sklearn (skipped without the
        # optional [ml] dependency group).
        try:
            import sklearn  # noqa: F401
        except ImportError:
            self.skipTest("scikit-learn not installed (optional [ml] group)")
        fit_response = _handle({
            "action": "fit", "model_id": "gp-1",
            "X": [
                {"homo_ev": -5.1, "lumo_ev": -2.0, "band_gap_ev": 3.1},
                {"homo_ev": -5.3, "lumo_ev": -1.9, "band_gap_ev": 3.4},
                {"homo_ev": -4.9, "lumo_ev": -2.2, "band_gap_ev": 2.7},
            ],
            "y": [1.0, 0.8, 0.6],
        })
        self.assertTrue(fit_response["ok"], fit_response)
        self.assertIn("fit_result", fit_response)
        provenance = fit_response["provenance"]
        self.assertEqual(provenance["surrogate_type"], "SKLEARN_GPR")
        self.assertNotEqual(provenance["training_set_hash"], "")
        self.assertIn("homo_ev", provenance["feature_names"])

        predict_response = _handle({
            "action": "predict", "model_id": "gp-1",
            "X": [{"homo_ev": -5.2, "lumo_ev": -2.0, "band_gap_ev": 3.2}],
        })
        self.assertTrue(predict_response["ok"], predict_response)
        self.assertEqual(len(predict_response["values"]), 1)
        self.assertEqual(predict_response["provenance"]["training_set_hash"], provenance["training_set_hash"])

        uncertainty_response = _handle({
            "action": "uncertainty", "model_id": "gp-1",
            "X": [{"homo_ev": -5.2, "lumo_ev": -2.0, "band_gap_ev": 3.2}],
        })
        self.assertTrue(uncertainty_response["ok"], uncertainty_response)
        self.assertGreaterEqual(uncertainty_response["values"][0], 0.0)

        acquisition_response = _handle({
            "action": "acquisition", "model_id": "gp-1", "strategy": "ucb",
            "X": [{"homo_ev": -5.2, "lumo_ev": -2.0, "band_gap_ev": 3.2}],
        })
        self.assertTrue(acquisition_response["ok"], acquisition_response)
        self.assertEqual(len(acquisition_response["values"]), 1)

    def test_bridge_module_runs_as_process(self):
        # End-to-end: the module starts, answers a stop request, and exits.
        result = subprocess.run(
            [sys.executable, "-m", "spirosearch.surrogate_bridge"],
            input=json.dumps({"action": "stop", "model_id": "m"}) + "\n",
            capture_output=True,
            text=True,
            timeout=30,
            env=None,
        )
        self.assertEqual(result.returncode, 0)
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        self.assertGreaterEqual(len(lines), 1)
        response = json.loads(lines[-1])
        self.assertTrue(response["ok"])
        self.assertEqual(response["action"], "stop")


if __name__ == "__main__":
    unittest.main()
