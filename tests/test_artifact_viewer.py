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
        self.assertIn('id="canonicalEvidenceList"', html)
        self.assertIn('id="canonicalEvidenceCount"', html)
        self.assertIn('id="scoringViewList"', html)
        self.assertIn('id="scoringFactCount"', html)
        self.assertIn('id="reviewClosureList"', html)
        self.assertIn('id="reviewClosureCount"', html)
        self.assertIn('id="reviewQueueList"', html)
        self.assertIn('id="cacheSummary"', html)
        self.assertIn('id="errorState"', html)
        self.assertNotIn("landing", html.casefold())

    def test_viewer_script_parses_jsonl_and_renders_manifest_artifacts(self):
        script = Path("frontend/artifact-viewer/viewer.js").read_text(encoding="utf-8")

        self.assertIn("function parseJsonl", script)
        self.assertIn("function renderManifest", script)
        self.assertIn("function renderRecommendations", script)
        self.assertIn("function renderTimeline", script)
        self.assertIn("function renderEnrichmentFlow", script)
        self.assertIn("function renderCanonicalEvidence", script)
        self.assertIn("function renderScoringView", script)
        self.assertIn("function renderReviewClosure", script)
        self.assertIn("function getArtifact", script)
        self.assertIn("enrichment-results.json", script)
        self.assertIn("canonical-evidence.json", script)
        self.assertIn("provider-cache-index.json", script)
        self.assertIn("review-queue.jsonl", script)
        self.assertIn("review-events.jsonl", script)
        self.assertIn("review-summary.json", script)
        self.assertIn("recompute-markers.jsonl", script)
        self.assertIn("candidate_id", script)
        self.assertIn("cache_status", script)
        self.assertIn("review_item_id", script)
        self.assertIn("trace_event_id", script)
        self.assertIn("response_id", script)
        self.assertIn("lookup_id", script)
        self.assertIn("outcome", script)
        self.assertIn("energy_evidence", script)
        self.assertIn("eligible_for_scoring", script)
        self.assertIn("scoring_view", script)
        self.assertIn("safeCount(event.candidate_count)", script)
        self.assertIn("function safeCount", script)
        self.assertIn("function showError", script)
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

    def test_viewer_reports_jsonl_line_errors_preserves_manifest_counts_and_prefers_manifest_path(self):
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
  document: {
    getElementById: element,
  },
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);

let parseError = "";
try {
  context.parseArtifact("review-queue.jsonl", '{"ok":true}\n\n{bad}\n');
} catch (error) {
  parseError = error.message;
}

context.renderManifest({
  run_id: "legacy-run",
  candidate_count: 7,
  context: { provider_outcomes: { failure_count: 2 } },
});
context.renderEnrichmentFlow(null, null, [], []);

vm.runInContext(`
state.manifest = {
  artifacts: [{kind: "provider_cache_index", path: "nested/provider-cache-index.json"}]
};
state.artifacts.clear();
state.artifacts.set("provider-cache-index.json", {marker: "wrong-default"});
state.artifacts.set("nested/provider-cache-index.json", {marker: "manifest-path"});
`, context);
const matched = context.getArtifact("provider-cache-index.json", "provider_cache_index");
vm.runInContext('state.artifacts.delete("nested/provider-cache-index.json");', context);
const unmatched = context.getArtifact("provider-cache-index.json", "provider_cache_index");
context.showError("visible failure");
const errorText = element("errorState").textContent;
const errorDisplay = element("errorState").style.display;
context.clearError();
const clearedDisplay = element("errorState").style.display;

