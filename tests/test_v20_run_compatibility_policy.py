import json
import subprocess
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from spirosearch.project_evolution import ReadOnlyProjectAPI, RunCompatibilityPolicy


FIXTURE_DIR = Path("tests/fixtures/v20_project_evolution")


BASE_DIMENSIONS = {
    "run_manifest_schema_version": "v6.run_manifest.v1",
    "screening_policy_version": "v12.screening_policy.v1",
    "scoring_formula_version": "formula-a",
    "scoring_weights_version": "weights-a",
    "target_profile_version": "profile-a",
    "dataset_snapshot_id": "snapshot-a",
    "candidate_pool_semantics_version": "pool-a",
    "candidate_identity_version": "identity-a",
}


class V20RunCompatibilityPolicyTests(unittest.TestCase):
    def test_policy_declares_rules_for_every_required_dimension(self):
        required = set(BASE_DIMENSIONS)
        self.assertEqual(set(RunCompatibilityPolicy().dimension_rules()), required)

    def test_table_driven_dimensions_fail_closed_with_stable_reason_codes(self):
        policy = RunCompatibilityPolicy()
        for dimension in BASE_DIMENSIONS:
            with self.subTest(dimension=dimension):
                source = dict(BASE_DIMENSIONS)
                target = dict(BASE_DIMENSIONS)
                target[dimension] = f"{target[dimension]}-changed"

                result = policy.evaluate(source, target)
                by_dimension = {item["dimension"]: item for item in result["dimensions"]}

                self.assertEqual(by_dimension[dimension]["status"], "non_comparable")
                self.assertEqual(by_dimension[dimension]["reason_codes"], [f"{dimension.upper()}_CHANGED"])
                self.assertIn(result["status"], {"partially_comparable", "non_comparable"})

    def test_missing_metadata_fails_closed_and_score_rank_is_unavailable(self):
        source = dict(BASE_DIMENSIONS)
        target = dict(BASE_DIMENSIONS)
        del target["scoring_weights_version"]

        result = RunCompatibilityPolicy().evaluate(source, target)
        score_rank = next(item for item in result["dimensions"] if item["dimension"] == "score_rank")

        self.assertEqual(result["status"], "partially_comparable")
        self.assertEqual(score_rank["status"], "non_comparable")
        self.assertIn("MISSING_SCORING_WEIGHTS_VERSION", score_rank["reason_codes"])
        self.assertFalse(result["score_rank_comparable"])

    def test_readonly_comparison_envelope_exposes_fixture_compatibility(self):
        envelope = ReadOnlyProjectAPI(FIXTURE_DIR).comparison("run-001", "run-002")

        self.assertEqual(envelope["status"], "degraded")
        self.assertEqual(envelope["surface"], "run_comparison")
        self.assertTrue(envelope["read_only"])
        self.assertEqual(envelope["payload"]["compatibility"]["status"], "partially_comparable")
        score_rank = next(
            item for item in envelope["payload"]["compatibility"]["dimensions"]
            if item["dimension"] == "score_rank"
        )
        self.assertEqual(score_rank["status"], "non_comparable")
        self.assertIn("DATASET_SNAPSHOT_CHANGED", score_rank["reason_codes"])
        Draft202012Validator(
            json.loads(Path("schemas/readonly-api-envelope.schema.json").read_text(encoding="utf-8"))
        ).validate(envelope)

    def test_frontend_renderer_uses_backend_compatibility_without_recomputing(self):
        script = r"""
const fs = require("fs");
const vm = require("vm");
const source = fs.readFileSync("frontend/artifact-viewer/viewer.js", "utf8");
function element() {
  return {
    addEventListener() {},
    appendChild() {},
    setAttribute() {},
    removeAttribute() {},
    focus() {},
    style: {},
    classList: {add() {}, remove() {}, toggle() {}},
    textContent: "",
    innerHTML: "",
    value: "",
    checked: false,
  };
}
const context = {
  console,
  window: {addEventListener() {}},
  document: {
    getElementById: () => element(),
    querySelector: () => element(),
    querySelectorAll: () => [],
    createElement: () => element(),
  },
};
vm.createContext(context);
vm.runInContext(source, context);
const html = context.renderRunCompatibilityDiagnostics({
  status: "partially_comparable",
  reason_codes: ["DATASET_SNAPSHOT_CHANGED"],
  dimensions: [{dimension: "score_rank", status: "non_comparable", reason_codes: ["DATASET_SNAPSHOT_CHANGED"]}]
});
if (!html.includes("partially_comparable") || !html.includes("score_rank") || !html.includes("DATASET_SNAPSHOT_CHANGED")) {
  throw new Error(html);
}
"""
        subprocess.run(["node", "-e", script], check=True, cwd=Path.cwd())


if __name__ == "__main__":
    unittest.main()
