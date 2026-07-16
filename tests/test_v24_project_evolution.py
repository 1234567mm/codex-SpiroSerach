import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from spirosearch.artifacts import ARTIFACT_KIND_METADATA
from spirosearch.v24_project_evolution import build_v24_project_evolution


class V24ProjectEvolutionTests(unittest.TestCase):
    def test_project_evolution_view_summarizes_efficiency_decisions_and_model_state(self):
        view = build_v24_project_evolution(
            loop_state={"loop_state_id": "loop-1", "round_id": "round-1", "loop_status": "admitted", "model_evaluation": {"model_version": "model-v1"}},
            recommendations={"items": [{"candidate_id": "a"}, {"candidate_id": "b"}]},
            experiment_requests={"requests": [{"request_id": "r-a"}, {"request_id": "r-b"}]},
            observation_import={"accepted_observations": [{"request_id": "r-a"}], "rejected_observations": [{"request_id": "r-b"}]},
            controls_report={"control_status": "pass", "reason_codes": []},
        )

        self.assertEqual(view["round_efficiency"]["accepted_observation_count"], 1)
        self.assertEqual(view["decisions"]["requested_count"], 2)
        self.assertEqual(view["model_state_change"]["model_version"], "model-v1")
        self.assertIn("v24_project_evolution", ARTIFACT_KIND_METADATA)

    def test_missing_v24_artifacts_degrade_explicitly(self):
        view = build_v24_project_evolution(loop_state=None, recommendations=None, experiment_requests=None, observation_import=None, controls_report=None)

        self.assertEqual(view["view_status"], "degraded")
        self.assertIn("loop_state_missing", view["diagnostics"])

    def test_viewer_renders_v24_project_evolution_from_manifest_path(self):
        self.assertIsNotNone(shutil.which("node"), "node is required for viewer behavior test")
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {id, textContent: "", innerHTML: "", style: {}, addEventListener: () => {}});
  return elements.get(id);
}
const context = {console, Map, Number, String, JSON, document: {getElementById: element}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);
vm.runInContext(`
state.manifest = {artifacts: [{kind: "v24_project_evolution", path: "nested/v24-evolution.json"}]};
state.artifacts.clear();
state.artifacts.set("v24-project-evolution.json", {round_efficiency: {recommended_count: 99}});
state.artifacts.set("nested/v24-evolution.json", {
  view_status: "available",
  round_efficiency: {recommended_count: 2, requested_count: 2, accepted_observation_count: 1},
  decisions: {loop_status: "admitted", control_status: "pass", requested_count: 2},
  model_state_change: {model_version: "model-v1", loop_state_id: "loop-1"},
  diagnostics: []
});
renderKnownArtifacts();
`, context);
process.stdout.write(JSON.stringify({count: element("v24ProjectEvolutionCount").textContent, html: element("v24ProjectEvolutionList").innerHTML}));
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as file:
            file.write(runner)
            runner_path = Path(file.name)
        try:
            result = subprocess.run(["node", str(runner_path), "frontend/artifact-viewer/viewer.js"], check=True, capture_output=True, text=True)
        finally:
            runner_path.unlink(missing_ok=True)
        rendered = json.loads(result.stdout)

        self.assertEqual(rendered["count"], "available")
        self.assertIn("recommended 2", rendered["html"])
        self.assertIn("requested 2", rendered["html"])
        self.assertIn("accepted observations 1", rendered["html"])
        self.assertIn("model-v1", rendered["html"])
        self.assertNotIn("99", rendered["html"])


if __name__ == "__main__":
    unittest.main()