process.stdout.write(JSON.stringify({
  parseError,
  candidateCount: element("candidateCount").textContent,
  needsReviewCount: element("needsReviewCount").textContent,
  candidateFlow: element("candidateFlow").innerHTML,
  matched,
  unmatched,
  errorText,
  errorDisplay,
  clearedDisplay,
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
        self.assertIn("review-queue.jsonl line 3", rendered["parseError"])
        self.assertEqual(rendered["candidateCount"], "7")
        self.assertEqual(rendered["needsReviewCount"], "2")
        self.assertIn("No enrichment results loaded", rendered["candidateFlow"])
        self.assertEqual(rendered["matched"], {"marker": "manifest-path"})
        self.assertIsNone(rendered["unmatched"])
        self.assertEqual(rendered["errorText"], "visible failure")
        self.assertEqual(rendered["errorDisplay"], "block")
        self.assertEqual(rendered["clearedDisplay"], "none")

    def test_viewer_renders_canonical_evidence_with_material_use_and_energy_context(self):
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
  document: {
    getElementById: element,
  },
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);

context.renderCanonicalEvidence({
  records: [{
    candidate_id: "c1",
    material: {
      material_id: "c1",
      material_kind: "small_molecule",
      supplier_status: "available",
      synthesis_readiness: "commercial",
    },
    use_instance: {
      use_instance_id: "c1:HTL",
      material_id: "c1",
      role: "HTL",
      profile: "htl_replacement_profile",
    },
    energy_evidence: [{
      energy_evidence_id: "energy:c1:homo_ev",
      property_name: "homo_ev",
      value_ev: -5.2,
      unit: "eV",
      eligible_for_scoring: true,
      provenance: {
        provider_name: "legacy_candidate",
        trust_level: "T3_literature_machine",
        curation_status: "machine_extracted",
      },
    }],
    review_items: [{
      reason_code: "energy_levels_missing",
      severity: "medium",
    }],
  }],
});

process.stdout.write(JSON.stringify({
  count: element("canonicalEvidenceCount").textContent,
  html: element("canonicalEvidenceList").innerHTML,
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
        self.assertEqual(rendered["count"], "1 records")
        self.assertIn("c1", rendered["html"])
        self.assertIn("small_molecule", rendered["html"])
        self.assertIn("HTL", rendered["html"])
        self.assertIn("homo_ev -5.2 eV", rendered["html"])
        self.assertIn("eligible", rendered["html"])
        self.assertIn("legacy_candidate", rendered["html"])
        self.assertIn("energy_levels_missing", rendered["html"])

    def test_viewer_renders_scoring_view_from_manifest_path_without_default_filename_guess(self):
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
  document: {
    getElementById: element,
  },
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);

vm.runInContext(`
state.manifest = {
  artifacts: [{kind: "scoring_view", path: "nested/custom-score-payload.json"}]
};
state.artifacts.clear();
state.artifacts.set("scoring-view.json", {energy_facts: [{material_id: "wrong"}]});
state.artifacts.set("nested/custom-score-payload.json", {
  schema_version: "v10.scoring_view.v1",
  energy_facts: [{
    evidence_id: "energy:c1:homo_ev",
    material_id: "c1",
    use_instance_id: "c1:HTL",
    property_name: "homo_ev",
    value_ev: -5.2,
    unit: "eV",
    method: "reported",
    reference_scale: "vacuum",
    computed: false,
    quality: {
      quality_score: 0.85,
      trust_level: "T4_literature_curated",
      curation_status: "curated",
      eligible_for_scoring: true,
      blocking_review_count: 0,
      blocking_review_ids: [],
    },
  }],
});
renderKnownArtifacts();
`, context);
const matchedHtml = element("scoringViewList").innerHTML;
const matchedCount = element("scoringFactCount").textContent;

vm.runInContext(`
state.artifacts.clear();
state.artifacts.set("scoring-view.json", {energy_facts: [{material_id: "wrong"}]});
renderKnownArtifacts();
`, context);
const unmatchedHtml = element("scoringViewList").innerHTML;
const unmatchedCount = element("scoringFactCount").textContent;

process.stdout.write(JSON.stringify({
  matchedHtml,
  matchedCount,
  unmatchedHtml,
  unmatchedCount,
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
        self.assertEqual(rendered["matchedCount"], "1 facts")
        self.assertIn("c1", rendered["matchedHtml"])
        self.assertIn("homo_ev -5.2 eV", rendered["matchedHtml"])
        self.assertIn("quality 0.85", rendered["matchedHtml"])
        self.assertNotIn("wrong", rendered["matchedHtml"])
        self.assertEqual(rendered["unmatchedCount"], "0 facts")
        self.assertIn("No scoring view loaded", rendered["unmatchedHtml"])
        self.assertNotIn("wrong", rendered["unmatchedHtml"])

    def test_viewer_renders_review_closure_artifacts_from_manifest_paths(self):
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
  document: {
    getElementById: element,
  },
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);

vm.runInContext(`
state.manifest = {
  artifacts: [
    {kind: "review_events", path: "review/run-events.jsonl"},
    {kind: "review_summary", path: "review/summary.json"},
    {kind: "recompute_markers", path: "review/recompute.jsonl"}
  ]
};
state.artifacts.clear();
state.artifacts.set("review-events.jsonl", [{event_id: "wrong-event"}]);
state.artifacts.set("review-summary.json", {review_count: 99});
state.artifacts.set("recompute-markers.jsonl", [{marker_id: "wrong-marker"}]);
state.artifacts.set("review/run-events.jsonl", [{
  event_id: "event-reject-homo-abcdef",
  event_type: "review_rejected",
  review_item_id: "review-homo-abcdef",
  target_type: "energy_evidence",
  target_id: "energy:c1:homo_ev",
  reviewer: "curator_1",
  decision: "reject",
  resolution_status: "rejected",
  reason: "<unsafe reason>",
  recompute_marker_ids: ["marker-recompute-abcdef"]
}]);
state.artifacts.set("review/summary.json", {
  run_id: "run-review-closure-abcdef",
  generated_at: "2026-07-09T00:00:00+00:00",
  review_count: 2,
  event_count: 1,
  applied_event_count: 1,
  open_blocking_count: 0,
  resolved_count: 0,
  rejected_count: 1,
  by_resolution_status: {rejected: 1, open: 1},
  by_reason_code: {energy_levels_missing: 1, "reference scale": 1},
  by_assigned_queue: {energy: 2},
  by_severity: {high: 1, medium: 1},
  review_item_ids: ["review-homo-abcdef"],
  review_event_ids: ["event-reject-homo-abcdef"],
  recompute_marker_ids: ["marker-recompute-abcdef"]
});
state.artifacts.set("review/recompute.jsonl", [{
  marker_id: "marker-recompute-abcdef",
  review_event_id: "event-reject-homo-abcdef",
  review_item_id: "review-homo-abcdef",
  candidate_id: "c1",
  target_type: "energy_evidence",
  target_id: "energy:c1:homo_ev",
  affected_artifacts: ["canonical-evidence.json", "scoring-view.json"],
  reason: "review closure",
  status: "pending"
}]);
renderKnownArtifacts();
`, context);

process.stdout.write(JSON.stringify({
  count: element("reviewClosureCount").textContent,
  html: element("reviewClosureList").innerHTML,
  emailReviewerLabel: vm.runInContext('reviewerLabel("curator@example")', context),
  userReviewerLabel: vm.runInContext('reviewerLabel("curator_1")', context),
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
        self.assertEqual(rendered["count"], "1 events / 1 markers")
        self.assertIn("run run-review-c", rendered["html"])
        self.assertIn("generated 2026-07-09T00:00:00+00:00", rendered["html"])
        self.assertIn("review_count 2", rendered["html"])
        self.assertIn("open_blocking 0", rendered["html"])
        self.assertIn("rejected 1", rendered["html"])
        self.assertIn("event-reject", rendered["html"])
        self.assertIn("reviewer human reviewer", rendered["html"])
        self.assertNotIn("curator@example", rendered["html"])
        self.assertNotIn("curator_1", rendered["html"])
        self.assertEqual(rendered["emailReviewerLabel"], "human reviewer")
        self.assertEqual(rendered["userReviewerLabel"], "human reviewer")
        self.assertIn("review review-homo", rendered["html"])
        self.assertIn("marker-recom", rendered["html"])
        self.assertIn("canonical-evidence.json", rendered["html"])
        self.assertIn("scoring-view.json", rendered["html"])
        self.assertIn("&lt;unsafe reason&gt;", rendered["html"])
        self.assertNotIn("<unsafe reason>", rendered["html"])
        self.assertNotIn("wrong-event", rendered["html"])
        self.assertNotIn("wrong-marker", rendered["html"])


if __name__ == "__main__":
    unittest.main()
