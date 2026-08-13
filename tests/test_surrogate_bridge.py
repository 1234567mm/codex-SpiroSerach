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
