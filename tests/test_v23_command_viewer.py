import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class V23CommandViewerTests(unittest.TestCase):
    def test_static_viewer_declares_command_state_panel(self):
        html = Path("frontend/artifact-viewer/index.html").read_text(encoding="utf-8")

        self.assertIn('id="commandStatePanel"', html)
        self.assertIn('id="commandStateCount"', html)
        self.assertIn('id="commandStateList"', html)
        self.assertIn("#commandStatePanel", html)

    def test_viewer_renders_command_states_from_manifest_paths_without_write_surface(self):
        self.assertIsNotNone(shutil.which("node"), "node is required for viewer behavior test")
        runner = r"""
const fs = require("fs");
const vm = require("vm");

const elements = new Map();
function element(id) {
  if (!elements.has(id)) {
    elements.set(id, {
      id,
      textContent: "",
      innerHTML: "",
      style: {},
      addEventListener: () => {},
    });
  }
  return elements.get(id);
}

const context = {
  console,
  Map,
  Number,
  String,
  JSON,
  document: {getElementById: element},
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);

vm.runInContext(`
state.manifest = {
  artifacts: [
    {kind: "v23_action_results", path: "commands/custom-action-results.jsonl"},
    {kind: "v23_recompute_job_status", path: "commands/jobs/recompute-job.json"}
  ]
};
state.artifacts.clear();
state.artifacts.set("v23/action-results.jsonl", [{request_id: "wrong-default", status: "accepted"}]);
state.artifacts.set("v23/recompute-jobs/wrong.json", {request_id: "wrong-job", job_status: "queued"});
state.artifacts.set("commands/custom-action-results.jsonl", [
  {request_id: "review-ok", action_type: "review_decision", status: "accepted", actor_id: "curator-a", reason_code: "command_preconditions_passed", message: "accepted"},
  {request_id: "recompute-pending", action_type: "recompute_request", status: "accepted", actor_id: "operator-a", reason_code: "command_preconditions_passed", message: "queued"},
  {request_id: "review-conflict", action_type: "review_decision", status: "conflict", actor_id: "curator-a", reason_code: "stale_target_version", message: "conflict"},
  {request_id: "review-failed", action_type: "review_decision", status: "rejected", actor_id: "operator-a", reason_code: "unauthorized_role", message: "<unsafe failure>"}
]);
state.artifacts.set("commands/jobs/recompute-job.json", {
  request_id: "recompute-pending",
  action_type: "recompute_request",
  job_status: "queued",
  result_status: "accepted",
  retry_state: {attempt: 0, retryable: false, last_status: "accepted"}
});
renderKnownArtifacts();
`, context);

process.stdout.write(JSON.stringify({
  count: element("commandStateCount").textContent,
  html: element("commandStateList").innerHTML,
}));
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as file:
            file.write(runner)
            runner_path = Path(file.name)
        try:
            result = subprocess.run(
                ["node", str(runner_path), "frontend/artifact-viewer/viewer.js"],
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            runner_path.unlink(missing_ok=True)

        rendered = json.loads(result.stdout)
        self.assertEqual(rendered["count"], "4 results / 1 jobs")
        self.assertIn("confirmation required", rendered["html"])
        self.assertIn("static viewer is read-only", rendered["html"])
        self.assertIn("success", rendered["html"])
        self.assertIn("pending", rendered["html"])
        self.assertIn("conflict", rendered["html"])
        self.assertIn("failure", rendered["html"])
        self.assertIn("queued", rendered["html"])
        self.assertIn("&lt;unsafe failure&gt;", rendered["html"])
        self.assertNotIn("<unsafe failure>", rendered["html"])
        self.assertNotIn("wrong-default", rendered["html"])
        self.assertNotIn("wrong-job", rendered["html"])

    def test_viewer_source_does_not_call_command_side_effects(self):
        script = Path("frontend/artifact-viewer/viewer.js").read_text(encoding="utf-8")

        self.assertNotIn("provider_execution", script)
        self.assertNotIn("experiment_dispatch", script)
        self.assertNotIn("model_training", script)
        self.assertNotIn("create_v23_command_registry", script)


if __name__ == "__main__":
    unittest.main()
