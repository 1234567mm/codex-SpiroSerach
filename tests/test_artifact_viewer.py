import unittest
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


class ArtifactViewerTests(unittest.TestCase):
    def test_static_viewer_exposes_manifest_and_artifact_file_inputs(self):
        html = Path("frontend/artifact-viewer/index.html").read_text(encoding="utf-8")

        self.assertIn('id="manifestFile"', html)
        self.assertIn('id="artifactFiles"', html)
        self.assertIn('id="artifactTable"', html)
        self.assertIn('id="recommendationList"', html)
        self.assertIn('id="timeline"', html)
        self.assertIn('id="candidateFlow"', html)
        self.assertIn('id="reviewQueueList"', html)
        self.assertIn('id="cacheSummary"', html)
        self.assertNotIn("landing", html.casefold())

    def test_viewer_script_parses_jsonl_and_renders_manifest_artifacts(self):
        script = Path("frontend/artifact-viewer/viewer.js").read_text(encoding="utf-8")

        self.assertIn("function parseJsonl", script)
        self.assertIn("function renderManifest", script)
        self.assertIn("function renderRecommendations", script)
        self.assertIn("function renderTimeline", script)
        self.assertIn("function renderEnrichmentFlow", script)
        self.assertIn("function getArtifact", script)
        self.assertIn("enrichment-results.json", script)
        self.assertIn("provider-cache-index.json", script)
        self.assertIn("review-queue.jsonl", script)
        self.assertIn("candidate_id", script)
        self.assertIn("cache_status", script)
        self.assertIn("review_item_id", script)
        self.assertIn("trace_event_id", script)
        self.assertIn("response_id", script)
        self.assertIn("lookup_id", script)
        self.assertIn("outcome", script)
        self.assertIn("safeCount(event.candidate_count)", script)
        self.assertIn("function safeCount", script)
        self.assertIn("escapeHtml", script)

    def test_viewer_renders_enrichment_flow_with_precise_review_correlation_and_escaping(self):
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
  document: {
    getElementById: element,
  },
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);

const parsedJsonl = context.parseJsonl('{"a":1}\n\n{"b":2}\n');
const enrichment = {
  records: [{
    candidate_id: "c1",
    name: "<script>alert(1)</script>",
    status: "needs_review",
    missing_fields: ["homo_ev"],
    review_item_ids: ["review-a"],
  }],
};
const cacheIndex = {
  hit_count: 0,
  miss_count: 1,
  failure_count: 0,
  entries: [{
    candidate_id: "c1",
    provider: "pubchem",
    cache_status: "miss",
    cache_key: "cache-key-abcdef",
    raw_hash: "raw-hash-abcdef",
    trace_event_id: "trace-1234567890",
  }],
};
const reviewQueue = [
  {
    review_item_id: "review-a",
    target_id: "different-target",
    reason: "pubchem_structure_ambiguous",
    provider: "pubchem",
    cache_status: "miss",
    trace_event_id: "trace-1234567890",
    lookup_id: "lookup-1234567890",
    response_id: "response-1234567890",
    severity: "needs_curator",
  },
  {
    review_item_id: "review-wrong",
    target_id: "c1",
    reason: "wrong_reason",
    severity: "needs_curator",
  },
];
const trace = [{
  event_id: "trace-1234567890",
  event_type: "provider_lookup",
  provider: "pubchem",
  outcome: "provider_fetch_succeeded",
}];

context.renderEnrichmentFlow(enrichment, cacheIndex, reviewQueue, trace);
context.renderReviewQueue(reviewQueue);

process.stdout.write(JSON.stringify({
  parsedCount: parsedJsonl.length,
  candidateFlow: element("candidateFlow").innerHTML,
  reviewQueueList: element("reviewQueueList").innerHTML,
  cacheSummary: element("cacheSummary").textContent,
  candidateCount: element("candidateCount").textContent,
  needsReviewCount: element("needsReviewCount").textContent,
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
        self.assertEqual(rendered["parsedCount"], 2)
        self.assertEqual(rendered["cacheSummary"], "hit 0 / miss 1 / failed 0")
        self.assertEqual(rendered["candidateCount"], "1")
        self.assertEqual(rendered["needsReviewCount"], "1")
        self.assertIn("pubchem_structure_ambiguous", rendered["candidateFlow"])
        self.assertIn("provider pubchem", rendered["candidateFlow"])
        self.assertIn("cache miss", rendered["candidateFlow"])
        self.assertIn("outcome provider_fetch_succeeded", rendered["candidateFlow"])
        self.assertIn("trace trace-123456", rendered["candidateFlow"])
        self.assertIn("lookup lookup-12345", rendered["candidateFlow"])
        self.assertIn("response response-123", rendered["candidateFlow"])
        self.assertIn("review review-a", rendered["candidateFlow"])
        self.assertNotIn("wrong_reason", rendered["candidateFlow"])
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", rendered["candidateFlow"])
        self.assertNotIn("<script>alert(1)</script>", rendered["candidateFlow"])
        self.assertIn("review-a", rendered["reviewQueueList"])


if __name__ == "__main__":
    unittest.main()
