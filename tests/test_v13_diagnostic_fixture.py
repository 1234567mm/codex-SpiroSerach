import tempfile
import unittest
import json
import subprocess
from pathlib import Path

from spirosearch.artifact_validation import validate_artifact_run
from spirosearch.readonly_api import ReadOnlyRunAPI
from spirosearch.v13_diagnostic_fixture import write_v13_diagnostic_fixture


class V13DiagnosticFixtureTests(unittest.TestCase):
    def test_fixture_closes_all_artifacts_and_algorithm_panels(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            write_v13_diagnostic_fixture(output_dir)

            report = validate_artifact_run(output_dir)
            self.assertEqual(report.status, "valid", report.to_dict())
            self.assertEqual(report.summary["artifact_count"], 11)

            diagnostics = ReadOnlyRunAPI(output_dir).algorithm_diagnostics()
            self.assertEqual(diagnostics["status"], "available")
            self.assertEqual(diagnostics["payload"]["available_count"], 6)
            panels = diagnostics["payload"]["panels"]
            screening = panels["screening_input_view"]["payload"]["data"]
            self.assertEqual({item["status"] for item in screening["candidates"]}, {"pass", "defer", "reject"})
            self.assertEqual(panels["model_evaluation"]["payload"]["data"]["activation_status"], "disabled")
            self.assertEqual(panels["acquisition_breakdown"]["payload"]["data"]["replay"]["status"], "non_regression")

    def test_committed_fixture_remains_valid(self):
        fixture_dir = Path("tests/fixtures/artifact_viewer/v13_algorithm_run")
        report = validate_artifact_run(fixture_dir)
        self.assertEqual(report.status, "valid", report.to_dict())
        self.assertEqual(report.summary["artifact_count"], 11)

    def test_static_viewer_renders_screening_and_model_diagnostics(self):
        runner = r'''
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {id, textContent: "", innerHTML: "", style: {}, addEventListener: () => {}});
  return elements.get(id);
}
const context = {console, Map, Number, String, JSON, document: {getElementById: element}};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);
const fixtureDir = process.argv[3];
const manifest = JSON.parse(fs.readFileSync(path.join(fixtureDir, "run-manifest.json"), "utf8"));
context.loadedManifest = manifest;
vm.runInContext("state.manifest = loadedManifest", context);
for (const artifact of manifest.artifacts) {
  const artifactText = fs.readFileSync(path.join(fixtureDir, artifact.path), "utf8");
  context.loadedArtifactPath = artifact.path;
  context.loadedArtifactPayload = context.parseArtifact(artifact.path, artifactText);
  vm.runInContext("state.artifacts.set(loadedArtifactPath, loadedArtifactPayload)", context);
}
context.renderKnownArtifacts();
process.stdout.write(JSON.stringify({
  screening: element("screeningEligibilityList").innerHTML,
  model: element("modelEvaluationList").innerHTML,
  screeningCount: element("screeningEligibilityCount").textContent,
  modelStatus: element("modelActivationStatus").textContent,
}));
'''
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as file:
            file.write(runner)
            runner_path = Path(file.name)
        try:
            result = subprocess.run(
                ["node", str(runner_path), "frontend/artifact-viewer/viewer.js", "tests/fixtures/artifact_viewer/v13_algorithm_run"],
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            runner_path.unlink(missing_ok=True)
        rendered = json.loads(result.stdout)
        self.assertEqual(rendered["screeningCount"], "3 candidates")
        self.assertIn("pass-1", rendered["screening"])
        self.assertIn("defer", rendered["screening"])
        self.assertIn("reject", rendered["screening"])
        self.assertEqual(rendered["modelStatus"], "disabled")
        self.assertIn("does_not_beat_heuristic", rendered["model"])


if __name__ == "__main__":
    unittest.main()
