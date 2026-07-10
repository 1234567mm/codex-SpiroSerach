import hashlib
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

from spirosearch.artifact_repository import JsonArtifactRepository
from spirosearch.artifact_validation import validate_artifact_run
from spirosearch.artifacts import ARTIFACT_KIND_METADATA


FIXTURE_DIR = Path("tests/fixtures/artifact_viewer/v11_diagnostic_run")
VALID_REPORT_PATH = FIXTURE_DIR / "artifact-validation-report.valid.json"
DEGRADED_REPORT_PATH = FIXTURE_DIR / "artifact-validation-report.degraded.json"

EXPECTED_KINDS = {
    "recommendations",
    "agent_trace",
    "enrichment_results",
    "provider_cache_index",
    "provider_cache",
    "review_queue",
    "canonical_evidence",
    "scoring_view",
    "review_events",
    "review_summary",
    "recompute_markers",
}

OPTIONAL_PANELS = {
    "conflict_events": "Conflict Panel",
    "performance_timeline": "Performance/Error Timeline",
}


class V11VisualizationFixtureTests(unittest.TestCase):
    def test_v11_diagnostic_fixture_manifest_and_payloads_validate(self):
        repository = JsonArtifactRepository.from_output_dir(FIXTURE_DIR)
        manifest_status = repository.manifest_status()
        self.assertTrue(manifest_status.available, manifest_status.unavailable)

        manifest = manifest_status.payload
        self.assertEqual(manifest["run_id"], "v11-diagnostic-run-001")
        artifacts = manifest["artifacts"]
        self.assertEqual({artifact["kind"] for artifact in artifacts}, EXPECTED_KINDS)
        self.assertEqual(len(artifacts), len(EXPECTED_KINDS))

        for artifact in artifacts:
            kind = artifact["kind"]
            fixture_path = FIXTURE_DIR / artifact["path"]
            self.assertEqual(Path(artifact["path"]).name, artifact["path"])
            self.assertTrue(fixture_path.exists(), artifact["path"])
            content = fixture_path.read_bytes()
            self.assertEqual(artifact["sha256"], hashlib.sha256(content).hexdigest(), kind)
            self.assertEqual(artifact["bytes"], len(content), kind)
            if artifact["format"] == "jsonl":
                expected_records = sum(1 for line in content.decode("utf-8").splitlines() if line.strip())
                self.assertEqual(artifact["record_count"], expected_records, kind)
                read_result = repository.read_jsonl(kind)
            else:
                self.assertIsNone(artifact["record_count"], kind)
                read_result = repository.read_json(kind)

            expected_metadata = ARTIFACT_KIND_METADATA[kind]
            self.assertEqual(artifact["schema_ref"], expected_metadata["schema_ref"], kind)
            self.assertEqual(tuple(artifact["join_keys"]), expected_metadata["join_keys"], kind)
            self.assertEqual(tuple(artifact["depends_on"]), expected_metadata["depends_on"], kind)
            self.assertTrue(read_result.available, read_result.unavailable)

        report = validate_artifact_run(FIXTURE_DIR)
        self.assertEqual(report.status, "valid")
        self.assertEqual(report.summary["valid_artifact_count"], len(EXPECTED_KINDS))
        self.assertEqual(report.summary["error_count"], 0)
        join_diagnostics = {diagnostic["kind"]: diagnostic for diagnostic in report.to_dict()["join_diagnostics"]}
        self.assertTrue(all(diagnostic["severity"] == "info" for diagnostic in join_diagnostics.values()))
        self.assertEqual(join_diagnostics["enrichment_results"]["status"], "informational")
        self.assertIn("review_item_ids", join_diagnostics["enrichment_results"]["notes"][0])
        self.assertEqual(join_diagnostics["review_summary"]["status"], "informational")
        self.assertIn("review_item_ids", " ".join(join_diagnostics["review_summary"]["notes"]))
        self.assertIn("review_event_ids", " ".join(join_diagnostics["review_summary"]["notes"]))
        self.assertIn("recompute_marker_ids", " ".join(join_diagnostics["review_summary"]["notes"]))
        self.assertEqual(join_diagnostics["scoring_view"]["status"], "informational")
        self.assertIn("canonical_evidence", join_diagnostics["scoring_view"]["notes"][0])
        self.assert_json_schema_valid(VALID_REPORT_PATH, "artifact-validation-report.schema.json")
        self.assertEqual(json.loads(VALID_REPORT_PATH.read_text(encoding="utf-8")), report.to_dict())

    def test_v11_diagnostic_fixture_covers_required_panel_join_paths(self):
        repository = JsonArtifactRepository.from_output_dir(FIXTURE_DIR)
        enrichment = repository.read_json("enrichment_results").payload
        canonical = repository.read_json("canonical_evidence").payload
        scoring = repository.read_json("scoring_view").payload
        cache_index = repository.read_json("provider_cache_index").payload
        cache_records = repository.read_jsonl("provider_cache").records
        review_queue = repository.read_jsonl("review_queue").records
        review_events = repository.read_jsonl("review_events").records
        recompute_markers = repository.read_jsonl("recompute_markers").records
        trace_events = repository.read_jsonl("agent_trace").records
        summary = repository.read_json("review_summary").payload

        candidate_ids = {record["candidate_id"] for record in enrichment["records"]}
        self.assertEqual(candidate_ids, {record["candidate_id"] for record in canonical["records"]})
        self.assertIn("spiro-ometsad", candidate_ids)
        self.assertIn("spiro-frontier-review", candidate_ids)

        review_ids = {item["review_item_id"] for item in review_queue}
        enrichment_review_ids = {
            review_id
            for record in enrichment["records"]
            for review_id in record["review_item_ids"]
        }
        canonical_review_ids = {
            item["review_item_id"]
            for record in canonical["records"]
            for item in record["review_items"]
        }
        self.assertTrue(enrichment_review_ids)
        self.assertTrue(canonical_review_ids)
        self.assertTrue(enrichment_review_ids <= review_ids)
        self.assertTrue(canonical_review_ids <= review_ids)

        trace_ids = {event["event_id"] for event in trace_events}
        self.assertTrue({entry["trace_event_id"] for entry in cache_index["entries"]} <= trace_ids)
        self.assertTrue({item["trace_event_id"] for item in review_queue if item.get("trace_event_id")} <= trace_ids)

        cache_by_key = {record["cache_key"]: record["response"] for record in cache_records}
        cache_index_by_key = {entry["cache_key"]: entry for entry in cache_index["entries"]}
        trace_by_id = {event["event_id"]: event for event in trace_events}
        provider_refs = [
            provider_ref
            for record in enrichment["records"]
            for provider_ref in record["provider_refs"]
        ]
        self.assertTrue(provider_refs)
        for provider_ref in provider_refs:
            cache_entry = cache_index_by_key[provider_ref["cache_key"]]
            cache_response = cache_by_key[provider_ref["cache_key"]]
            trace_event = trace_by_id[provider_ref["trace_event_id"]]
            self.assertEqual(cache_entry["response_id"], provider_ref["response_id"])
            self.assertEqual(cache_entry["raw_hash"], provider_ref["raw_hash"])
            self.assertEqual(cache_response["response_id"], provider_ref["response_id"])
            self.assertEqual(trace_event["response_id"], provider_ref["response_id"])

        for entry in cache_index["entries"]:
            response = cache_by_key[entry["cache_key"]]
            self.assertEqual(response["response_id"], entry["response_id"])
            self.assertEqual(response["raw_hash"], entry["raw_hash"])
            self.assertEqual(response["provider"], entry["provider"])

        canonical_energy = {
            energy["energy_evidence_id"]: energy
            for record in canonical["records"]
            for energy in record["energy_evidence"]
        }
        scoring_ids = {fact["evidence_id"] for fact in scoring["energy_facts"]}
        self.assertTrue(scoring_ids <= set(canonical_energy))
        self.assertTrue(scoring_ids)
        self.assertTrue(all(canonical_energy[evidence_id]["eligible_for_scoring"] for evidence_id in scoring_ids))
        self.assertTrue(
            any(not energy["eligible_for_scoring"] for energy in canonical_energy.values()),
            "fixture must include panel data for blocked/non-scoring evidence",
        )

        event_ids = {event["event_id"] for event in review_events}
        marker_ids = {marker["marker_id"] for marker in recompute_markers}
        self.assertEqual(set(summary["review_item_ids"]), review_ids)
        self.assertEqual(set(summary["review_event_ids"]), event_ids)
        self.assertEqual(set(summary["recompute_marker_ids"]), marker_ids)
        self.assertEqual(summary["review_count"], len(review_queue))
        self.assertEqual(summary["event_count"], len(review_events))
        self.assertEqual(summary["resolved_count"], 1)
        self.assertEqual(summary["open_blocking_count"], 1)

    def test_v11_degraded_report_marks_optional_panels_local_unavailable(self):
        degraded = validate_artifact_run(FIXTURE_DIR, optional_artifacts=OPTIONAL_PANELS)
        self.assertEqual(degraded.status, "degraded")
        self.assertEqual(degraded.severity, "warning")
        self.assertEqual(degraded.summary["error_count"], 0)
        self.assertEqual(degraded.summary["run_unavailable_count"], 0)
        self.assertEqual(degraded.summary["optional_unavailable_count"], 2)
        self.assertEqual({artifact.kind for artifact in degraded.optional_artifacts}, set(OPTIONAL_PANELS))
        self.assertEqual({panel["panel_id"] for panel in degraded.panels}, {"conflict_panel", "performance_error_timeline"})
        self.assert_json_schema_valid(DEGRADED_REPORT_PATH, "artifact-validation-report.schema.json")
        self.assertEqual(json.loads(DEGRADED_REPORT_PATH.read_text(encoding="utf-8")), degraded.to_dict())

    def test_v11_fixture_renders_current_static_viewer_panels(self):
        self.assertIsNotNone(shutil.which("node"), "node is required for viewer behavior test")
        runner = r"""
const fs = require("fs");
const path = require("path");
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

const fixtureDir = process.argv[3];
const manifest = JSON.parse(fs.readFileSync(path.join(fixtureDir, "run-manifest.json"), "utf8"));
context.loadedManifest = manifest;
vm.runInContext("state.manifest = loadedManifest", context);
for (const artifact of manifest.artifacts) {
  const artifactText = fs.readFileSync(path.join(fixtureDir, artifact.path), "utf8");
  const parsed = context.parseArtifact(artifact.path, artifactText);
  context.loadedArtifactPath = artifact.path;
  context.loadedArtifactPayload = parsed;
  vm.runInContext("state.artifacts.set(loadedArtifactPath, loadedArtifactPayload)", context);
}
context.renderKnownArtifacts();

process.stdout.write(JSON.stringify({
  artifactCount: element("artifactCount").textContent,
  candidateCount: element("candidateCount").textContent,
  needsReviewCount: element("needsReviewCount").textContent,
  recommendationCount: element("recommendationCount").textContent,
  traceCount: element("traceCount").textContent,
  canonicalEvidenceCount: element("canonicalEvidenceCount").textContent,
  scoringFactCount: element("scoringFactCount").textContent,
  reviewQueueCount: element("reviewQueueCount").textContent,
  reviewClosureCount: element("reviewClosureCount").textContent,
  candidateFlow: element("candidateFlow").innerHTML,
  canonicalEvidence: element("canonicalEvidenceList").innerHTML,
  scoringView: element("scoringViewList").innerHTML,
  reviewClosure: element("reviewClosureList").innerHTML,
  timeline: element("timeline").innerHTML,
}));
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as file:
            file.write(runner)
            runner_path = Path(file.name)
        try:
            result = subprocess.run(
                ["node", str(runner_path), "frontend/artifact-viewer/viewer.js", str(FIXTURE_DIR)],
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            runner_path.unlink(missing_ok=True)

        rendered = json.loads(result.stdout)
        self.assertEqual(rendered["artifactCount"], str(len(EXPECTED_KINDS)))
        self.assertEqual(rendered["candidateCount"], "2")
        self.assertEqual(rendered["needsReviewCount"], "1")
        self.assertEqual(rendered["recommendationCount"], "1")
        self.assertEqual(rendered["traceCount"], "3 events")
        self.assertEqual(rendered["canonicalEvidenceCount"], "2 records")
        self.assertEqual(rendered["scoringFactCount"], "2 facts")
        self.assertEqual(rendered["reviewQueueCount"], "2 items")
        self.assertEqual(rendered["reviewClosureCount"], "1 events / 1 markers")
        self.assertIn("spiro-ometsad", rendered["candidateFlow"])
        self.assertIn("spiro-frontier-review", rendered["candidateFlow"])
        self.assertIn("&lt;b&gt;unsafe label&lt;/b&gt;", rendered["candidateFlow"])
        self.assertNotIn("<b>unsafe label</b>", rendered["candidateFlow"])
        self.assertIn("homo_ev -5.2 eV", rendered["canonicalEvidence"])
        self.assertIn("not eligible", rendered["canonicalEvidence"])
        self.assertIn("quality 0.92", rendered["scoringView"])
        self.assertIn("review summary", rendered["reviewClosure"])
        self.assertIn("provider_lookup", rendered["timeline"])

    def assert_json_schema_valid(self, path: Path, schema_name: str) -> None:
        schema = json.loads((Path("schemas") / schema_name).read_text(encoding="utf-8"))
        payload = json.loads(path.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(payload)


if __name__ == "__main__":
    unittest.main()
