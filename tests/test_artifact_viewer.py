import unittest
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


class ArtifactViewerTests(unittest.TestCase):
    def test_static_viewer_exposes_manifest_first_bundle_input(self):
        html = Path("frontend/artifact-viewer/index.html").read_text(encoding="utf-8")

        self.assertIn('id="bundleFiles"', html)
        self.assertIn('id="projectEvolutionFiles"', html)
        self.assertIn('id="projectEvolutionPanel"', html)
        self.assertIn('id="projectEvolutionList"', html)
        self.assertIn('aria-label="Viewer sections"', html)
        self.assertIn("#candidateWorkspace", html)
        self.assertIn("webkitdirectory", html)
        self.assertIn('<script src="run-data-store.js"></script>', html)
        self.assertIn('<script src="candidate-projection.js"></script>', html)
        self.assertNotIn('id="manifestFile"', html)
        self.assertNotIn('id="artifactFiles"', html)
        self.assertIn('id="artifactTable"', html)
        self.assertIn('id="candidateTable"', html)
        self.assertIn('id="candidateDetail"', html)
        self.assertIn('id="candidateSearch"', html)
        self.assertIn('id="candidateStatusFilter"', html)
        self.assertIn('id="candidateSort"', html)
        self.assertIn('id="candidateGroups"', html)
        self.assertIn('id="candidateDiagnostics"', html)
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

    def test_project_evolution_markdown_import_is_escaped_and_kept_as_context(self):
        self.assertIsNotNone(shutil.which("node"), "node is required for project evolution test")
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
  console, JSON, Map, Set, Object, Array, String, Number, Error, Promise,
  document: {getElementById: element},
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);

function file(name, text) {
  return {name, text: async () => text};
}

async function main() {
  const markdown = `---
version: V19
status: proposed <unsafe>
---
# Evolution <script>alert(1)</script>
## Exit Gate
Acceptance gate: user-selected context only <b>not facts</b>
`;
  const result = await context.loadProjectEvolutionFiles([
    file("v19.md", markdown),
    file("notes.txt", "# unsupported"),
  ]);
  context.renderProjectEvolution(result);
  process.stdout.write(JSON.stringify({
    count: element("projectEvolutionCount").textContent,
    html: element("projectEvolutionList").innerHTML,
    documentCount: result.documents.length,
    diagnosticCodes: result.diagnostics.map((item) => item.code),
  }));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
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
        observed = json.loads(result.stdout)
        self.assertEqual(observed["documentCount"], 1)
        self.assertIn("1 documents / 1 diagnostics", observed["count"])
        self.assertIn("human context only", observed["html"])
        self.assertIn("does not prove implementation completion", observed["html"])
        self.assertIn("declared status proposed &lt;unsafe&gt;", observed["html"])
        self.assertIn("Evolution &lt;script&gt;alert(1)&lt;/script&gt;", observed["html"])
        self.assertIn("Acceptance gate: user-selected context only &lt;b&gt;not facts&lt;/b&gt;", observed["html"])
        self.assertNotIn("<script>alert(1)</script>", observed["html"])
        self.assertNotIn("<b>not facts</b>", observed["html"])
        self.assertIn("project_evolution_unsupported_file", observed["diagnosticCodes"])

    def test_candidate_projection_maps_authoritative_screening_and_fails_closed(self):
        self.assertIsNotNone(shutil.which("node"), "node is required for projection test")
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const context = {console, JSON, Map, Set, Object, Array, String, Number, Error};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);

function artifact(payload) { return {payload, metadata: {}}; }
const canonical = {records: [
  {candidate_id: "continue-c", material: {material_id: "material-c"}, use_instance: {material_id: "material-c", use_instance_id: "use-c", role: "HTL"}, energy_evidence: [{energy_evidence_id: "e-c", material_id: "material-c", use_instance_id: "use-c"}], review_items: []},
  {candidate_id: "review-c", material: {material_id: "material-r"}, use_instance: {material_id: "material-r", use_instance_id: "use-r", role: "HTL"}, energy_evidence: [], review_items: [{review_item_id: "r-c", target_type: "use_instance", target_id: "use-r"}]},
  {candidate_id: "reject-c", material: {material_id: "material-x"}, use_instance: {material_id: "material-x", use_instance_id: "use-x", role: "HTL"}, energy_evidence: [], review_items: []},
  {candidate_id: "missing-c", material: {material_id: "material-m"}, use_instance: {material_id: "material-m", use_instance_id: "use-m"}, energy_evidence: [], review_items: []},
  {candidate_id: "unknown-c", material: {material_id: "material-u"}, use_instance: {material_id: "material-u", use_instance_id: "use-u"}, energy_evidence: [], review_items: []},
  {candidate_id: "invalid-c", material: {material_id: "material-i"}, use_instance: {material_id: "material-i", use_instance_id: "use-i"}, energy_evidence: [], review_items: []},
  {candidate_id: "duplicate-c", material: {material_id: "material-d"}, use_instance: {material_id: "material-d", use_instance_id: "use-d"}, energy_evidence: [], review_items: []},
  {candidate_id: "mapping-c", material: {material_id: "material-a"}, use_instance: {material_id: "material-b", use_instance_id: "use-map"}, energy_evidence: [], review_items: []},
  {candidate_id: "evidence-c", material: {material_id: "material-e"}, use_instance: {material_id: "material-e", use_instance_id: "use-e"}, energy_evidence: [], review_items: []},
  {candidate_id: "review-ref-c", material: {material_id: "material-rr"}, use_instance: {material_id: "material-rr", use_instance_id: "use-rr"}, energy_evidence: [], review_items: []},
  {candidate_id: "review-map-c", material: {material_id: "material-rm"}, use_instance: {material_id: "material-rm", use_instance_id: "use-rm"}, energy_evidence: [], review_items: [{review_item_id: "r-wrong", target_type: "candidate", target_id: "use-rm"}]},
  {candidate_id: "canonical-duplicate", material: {material_id: "material-one"}, use_instance: {material_id: "material-one", use_instance_id: "use-one"}, energy_evidence: [], review_items: []},
  {candidate_id: "canonical-duplicate", material: {material_id: "material-two"}, use_instance: {material_id: "material-two", use_instance_id: "use-two"}, energy_evidence: [], review_items: []},
]};
const componentNames = ["homo_alignment", "lumo_alignment", "band_gap", "solubility", "stability", "cost", "synthesis_complexity"];
function screeningRow(candidateId, status, options = {}) {
  return {
    candidate_id: candidateId,
    status,
    codes: options.codes || [],
    components: componentNames.map((name) => ({
      name, utility: 0.5, quality: 1, observed: false,
      evidence_ids: options.evidence?.[name] || [],
    })),
    blocking_review_ids: options.reviewIds || [],
    profile_version: "v12.htl_screening.v1",
    weights: {homo_alignment: 0.3, lumo_alignment: 0.2, band_gap: 0.1, solubility: 0.1, stability: 0.15, cost: 0.1, synthesis_complexity: 0.05},
    weighted_utility: 0.5,
    coverage: options.coverage ?? 0.5,
  };
}
const screening = {schema_version: "v19.screening_input_view.v1", profile_version: "v12.htl_screening.v1", candidates: [
  screeningRow("continue-c", "pass", {evidence: {homo_alignment: ["e-c"]}, coverage: 0.9}),
  screeningRow("review-c", "defer", {reviewIds: ["r-c"]}),
  screeningRow("reject-c", "reject"),
  screeningRow("unknown-c", "maybe"),
  {...screeningRow("invalid-c", "pass"), components: {not: "an array"}},
  screeningRow("duplicate-c", "pass"),
  screeningRow("duplicate-c", "reject"),
  screeningRow("mapping-c", "pass"),
  screeningRow("evidence-c", "pass", {evidence: {homo_alignment: ["not-there"]}}),
  screeningRow("review-ref-c", "defer", {reviewIds: ["missing-review"]}),
  screeningRow("review-map-c", "defer", {reviewIds: ["r-wrong"]}),
  screeningRow("canonical-duplicate", "pass"),
  screeningRow("screening-only", "pass"),
]};
const snapshot = {
  manifest: {run_id: "run-1", artifacts: [{kind: "canonical_evidence"}, {kind: "screening_input_view"}, {kind: "recommendations"}]},
  manifestMetadata: {runId: "run-1", schemaVersion: "manifest-v1"},
  availability: {canonical_evidence: {status: "available"}, screening_input_view: {status: "available"}, recommendations: {status: "available"}},
  artifacts: {
    canonical_evidence: artifact(canonical),
    screening_input_view: artifact(screening),
    recommendations: artifact({requests: [
      {candidate_id: "review-c", request_id: "request-review", acquisition_score: 99, rank: 1},
      {candidate_id: "reject-c", request_id: "request-reject", acquisition_score: 100, rank: 0},
    ]}),
  },
  diagnostics: [],
};
const projection = context.SpiroCandidateProjection.project(snapshot);
const unavailableProjection = context.SpiroCandidateProjection.project({
  manifest: {run_id: "run-unavailable", artifacts: [{kind: "canonical_evidence"}, {kind: "screening_input_view"}]},
  manifestMetadata: {runId: "run-unavailable"},
  availability: {canonical_evidence: {status: "available"}, screening_input_view: {status: "parse_error"}},
  artifacts: {canonical_evidence: artifact({records: [canonical.records[0]]})},
  diagnostics: [],
});
const invalidProjection = context.SpiroCandidateProjection.project({
  manifest: {run_id: "run-invalid", artifacts: [{kind: "canonical_evidence"}, {kind: "screening_input_view"}]},
  manifestMetadata: {runId: "run-invalid"},
  availability: {canonical_evidence: {status: "available"}, screening_input_view: {status: "available"}},
  artifacts: {canonical_evidence: artifact({records: [canonical.records[0]]}), screening_input_view: artifact({candidates: {bad: true}})},
  diagnostics: [],
});
snapshot.artifacts.screening_input_view.payload.candidates[0].status = "reject";
let mutationBlocked = false;
try { projection.groups.continue[0].candidateId = "mutated"; } catch (error) { mutationBlocked = true; }
const all = Object.values(projection.groups).flat();
const byId = Object.fromEntries(all.map((candidate) => [candidate.candidateId, candidate]));
process.stdout.write(JSON.stringify({
  groupIds: Object.fromEntries(Object.entries(projection.groups).map(([key, value]) => [key, value.map((candidate) => candidate.candidateId)])),
  diagnostics: projection.diagnostics.map((item) => item.code),
  reasons: Object.fromEntries(all.map((candidate) => [candidate.candidateId, candidate.diagnostic?.reason || null])),
  continueBackendStatus: byId["continue-c"].backendStatus,
  reviewBackendStatus: byId["review-c"].backendStatus,
  rejectBackendStatus: byId["reject-c"].backendStatus,
  reviewRecommendation: byId["review-c"].recommendation.requests[0],
  rejectRecommendation: byId["reject-c"].recommendation.requests[0],
  continueMaterial: byId["continue-c"].identity.materialId,
  evidenceCoverage: byId["continue-c"].evidenceCoverage,
  frozen: Object.isFrozen(projection) && Object.isFrozen(projection.groups.continue[0]),
  mutationBlocked,
  unavailableGroup: unavailableProjection.groups["insufficient-data"].map((candidate) => candidate.candidateId),
  unavailableReason: unavailableProjection.groups["insufficient-data"][0].diagnostic,
  unavailableCapability: unavailableProjection.capabilities.screening_input_view.status,
  invalidGroup: invalidProjection.groups["insufficient-data"].map((candidate) => candidate.candidateId),
  invalidCodes: invalidProjection.diagnostics.map((item) => item.code),
}));
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as file:
            file.write(runner)
            runner_path = Path(file.name)
        try:
            result = subprocess.run(
                ["node", str(runner_path), "frontend/artifact-viewer/candidate-projection.js"],
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            runner_path.unlink(missing_ok=True)

        projected = json.loads(result.stdout)
        self.assertEqual(projected["groupIds"]["continue"], ["continue-c"])
        self.assertEqual(projected["groupIds"]["review"], ["review-c"])
        self.assertEqual(projected["groupIds"]["reject"], ["reject-c"])
        self.assertCountEqual(
            projected["groupIds"]["insufficient-data"],
            ["missing-c", "unknown-c", "invalid-c", "duplicate-c", "mapping-c", "evidence-c", "review-ref-c", "review-map-c", "canonical-duplicate"],
        )
        self.assertEqual(projected["continueBackendStatus"], "pass")
        self.assertEqual(projected["reviewBackendStatus"], "defer")
        self.assertEqual(projected["rejectBackendStatus"], "reject")
        self.assertEqual(projected["continueMaterial"], "material-c")
        self.assertEqual(projected["evidenceCoverage"]["joined"], 1)
        self.assertEqual(projected["reviewRecommendation"]["acquisition_score"], 99)
        self.assertEqual(projected["rejectRecommendation"]["acquisition_score"], 100)
        self.assertIn("screening_only_identity_contradiction", projected["diagnostics"])
        self.assertIn("duplicate_screening_candidate_id", projected["diagnostics"])
        self.assertIn("screening_row_invalid", projected["diagnostics"])
        self.assertIn("duplicate_canonical_candidate_id", projected["diagnostics"])
        self.assertIn("canonical_mapping_conflict", projected["diagnostics"])
        self.assertIn("unjoinable_evidence_reference", projected["diagnostics"])
        self.assertIn("unjoinable_review_reference", projected["diagnostics"])
        self.assertTrue(projected["frozen"])
        self.assertEqual(projected["unavailableGroup"], ["continue-c"])
        self.assertEqual(projected["unavailableCapability"], "parse_error")
        self.assertIn("screening_row_missing", projected["unavailableReason"]["codes"])
        self.assertEqual(projected["invalidGroup"], ["continue-c"])
        self.assertIn("screening_unavailable_or_invalid", projected["invalidCodes"])

    def test_candidate_projection_query_is_deterministic_and_non_mutating(self):
        self.assertIsNotNone(shutil.which("node"), "node is required for projection test")
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const context = {console, JSON, Map, Set, Object, Array, String, Number, Error};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);
const candidates = [
  {candidateId: "beta", group: "review", backendStatus: "defer", identity: {materialId: "mat-b", role: "HTL"}, evidenceCoverage: {ratio: 0.5}},
  {candidateId: "Alpha", group: "continue", backendStatus: "pass", identity: {materialId: "mat-a", role: "ETL"}, evidenceCoverage: {ratio: 1}},
  {candidateId: "gamma", group: "reject", backendStatus: "reject", identity: {materialId: "mat-g", role: "HTL"}, evidenceCoverage: {ratio: 0}},
];
const projection = {groups: {continue: [candidates[1]], review: [candidates[0]], reject: [candidates[2]], "insufficient-data": []}};
const first = context.SpiroCandidateProjection.query(projection, {search: "htl", statuses: ["review", "reject"], sort: "candidate-desc"});
const second = context.SpiroCandidateProjection.query(projection, {search: "htl", statuses: ["review", "reject"], sort: "candidate-desc"});
const empty = context.SpiroCandidateProjection.query(projection, {search: "no-match", statuses: [], sort: "candidate-asc"});
process.stdout.write(JSON.stringify({
  first: first.map((candidate) => candidate.candidateId),
  second: second.map((candidate) => candidate.candidateId),
  empty: empty.length,
  original: projection.groups.review[0].candidateId,
  inputFrozen: Object.isFrozen(projection.groups.review[0]),
}));
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as file:
            file.write(runner)
            runner_path = Path(file.name)
        try:
            result = subprocess.run(
                ["node", str(runner_path), "frontend/artifact-viewer/candidate-projection.js"],
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            runner_path.unlink(missing_ok=True)
        queried = json.loads(result.stdout)
        self.assertEqual(queried["first"], ["gamma", "beta"])
        self.assertEqual(queried["second"], queried["first"])
        self.assertEqual(queried["empty"], 0)
        self.assertEqual(queried["original"], "beta")
        self.assertFalse(queried["inputFrozen"])

    def test_candidate_projection_checks_local_contract_typed_anchors_and_reference_cardinality(self):
        self.assertIsNotNone(shutil.which("node"), "node is required for projection test")
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const context = {console, JSON, Map, Set, Object, Array, String, Number, Error};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);

const componentNames = ["homo_alignment", "lumo_alignment", "band_gap", "solubility", "stability", "cost", "synthesis_complexity"];
const exactWeights = {homo_alignment: 0.3, lumo_alignment: 0.2, band_gap: 0.1, solubility: 0.1, stability: 0.15, cost: 0.1, synthesis_complexity: 0.05};
function row(overrides = {}) {
  const evidenceIds = overrides.evidenceIds || [];
  return {
    candidate_id: "candidate-c",
    status: "pass",
    codes: [],
    components: componentNames.map((name) => ({name, utility: 0.5, quality: 1, observed: false, evidence_ids: name === "homo_alignment" ? evidenceIds : []})),
    blocking_review_ids: [],
    profile_version: "v12.htl_screening.v1",
    weights: {...exactWeights},
    weighted_utility: 0.5,
    coverage: 0.5,
    ...overrides,
  };
}
function record(overrides = {}) {
  return {
    candidate_id: "candidate-c",
    material: {material_id: "material-c"},
    use_instance: {material_id: "material-c", use_instance_id: "use-c"},
    energy_evidence: [],
    review_items: [],
    ...overrides,
  };
}
function snapshot(canonicalRecord, screeningRow, options = {}) {
  const reviewQueue = options.reviewQueue;
  const artifacts = {
    canonical_evidence: {payload: {records: [canonicalRecord]}},
    screening_input_view: {payload: {
      schema_version: options.schemaVersion || "v19.screening_input_view.v1",
      profile_version: options.topProfileVersion || "v12.htl_screening.v1",
      candidates: [screeningRow],
      ...(options.payloadExtra || {}),
    }},
  };
  const declarations = [{kind: "canonical_evidence"}, {kind: "screening_input_view"}];
  const availability = {canonical_evidence: {status: "available"}, screening_input_view: {status: "available"}};
  if (reviewQueue) {
    artifacts.review_queue = {payload: reviewQueue};
    declarations.push({kind: "review_queue"});
    availability.review_queue = {status: "available"};
  }
  return {manifest: {run_id: "run-contract", artifacts: declarations}, manifestMetadata: {runId: "run-contract"}, artifacts, availability, diagnostics: []};
}
function result(canonicalRecord, screeningRow, options = {}) {
  const projection = context.SpiroCandidateProjection.project(snapshot(canonicalRecord, screeningRow, options));
  const groups = Object.fromEntries(Object.entries(projection.groups).map(([group, values]) => [group, values.map((candidate) => candidate.candidateId)]));
  const candidate = Object.values(projection.groups).flat().find((item) => item.candidateId === "candidate-c");
  return {groups, blockerCodes: candidate?.blockers.codes || [], codes: projection.diagnostics.map((item) => item.code), messages: projection.diagnostics.map((item) => item.message), diagnostics: projection.diagnostics};
}

const invalidCode = result(record(), row({codes: ["NOT_A_FROZEN_CODE"]}));
const whitespaceFrozenCode = result(record(), row({codes: [" HOMO_MISMATCH "]}));
const invalidProfile = result(record(), row({profile_version: "future-profile"}));
const extraWeight = result(record(), row({weights: {...exactWeights, invented: 0}}));
const changedWeight = result(record(), row({weights: {...exactWeights, homo_alignment: 0.31}}));
const unsupportedSchema = result(record(), row(), {schemaVersion: "v20.screening_input_view.v1"});
const unsupportedTopProfile = result(record(), row(), {topProfileVersion: "future-profile"});
const payloadExtraProperty = result(record(), row(), {payloadExtra: {invented: true}});
const rowExtraProperty = result(record(), row({invented: true}));
const componentExtra = row();
componentExtra.components[0] = {...componentExtra.components[0], invented: true};
const componentExtraProperty = result(record(), componentExtra);
const statusWhitespace = result(record(), row({status: " pass "}));
const componentNameWhitespaceRow = row();
componentNameWhitespaceRow.components[0] = {...componentNameWhitespaceRow.components[0], name: " homo_alignment "};
const componentNameWhitespace = result(record(), componentNameWhitespaceRow);

const typedMismatch = result(
  record({review_items: [{review_item_id: "review-c", target_type: "candidate", target_id: "use-c"}]}),
  row({status: "defer", blocking_review_ids: ["review-c"]})
);
const wrongMappedEnergyTarget = result(
  record({
    energy_evidence: [{energy_evidence_id: "energy-target", material_id: "wrong-material", use_instance_id: "use-c"}],
    review_items: [{review_item_id: "review-energy", target_type: "energy_evidence", target_id: "energy-target"}],
  }),
  row({status: "defer", blocking_review_ids: ["review-energy"]})
);
const queueCandidateWhitespace = result(
  record({review_items: [{review_item_id: "review-exact-candidate", target_type: "use_instance", target_id: "use-c"}]}),
  row({status: "defer", blocking_review_ids: ["review-exact-candidate"]}),
  {reviewQueue: [{review_item_id: "review-exact-candidate", candidate_id: " candidate-c ", target_type: "use_instance", target_id: "use-c"}]}
);
const queueTargetWhitespace = result(
  record({review_items: [{review_item_id: "review-exact-target", target_type: "use_instance", target_id: "use-c"}]}),
  row({status: "defer", blocking_review_ids: ["review-exact-target"]}),
  {reviewQueue: [{review_item_id: "review-exact-target", candidate_id: "candidate-c", target_type: "use_instance", target_id: " use-c "}]}
);
const queueWrongCandidateSameReview = result(
  record({review_items: [{review_item_id: "review-cross-candidate", target_type: "use_instance", target_id: "use-c"}]}),
  row({status: "defer", blocking_review_ids: ["review-cross-candidate"]}),
  {reviewQueue: [{review_item_id: "review-cross-candidate", candidate_id: "other-candidate", target_type: "use_instance", target_id: "use-c"}]}
);
const unreferencedCanonicalWrongCandidate = result(
  record({review_items: [{review_item_id: "review-owned-unreferenced", target_type: "use_instance", target_id: "use-c"}]}),
  row(),
  {reviewQueue: [{review_item_id: "review-owned-unreferenced", candidate_id: "other-candidate", target_type: "use_instance", target_id: "use-c"}]}
);

const evidenceA = {energy_evidence_id: "e-duplicate", material_id: "material-c", use_instance_id: "use-c", property_name: "homo_ev"};
const evidenceB = {...evidenceA, property_name: "lumo_ev"};
const duplicateEvidenceForward = result(record({energy_evidence: [evidenceA, evidenceB]}), row({evidenceIds: ["e-duplicate"]}));
const duplicateEvidenceReverse = result(record({energy_evidence: [evidenceB, evidenceA]}), row({evidenceIds: ["e-duplicate"]}));
const unreferencedEvidenceDuplicate = result(record({energy_evidence: [evidenceA, evidenceB]}), row());

const canonicalReview = {review_item_id: "review-duplicate", target_type: "use_instance", target_id: "use-c"};
const queueReviewA = {review_item_id: "review-duplicate", candidate_id: "candidate-c", target_type: "use_instance", target_id: "use-c", reason: "a"};
const queueReviewB = {...queueReviewA, reason: "b"};
const duplicateReviewForward = result(
  record({review_items: [canonicalReview]}),
  row({status: "defer", blocking_review_ids: ["review-duplicate"]}),
  {reviewQueue: [queueReviewA, queueReviewB]}
);
const duplicateReviewReverse = result(
  record({review_items: [canonicalReview]}),
  row({status: "defer", blocking_review_ids: ["review-duplicate"]}),
  {reviewQueue: [queueReviewB, queueReviewA]}
);
const unreferencedReviewDuplicate = result(
  record({review_items: [canonicalReview]}),
  row(),
  {reviewQueue: [queueReviewA, queueReviewB]}
);
const unrelatedQueueDuplicate = result(
  record(),
  row(),
  {reviewQueue: [
    {...queueReviewA, candidate_id: "other-candidate"},
    {...queueReviewB, candidate_id: "other-candidate"},
  ]}
);
const canonicalOnlyReviewDuplicate = result(
  record({review_items: [
    {review_item_id: "review-canonical-duplicate", target_type: "use_instance", target_id: "use-c", reason: "a"},
    {review_item_id: "review-canonical-duplicate", target_type: "use_instance", target_id: "use-c", reason: "b"},
  ]}),
  row()
);
const mixedQueueAmbiguousReviewReference = result(
  record({review_items: [{review_item_id: "review-mixed-ambiguous", target_type: "use_instance", target_id: "use-c"}]}),
  row(),
  {reviewQueue: [
    {review_item_id: "review-mixed-ambiguous", candidate_id: "candidate-c", target_type: "use_instance", target_id: "use-c", reason: "a"},
    {review_item_id: "review-mixed-ambiguous", candidate_id: " candidate-c ", target_type: "use_instance", target_id: "use-c", reason: "b"},
  ]}
);

process.stdout.write(JSON.stringify({
  invalidCode, whitespaceFrozenCode, invalidProfile, extraWeight, changedWeight, unsupportedSchema, unsupportedTopProfile,
  payloadExtraProperty, rowExtraProperty, componentExtraProperty, statusWhitespace, componentNameWhitespace,
  typedMismatch, wrongMappedEnergyTarget, queueCandidateWhitespace, queueTargetWhitespace, queueWrongCandidateSameReview, unreferencedCanonicalWrongCandidate,
  duplicateEvidenceForward, duplicateEvidenceReverse, unreferencedEvidenceDuplicate,
  duplicateReviewForward, duplicateReviewReverse, unreferencedReviewDuplicate, unrelatedQueueDuplicate, canonicalOnlyReviewDuplicate, mixedQueueAmbiguousReviewReference,
}));
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as file:
            file.write(runner)
            runner_path = Path(file.name)
        try:
            result = subprocess.run(
                ["node", str(runner_path), "frontend/artifact-viewer/candidate-projection.js"],
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            runner_path.unlink(missing_ok=True)
        observed = json.loads(result.stdout)
        for name in ["invalidCode", "invalidProfile", "extraWeight", "changedWeight"]:
            self.assertEqual(observed[name]["groups"]["insufficient-data"], ["candidate-c"], name)
            self.assertIn("screening_row_invalid", observed[name]["codes"], name)
            self.assertTrue(any("browser-local structural" in message.casefold() for message in observed[name]["messages"]), name)
        self.assertEqual(observed["whitespaceFrozenCode"]["groups"]["insufficient-data"], ["candidate-c"])
        self.assertEqual(observed["whitespaceFrozenCode"]["blockerCodes"], [" HOMO_MISMATCH "])
        for name in ["unsupportedSchema", "unsupportedTopProfile"]:
            self.assertEqual(observed[name]["groups"]["insufficient-data"], ["candidate-c"], name)
            self.assertIn("screening_contract_unsupported", observed[name]["codes"], name)
            self.assertTrue(any("browser-local structural" in message.casefold() for message in observed[name]["messages"]), name)
        self.assertEqual(observed["payloadExtraProperty"]["groups"]["insufficient-data"], ["candidate-c"])
        self.assertIn("screening_contract_unsupported", observed["payloadExtraProperty"]["codes"])
        for name in ["rowExtraProperty", "componentExtraProperty"]:
            self.assertEqual(observed[name]["groups"]["insufficient-data"], ["candidate-c"], name)
            self.assertIn("screening_row_invalid", observed[name]["codes"], name)
        for name in ["statusWhitespace", "componentNameWhitespace"]:
            self.assertEqual(observed[name]["groups"]["insufficient-data"], ["candidate-c"], name)
            self.assertIn("screening_row_invalid", observed[name]["codes"], name)
        self.assertEqual(observed["typedMismatch"]["groups"]["insufficient-data"], ["candidate-c"])
        self.assertIn("unjoinable_review_reference", observed["typedMismatch"]["codes"])
        self.assertEqual(observed["wrongMappedEnergyTarget"]["groups"]["insufficient-data"], ["candidate-c"])
        self.assertIn("unjoinable_review_reference", observed["wrongMappedEnergyTarget"]["codes"])
        for name in ["queueCandidateWhitespace", "queueTargetWhitespace"]:
            self.assertEqual(observed[name]["groups"]["insufficient-data"], ["candidate-c"], name)
            self.assertIn("unjoinable_review_reference", observed[name]["codes"], name)
        self.assertEqual(observed["queueWrongCandidateSameReview"]["groups"]["insufficient-data"], ["candidate-c"])
        self.assertIn("unjoinable_review_reference", observed["queueWrongCandidateSameReview"]["codes"])
        self.assertEqual(observed["unreferencedCanonicalWrongCandidate"]["groups"]["insufficient-data"], ["candidate-c"])
        self.assertIn("unjoinable_review_reference", observed["unreferencedCanonicalWrongCandidate"]["codes"])
        owned_conflict = next(
            item for item in observed["unreferencedCanonicalWrongCandidate"]["diagnostics"]
            if item["code"] == "unjoinable_review_reference"
        )
        self.assertEqual(owned_conflict["source"], "canonical_evidence, review_queue")
        self.assertNotIn("declared blocking", owned_conflict["message"])
        for name in ["duplicateEvidenceForward", "duplicateEvidenceReverse"]:
            self.assertEqual(observed[name]["groups"]["insufficient-data"], ["candidate-c"], name)
            self.assertIn("ambiguous_evidence_reference", observed[name]["codes"], name)
        self.assertEqual(observed["unreferencedEvidenceDuplicate"]["groups"]["insufficient-data"], ["candidate-c"])
        self.assertIn("duplicate_owned_evidence_id", observed["unreferencedEvidenceDuplicate"]["codes"])
        for name in ["duplicateReviewForward", "duplicateReviewReverse"]:
            self.assertEqual(observed[name]["groups"]["insufficient-data"], ["candidate-c"], name)
            self.assertIn("duplicate_owned_review_id", observed[name]["codes"], name)
            self.assertNotIn("ambiguous_review_reference", observed[name]["codes"], name)
        self.assertEqual(observed["unreferencedReviewDuplicate"]["groups"]["insufficient-data"], ["candidate-c"])
        self.assertIn("duplicate_owned_review_id", observed["unreferencedReviewDuplicate"]["codes"])
        self.assertEqual(observed["unrelatedQueueDuplicate"]["groups"]["continue"], ["candidate-c"])
        self.assertEqual(observed["canonicalOnlyReviewDuplicate"]["groups"]["insufficient-data"], ["candidate-c"])
        canonical_duplicate = next(
            item for item in observed["canonicalOnlyReviewDuplicate"]["diagnostics"]
            if item["code"] == "duplicate_owned_review_id"
        )
        self.assertEqual(canonical_duplicate["source"], "canonical_evidence")
        self.assertNotIn("declared blocking", canonical_duplicate["message"])
        self.assertNotIn("review_queue", canonical_duplicate["message"])
        canonical_only_diagnostics = observed["canonicalOnlyReviewDuplicate"]["diagnostics"]
        self.assertEqual(len(canonical_only_diagnostics), 1)
        mixed_ambiguous = observed["mixedQueueAmbiguousReviewReference"]
        self.assertEqual(mixed_ambiguous["groups"]["insufficient-data"], ["candidate-c"])
        self.assertIn("ambiguous_review_reference", mixed_ambiguous["codes"])
        mixed_ambiguous_diag = next(
            item for item in mixed_ambiguous["diagnostics"]
            if item["code"] == "ambiguous_review_reference"
        )
        self.assertEqual(mixed_ambiguous_diag["source"], "canonical_evidence, review_queue")
        self.assertNotIn("declared blocking", mixed_ambiguous_diag["message"])

    def test_candidate_projection_preserves_v13_review_representation_across_canonical_and_queue(self):
        self.assertIsNotNone(shutil.which("node"), "node is required for projection test")
        runner = r"""
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const context = {console, JSON, Map, Set, Object, Array, String, Number, Error};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);
const fixtureDir = process.argv[3];
const readJson = (name) => JSON.parse(fs.readFileSync(path.join(fixtureDir, name), "utf8"));
const readJsonl = (name) => fs.readFileSync(path.join(fixtureDir, name), "utf8")
  .split(/\r?\n/).filter((line) => line.trim()).map((line) => JSON.parse(line));
const manifest = readJson("run-manifest.json");
const artifacts = {
  canonical_evidence: {payload: readJson("canonical-evidence.json")},
  screening_input_view: {payload: readJson("screening-input-view.json")},
  review_queue: {payload: readJsonl("review-queue.jsonl")},
};
const availability = Object.fromEntries(Object.keys(artifacts).map((kind) => [kind, {status: "available"}]));
const projection = context.SpiroCandidateProjection.project({
  manifest,
  manifestMetadata: {runId: manifest.run_id, schemaVersion: manifest.schema_version},
  artifacts,
  availability,
  diagnostics: [],
});
process.stdout.write(JSON.stringify({
  groups: Object.fromEntries(Object.entries(projection.groups).map(([group, candidates]) => [group, candidates.map((candidate) => candidate.candidateId)])),
  deferJoinedReviews: projection.groups.review.find((candidate) => candidate.candidateId === "defer-1")?.blockers.joinedReviews || [],
}));
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as file:
            file.write(runner)
            runner_path = Path(file.name)
        try:
            result = subprocess.run(
                [
                    "node",
                    str(runner_path),
                    "frontend/artifact-viewer/candidate-projection.js",
                    "tests/fixtures/artifact_viewer/v13_algorithm_run",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            runner_path.unlink(missing_ok=True)
        observed = json.loads(result.stdout)
        self.assertEqual(observed["groups"]["continue"], ["pass-1"])
        self.assertEqual(observed["groups"]["review"], ["defer-1"])
        self.assertEqual(observed["groups"]["reject"], ["reject-1"])
        self.assertEqual(observed["groups"]["insufficient-data"], [])
        self.assertEqual(len(observed["deferJoinedReviews"]), 1)

    def test_candidate_detail_projection_uses_contract_backed_sources(self):
        self.assertIsNotNone(shutil.which("node"), "node is required for projection test")
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const context = {console, JSON, Map, Set, Object, Array, String, Number, Error};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);

const componentNames = ["homo_alignment", "lumo_alignment", "band_gap", "solubility", "stability", "cost", "synthesis_complexity"];
const weights = {homo_alignment: 0.3, lumo_alignment: 0.2, band_gap: 0.1, solubility: 0.1, stability: 0.15, cost: 0.1, synthesis_complexity: 0.05};
const canonical = {
  records: [{
    candidate_id: "candidate-c",
    material: {material_id: "material-c", material_kind: "small_molecule", supplier_status: "available"},
    use_instance: {material_id: "material-c", use_instance_id: "use-c", role: "HTL"},
    energy_evidence: [
      {energy_evidence_id: "e-eligible", material_id: "material-c", use_instance_id: "use-c", property_name: "homo_ev"},
      {energy_evidence_id: "e-not-admitted", material_id: "material-c", use_instance_id: "use-c", property_name: "lumo_ev"},
      {energy_evidence_id: "e-contradictory", material_id: "material-c", use_instance_id: "use-c", property_name: "band_gap_ev"},
    ],
    review_items: [{review_item_id: "review-c", target_type: "use_instance", target_id: "use-c", reason_code: "needs_review"}],
  }],
};
const screening = {
  schema_version: "v19.screening_input_view.v1",
  profile_version: "v12.htl_screening.v1",
  candidates: [{
    candidate_id: "candidate-c",
    status: "defer",
    codes: ["HOMO_NOT_YET_RESOLVED"],
    components: componentNames.map((name) => ({
      name,
      utility: name === "homo_alignment" ? 0.25 : 0.5,
      quality: 1,
      observed: name === "homo_alignment",
      evidence_ids: name === "homo_alignment" ? ["e-eligible", "e-not-admitted", "e-contradictory"] : [],
    })),
    blocking_review_ids: ["review-c"],
    profile_version: "v12.htl_screening.v1",
    weights,
    weighted_utility: 0.5,
    coverage: 0.5,
  }],
};
const scoringView = {energy_facts: [
  {
    evidence_id: "e-eligible",
    material_id: "material-c",
    use_instance_id: "use-c",
    property_name: "homo_ev",
    value_ev: -5.2,
    unit: "eV",
    method: "reported",
    reference_scale: "vacuum",
    quality: {eligible_for_scoring: true, trust_level: "T4_literature_curated", curation_status: "curated", quality_score: 0.85},
  },
  {
    evidence_id: "e-not-admitted",
    material_id: "material-c",
    use_instance_id: "use-c",
    property_name: "lumo_ev",
    value_ev: -2.1,
    unit: "eV",
    method: "reported",
    reference_scale: "vacuum",
    quality: {eligible_for_scoring: false, trust_level: "T1_raw", curation_status: "raw", quality_score: 0},
  },
  {
    evidence_id: "e-contradictory",
    material_id: "other-material",
    use_instance_id: "use-c",
    property_name: "band_gap_ev",
    value_ev: 3.1,
    unit: "eV",
    method: "reported",
    reference_scale: "vacuum",
    quality: {eligible_for_scoring: true, trust_level: "T4_literature_curated", curation_status: "curated", quality_score: 0.85},
  },
]};
const reviewQueue = [{review_item_id: "review-c", candidate_id: "candidate-c", target_type: "use_instance", target_id: "use-c", reason: "needs review"}];
const reviewEvents = [
  {event_id: "event-good", review_item_id: "review-c", target_type: "use_instance", target_id: "use-c", decision: "accept", resolution_status: "resolved", reason: "closed", recompute_marker_ids: ["marker-good"]},
  {event_id: "event-wrong-target", review_item_id: "review-c", target_type: "candidate", target_id: "other-candidate", decision: "accept", resolution_status: "resolved", reason: "wrong target"},
];
const recomputeMarkers = [{
  marker_id: "marker-good",
  review_event_id: "event-good",
  review_item_id: "review-c",
  candidate_id: "candidate-c",
  target_type: "use_instance",
  target_id: "use-c",
  affected_artifacts: ["canonical-evidence.json", "scoring-view.json"],
  reason: "review closed",
  status: "pending",
}];
const reviewSummary = {
  review_count: 1,
  event_count: 2,
  applied_event_count: 1,
  open_blocking_count: 0,
  review_item_ids: ["review-c"],
  review_event_ids: ["event-good"],
  recompute_marker_ids: ["marker-good"],
};
const acquisition = {
  request_id: "request-a",
  model_version: "model-v1",
  strategy: "qlognehvi",
  candidates: [{candidate_id: "candidate-c", model_score: 0.8, heuristic_score: 0.2, model_selected: true}],
};
const artifacts = {
  canonical_evidence: {payload: canonical},
  screening_input_view: {payload: screening},
  scoring_view: {payload: scoringView},
  review_queue: {payload: reviewQueue},
  review_events: {payload: reviewEvents},
  recompute_markers: {payload: recomputeMarkers},
  review_summary: {payload: reviewSummary},
  acquisition_breakdown: {payload: acquisition},
  literature_claims: {payload: [{claim_id: "claim-run-scope", doi: "10.000/run"}]},
  source_assets: {payload: [{asset_id: "asset-run-scope", doi: "10.000/run"}]},
};
const availability = Object.fromEntries(Object.keys(artifacts).map((kind) => [kind, {status: "available", path: `${kind}.json`}]));
const manifest = {run_id: "run-detail", artifacts: Object.keys(artifacts).map((kind) => ({kind, path: `${kind}.json`}))};
const projection = context.SpiroCandidateProjection.project({manifest, manifestMetadata: {runId: "run-detail"}, artifacts, availability, diagnostics: []});
const candidate = projection.groups.review[0];
process.stdout.write(JSON.stringify({
  candidateId: candidate.candidateId,
  group: candidate.group,
  componentArtifacts: candidate.detail.explanation.components.map((item) => item.artifactKind),
  scoringIds: candidate.detail.explanation.eligibleScoringEvidence.map((item) => item.evidenceId),
  scoringArtifacts: candidate.detail.explanation.eligibleScoringEvidence.map((item) => item.artifactKind),
  unavailableEvidenceIds: candidate.detail.explanation.unavailableEvidenceIds,
  explanationDiagnostics: candidate.detail.explanation.diagnostics.map((item) => item.code),
  appliedEventIds: candidate.detail.diagnostics.appliedReviewEvents.map((item) => item.eventId),
  auditEventIds: candidate.detail.diagnostics.auditReviewEvents.map((item) => item.eventId),
  marker: candidate.detail.diagnostics.recomputeMarkers[0],
  reviewSummary: candidate.detail.diagnostics.reviewSummary,
  acquisition: candidate.detail.explanation.acquisition,
  paperEvidence: candidate.detail.paperEvidence,
  frozen: Object.isFrozen(candidate.detail) && Object.isFrozen(candidate.detail.explanation.eligibleScoringEvidence[0]),
}));
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as file:
            file.write(runner)
            runner_path = Path(file.name)
        try:
            result = subprocess.run(
                ["node", str(runner_path), "frontend/artifact-viewer/candidate-projection.js"],
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            runner_path.unlink(missing_ok=True)
        observed = json.loads(result.stdout)
        self.assertEqual(observed["candidateId"], "candidate-c")
        self.assertEqual(observed["group"], "review")
        self.assertEqual(set(observed["componentArtifacts"]), {"screening_input_view"})
        self.assertEqual(observed["scoringIds"], ["e-eligible"])
        self.assertEqual(observed["scoringArtifacts"], ["scoring_view"])
        self.assertCountEqual(observed["unavailableEvidenceIds"], ["e-not-admitted", "e-contradictory"])
        self.assertIn("contradictory_scoring_evidence", observed["explanationDiagnostics"])
        self.assertEqual(observed["appliedEventIds"], ["event-good"])
        self.assertEqual(observed["auditEventIds"], ["event-wrong-target"])
        self.assertEqual(observed["marker"]["markerId"], "marker-good")
        self.assertEqual(observed["marker"]["artifactKind"], "recompute_markers")
        self.assertEqual(observed["reviewSummary"]["artifactKind"], "review_summary")
        self.assertEqual(observed["acquisition"]["artifactKind"], "acquisition_breakdown")
        self.assertEqual(observed["paperEvidence"]["status"], "unavailable")
        self.assertIn("run/DOI scope", observed["paperEvidence"]["message"])
        self.assertTrue(observed["frozen"])

    def test_candidate_workspace_renders_groups_controls_selection_and_empty_state(self):
        self.assertIsNotNone(shutil.which("node"), "node is required for workspace test")
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
      value: id === "candidateStatusFilter" ? "all" : id === "candidateSort" ? "candidate-asc" : "",
      style: {},
      dataset: {},
      addEventListener: () => {},
    });
  }
  return elements.get(id);
}
const context = {
  console, JSON, Map, Set, Object, Array, String, Number, Error,
  document: {getElementById: element},
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);
vm.runInContext(fs.readFileSync(process.argv[3], "utf8"), context);

function candidate(candidateId, group, backendStatus, materialId, ratio) {
  return {
    candidateId, group, backendStatus,
    identity: {materialId, useInstanceId: `use-${candidateId}`, role: "HTL", materialKind: "small_molecule", supplierStatus: "available"},
    blockers: {codes: group === "review" ? ["NEEDS_REVIEW"] : [], reviewIds: group === "review" ? ["review-<unsafe>", "review-two"] : [], missingReviewIds: []},
    evidenceCoverage: {declared: 2, joined: ratio * 2, ratio, evidenceIds: [], missingEvidenceIds: []},
    screening: {coverage: ratio, weightedUtility: 0.9, profileVersion: "profile-v1"},
    recommendation: {capability: "available", requests: [{request_id: `request-${candidateId}`, acquisition_score: 0.99}]},
    lineage: {capability: "available", events: [{eventId: `event-${candidateId}`, eventType: "screened", provider: "fixture", outcome: "ok"}]},
    diagnostic: group === "insufficient-data" ? {source: "screening_input_view", reason: "missing row", codes: ["screening_row_missing"]} : null,
  };
}
context.workspaceProjection = {
  capabilities: {scoring_view: {status: "available"}, review_queue: {status: "available"}, recommendations: {status: "available"}, agent_trace: {status: "available"}},
  diagnostics: [{code: "screening_only_identity_contradiction", candidateId: "outside", message: "not actionable", source: "screening_input_view"}],
  groups: {
    continue: [candidate("Alpha", "continue", "pass", "material-a", 1), candidate("unsafe-<script>alert(1)</script>", "continue", "pass", "material-safe", 1)],
    review: [candidate("beta", "review", "defer", "material-b", 0.5)],
    reject: [candidate("gamma", "reject", "reject", "material-g", 0)],
    "insufficient-data": [{...candidate("delta", "insufficient-data", null, "material-d", 0), blockers: {codes: [" HOMO_MISMATCH ", "<unsafe-code>"], reviewIds: [], missingReviewIds: []}}],
  },
};
vm.runInContext("state.candidateProjection = workspaceProjection; renderCandidateWorkspace();", context);
const initialGroups = element("candidateGroups").innerHTML;
const initialTable = element("candidateTable").innerHTML;
const initialDetail = element("candidateDetail").innerHTML;
context.selected = vm.runInContext("state.selectedCandidateId", context);

vm.runInContext(`
state.selectedCandidateId = "beta";
state.candidateControls = {search: "", statuses: ["review"], sort: "candidate-asc"};
renderCandidateWorkspace();
`, context);
const preservedSelection = vm.runInContext("state.selectedCandidateId", context);
const reviewDetail = element("candidateDetail").innerHTML;

vm.runInContext(`
state.selectedCandidateId = "delta";
state.candidateControls = {search: "", statuses: ["insufficient-data"], sort: "candidate-asc"};
renderCandidateWorkspace();
`, context);
const insufficientDetail = element("candidateDetail").innerHTML;

vm.runInContext(`
state.candidateControls = {search: "no-match", statuses: [], sort: "candidate-asc"};
renderCandidateWorkspace();
`, context);
const emptyTable = element("candidateTable").innerHTML;
const emptyDetail = element("candidateDetail").innerHTML;

process.stdout.write(JSON.stringify({
  initialGroups,
  initialTable,
  initialDetail,
  selected: context.selected,
  preservedSelection,
  reviewDetail,
  insufficientDetail,
  emptyTable,
  emptyDetail,
  diagnostics: element("candidateDiagnostics").innerHTML,
}));
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as file:
            file.write(runner)
            runner_path = Path(file.name)
        try:
            result = subprocess.run(
                [
                    "node",
                    str(runner_path),
                    "frontend/artifact-viewer/candidate-projection.js",
                    "frontend/artifact-viewer/viewer.js",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            runner_path.unlink(missing_ok=True)
        rendered = json.loads(result.stdout)
        for label in ["Continue", "Review", "Reject", "Insufficient data"]:
            self.assertIn(label, rendered["initialGroups"])
        self.assertIn("Alpha", rendered["initialTable"])
        self.assertIn("recommendation context", rendered["initialDetail"])
        self.assertIn("evidence coverage", rendered["initialDetail"])
        self.assertIn("lineage", rendered["initialDetail"])
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", rendered["initialTable"])
        self.assertNotIn("<script>alert(1)</script>", rendered["initialTable"])
        self.assertEqual(rendered["selected"], "Alpha")
        self.assertEqual(rendered["preservedSelection"], "beta")
        self.assertIn("blocker codes 1", rendered["reviewDetail"])
        self.assertIn("blocking reviews 2", rendered["reviewDetail"])
        self.assertIn("review-&lt;unsafe&gt;", rendered["reviewDetail"])
        self.assertNotIn("review-<unsafe>", rendered["reviewDetail"])
        self.assertIn("> HOMO_MISMATCH </span>", rendered["insufficientDetail"])
        self.assertNotIn(">HOMO_MISMATCH</span>", rendered["insufficientDetail"])
        self.assertIn("&lt;unsafe-code&gt;", rendered["insufficientDetail"])
        self.assertIn("No candidates match", rendered["emptyTable"])
        self.assertIn("Adjust search or status filters", rendered["emptyDetail"])
        self.assertIn("screening_only_identity_contradiction", rendered["diagnostics"])

    def test_candidate_detail_tabs_render_roles_and_keyboard_activation(self):
        self.assertIsNotNone(shutil.which("node"), "node is required for workspace tab test")
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
      value: id === "candidateStatusFilter" ? "all" : id === "candidateSort" ? "candidate-asc" : "",
      style: {},
      dataset: {},
      focused: false,
      handlers: {},
      addEventListener(type, handler) {
        if (!this.handlers[type]) this.handlers[type] = [];
        this.handlers[type].push(handler);
      },
      focus() {
        this.focused = true;
      },
    });
  }
  return elements.get(id);
}
const context = {
  console, JSON, Map, Set, Object, Array, String, Number, Error,
  document: {getElementById: element},
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);
vm.runInContext(fs.readFileSync(process.argv[3], "utf8"), context);

context.workspaceProjection = {
  capabilities: {},
  diagnostics: [],
  groups: {
    continue: [{
      candidateId: "Alpha",
      group: "continue",
      backendStatus: "pass",
      identity: {materialId: "material-a", useInstanceId: "use-a", role: "HTL", materialKind: "small_molecule", supplierStatus: "available"},
      blockers: {codes: [], reviewIds: [], joinedReviews: [], missingReviewIds: []},
      evidenceCoverage: {declared: 1, joined: 1, ratio: 1, evidenceIds: ["e-a"], missingEvidenceIds: []},
      screening: {coverage: 1, weightedUtility: 0.9, profileVersion: "profile-v1"},
      recommendation: {capability: "not-declared", requests: []},
      lineage: {capability: "not-declared", events: []},
      diagnostic: null,
      detail: {
        explanation: {
          components: [{artifactKind: "screening_input_view", name: "homo_alignment", utility: 0.9, quality: 1, observed: true, evidenceIds: ["e-a"]}],
          eligibleScoringEvidence: [{artifactKind: "scoring_view", evidenceId: "e-a", propertyName: "homo_ev", valueEv: -5.2, unit: "eV", quality: {trust_level: "T4_literature_curated"}}],
          unavailableEvidenceIds: [],
          diagnostics: [],
          acquisition: {artifactKind: "acquisition_breakdown", modelScore: 0.8, heuristicScore: 0.2, strategy: "qlognehvi", requestId: "request-a"},
        },
        diagnostics: {
          blockingReviews: [{artifactKind: "review_queue", reviewItemId: "review-a", targetType: "use_instance", targetId: "use-a", resolutionStatus: "open"}],
          appliedReviewEvents: [{artifactKind: "review_events", eventId: "event-a", reviewItemId: "review-a", targetType: "use_instance", targetId: "use-a", decision: "accept", resolutionStatus: "resolved"}],
          auditReviewEvents: [],
          recomputeMarkers: [{artifactKind: "recompute_markers", markerId: "marker-a", reviewEventId: "event-a", reviewItemId: "review-a", targetType: "use_instance", targetId: "use-a", status: "pending", affectedArtifacts: ["scoring-view.json"]}],
          reviewSummary: {artifactKind: "review_summary", reviewCount: 1, eventCount: 1, appliedEventCount: 1, openBlockingCount: 0},
          artifactStatuses: [{kind: "scoring_view", status: "available", path: "scoring-view.json"}],
          contradictions: [],
        },
        paperEvidence: {status: "unavailable", message: "No explicit backend candidate-to-paper join; literature is available only at run/DOI scope.", runArtifacts: [{kind: "literature_claims", status: "available"}], records: []},
      },
    }],
    review: [],
    reject: [],
    "insufficient-data": [],
  },
};
vm.runInContext("state.candidateProjection = workspaceProjection; renderCandidateWorkspace();", context);
const initial = element("candidateDetail").innerHTML;
const keydown = element("candidateDetail").handlers.keydown[0];
const click = element("candidateDetail").handlers.click[0];
function tabTarget(tab) {
  return {closest: () => ({dataset: {candidateTab: tab}})};
}
let prevented = false;
keydown({key: "ArrowRight", target: tabTarget("overview"), preventDefault: () => { prevented = true; }});
const afterArrowTab = vm.runInContext("state.selectedCandidateTab", context);
const afterArrowHtml = element("candidateDetail").innerHTML;
const explanationFocused = element("candidate-tab-explanation").focused;
keydown({key: "End", target: tabTarget("explanation"), preventDefault: () => {}});
const afterEndTab = vm.runInContext("state.selectedCandidateTab", context);
const paperHtml = element("candidateDetail").innerHTML;
click({target: tabTarget("diagnostics")});
const afterClickTab = vm.runInContext("state.selectedCandidateTab", context);
const diagnosticsHtml = element("candidateDetail").innerHTML;
process.stdout.write(JSON.stringify({
  initial,
  prevented,
  afterArrowTab,
  afterArrowHtml,
  explanationFocused,
  afterEndTab,
  paperHtml,
  afterClickTab,
  diagnosticsHtml,
}));
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as file:
            file.write(runner)
            runner_path = Path(file.name)
        try:
            result = subprocess.run(
                [
                    "node",
                    str(runner_path),
                    "frontend/artifact-viewer/candidate-projection.js",
                    "frontend/artifact-viewer/viewer.js",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            runner_path.unlink(missing_ok=True)
        rendered = json.loads(result.stdout)
        self.assertIn('role="tablist"', rendered["initial"])
        self.assertIn('role="tab"', rendered["initial"])
        self.assertIn('aria-selected="true"', rendered["initial"])
        self.assertIn('role="tabpanel"', rendered["initial"])
        self.assertTrue(rendered["prevented"])
        self.assertEqual(rendered["afterArrowTab"], "explanation")
        self.assertTrue(rendered["explanationFocused"])
        self.assertIn("ScoringView eligible evidence", rendered["afterArrowHtml"])
        self.assertEqual(rendered["afterEndTab"], "paper")
        self.assertIn("No explicit backend candidate-to-paper join", rendered["paperHtml"])
        self.assertEqual(rendered["afterClickTab"], "diagnostics")
        self.assertIn("Observed immutable recompute markers", rendered["diagnosticsHtml"])

    def test_run_data_store_commits_exact_manifest_bundle_atomically(self):
        self.assertIsNotNone(shutil.which("node"), "node is required for viewer behavior test")
        store_script = Path("frontend/artifact-viewer/run-data-store.js")
        self.assertTrue(
            store_script.exists(),
            "RelativePathBundleAdapter and RunDataStore script is required",
        )
        runner = r"""
const fs = require("fs");
const vm = require("vm");

const context = {console, JSON, Map, Set, Object, Array, String, Number, Error, Promise};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);

const {RelativePathBundleAdapter, RunDataStore} = context.SpiroRunData;

function file(relativePath, payload) {
  return {
    name: relativePath.split("/").pop(),
    webkitRelativePath: relativePath,
    text: async () => typeof payload === "string" ? payload : JSON.stringify(payload),
  };
}

function nameOnlyFile(name, payload) {
  return {
    name,
    text: async () => typeof payload === "string" ? payload : JSON.stringify(payload),
  };
}

function explicitPathFile(relativePath, payload) {
  return {
    name: relativePath.split("/").pop(),
    relativePath,
    text: async () => typeof payload === "string" ? payload : JSON.stringify(payload),
  };
}

function manifest(runId, artifacts) {
  return {
    schema_version: "v6.run_manifest.v1",
    run_id: runId,
    artifacts: artifacts.map((artifact) => ({
      format: "json",
      run_id: runId,
      ...artifact,
    })),
  };
}

function codes(result) {
  return result.diagnostics.map((diagnostic) => diagnostic.code);
}

async function main() {
  const runId = "run-good";
  const goodManifest = manifest(runId, [
    {kind: "canonical_evidence", path: "data/canonical.json"},
    {kind: "screening_input_view", path: "derived/screening.json"},
    {kind: "model_evaluation", path: "diagnostics/model.json"},
  ]);
  const canonical = {
    schema_version: "v9.canonical_evidence.v1",
    records: [{candidate_id: "candidate-1"}],
  };
  const screening = {
    schema_version: "v19.screening_input_view.v1",
    candidates: [{candidate_id: "candidate-1", status: "pass"}],
  };
  const goodFiles = [
    file("chosen-run/run-manifest.json", goodManifest),
    file("chosen-run/data/canonical.json", canonical),
    file("chosen-run/derived/screening.json", screening),
    file("chosen-run/diagnostics/model.json", "{bad json"),
  ];

  const adapter = new RelativePathBundleAdapter();
  const indexed = await adapter.index(goodFiles);
  const store = new RunDataStore(adapter);
  const committed = await store.replace(goodFiles);
  const snapshot = store.snapshot();
  const beforeCandidateId = snapshot.artifacts.canonical_evidence.payload.records[0].candidate_id;
  try {
    snapshot.artifacts.canonical_evidence.payload.records[0].candidate_id = "mutated";
  } catch (error) {
    // Frozen snapshots may throw in strict runtimes; either behavior is acceptable.
  }

  const basenameOnly = await new RunDataStore().replace([
    file("chosen-run/run-manifest.json", goodManifest),
    file("chosen-run/canonical.json", canonical),
    file("chosen-run/derived/screening.json", screening),
  ]);
  const duplicateKind = await new RunDataStore().replace([
    file("run-manifest.json", manifest("run-duplicate-kind", [
      {kind: "canonical_evidence", path: "canonical-a.json"},
      {kind: "canonical_evidence", path: "canonical-b.json"},
    ])),
  ]);
  const duplicateManifestPath = await new RunDataStore().replace([
    file("run-manifest.json", manifest("run-duplicate-path", [
      {kind: "canonical_evidence", path: "same.json"},
      {kind: "screening_input_view", path: "same.json"},
    ])),
  ]);
  const duplicateInputPath = await new RunDataStore().replace([
    file("run-manifest.json", manifest("run-input-path", [])),
    file("run-manifest.json", manifest("run-input-path", [])),
  ]);
  const unsafePath = await new RunDataStore().replace([
    file("run-manifest.json", manifest("run-unsafe", [
      {kind: "canonical_evidence", path: "../canonical.json"},
    ])),
  ]);
  const mixedManifest = manifest("run-mixed", [
    {kind: "canonical_evidence", path: "canonical.json", run_id: "other-run"},
  ]);
  const mixedRun = await store.replace([
    file("run-manifest.json", mixedManifest),
    file("canonical.json", canonical),
  ]);
  const afterFailedReplacement = store.snapshot();
  const duplicateCandidates = await new RunDataStore().replace([
    file("run-manifest.json", manifest("run-candidates", [
      {kind: "canonical_evidence", path: "canonical.json"},
    ])),
    file("canonical.json", {records: [{candidate_id: "same"}, {candidate_id: "same"}]}),
  ]);
  const nullCanonical = await new RunDataStore().replace([
    file("run-manifest.json", manifest("run-null-canonical", [
      {kind: "canonical_evidence", path: "canonical.json"},
    ])),
    file("canonical.json", "null"),
  ]);
  const missingCandidateId = await new RunDataStore().replace([
    file("run-manifest.json", manifest("run-missing-candidate", [
      {kind: "canonical_evidence", path: "canonical.json"},
    ])),
    file("canonical.json", {records: [{candidate_id: " "}]}),
  ]);
  const exactIdentityStore = new RunDataStore();
  const exactRawRunId = " run-exact ";
  const exactIdentityCommit = await exactIdentityStore.replace([
    file("run-manifest.json", manifest(exactRawRunId, [
      {kind: "canonical_evidence", path: "canonical.json"},
    ])),
    file("canonical.json", canonical),
  ]);
  const whitespaceMismatch = await exactIdentityStore.replace([
    file("run-manifest.json", manifest(" run-mismatch ", [
      {kind: "canonical_evidence", path: "canonical.json", run_id: "run-mismatch"},
    ])),
    file("canonical.json", canonical),
  ]);
  const reservedFiles = [
    file("run-manifest.json", manifest("run-reserved", [
      {kind: "canonical_evidence", path: "canonical.json"},
      {kind: "__proto__", path: "__proto__"},
    ])),
    file("canonical.json", canonical),
    file("__proto__", {nested: {marker: "reserved"}}),
  ];
  const reservedIndexed = await new RelativePathBundleAdapter().index(reservedFiles);
  const reservedCommit = await new RunDataStore().replace(reservedFiles);
  const reservedSnapshot = reservedCommit.snapshot;
  const formatAuthority = await new RunDataStore().replace([
    file("run-manifest.json", manifest("run-format-authority", [
      {kind: "canonical_evidence", path: "canonical.jsonl", format: "json"},
    ])),
    file("canonical.jsonl", canonical),
  ]);
  const unsupportedCanonicalFormat = await new RunDataStore().replace([
    file("run-manifest.json", manifest("run-format-unsupported", [
      {kind: "canonical_evidence", path: "canonical.json", format: "yaml"},
    ])),
    file("canonical.json", canonical),
  ]);
  const missingOptionalFormat = await new RunDataStore().replace([
    file("run-manifest.json", manifest("run-format-optional", [
      {kind: "canonical_evidence", path: "canonical.json"},
      {kind: "model_evaluation", path: "model.json", format: null},
    ])),
    file("canonical.json", canonical),
    file("model.json", {activation_status: "disabled"}),
  ]);
  const jsonlPayloadConflict = await new RunDataStore().replace([
    file("run-manifest.json", manifest("run-jsonl-conflict", [
      {kind: "canonical_evidence", path: "canonical.json"},
      {kind: "review_events", path: "review-events.jsonl", format: "jsonl"},
    ])),
    file("canonical.json", canonical),
    file("review-events.jsonl", '{"event_id":"event-1","run_id":"other-run"}\n{"event_id":"event-2"}\n'),
  ]);
  const jsonlPayloadWithoutRunId = await new RunDataStore().replace([
    file("run-manifest.json", manifest("run-jsonl-without-id", [
      {kind: "canonical_evidence", path: "canonical.json"},
      {kind: "review_events", path: "review-events.jsonl", format: "jsonl"},
    ])),
    file("canonical.json", canonical),
    file("review-events.jsonl", '{"event_id":"event-without-run-id"}\n'),
  ]);
  const jsonlConflictDiagnostic = jsonlPayloadConflict.diagnostics.find(
    (item) => item.code === "artifact_run_id_conflict" && item.kind === "review_events"
  );
  const nameOnlyBundle = await new RunDataStore().replace([
    nameOnlyFile("run-manifest.json", manifest("run-name-only", [
      {kind: "canonical_evidence", path: "canonical.json"},
    ])),
    nameOnlyFile("canonical.json", canonical),
  ]);
  const explicitPathBundle = await new RunDataStore().replace([
    explicitPathFile("explicit/run-manifest.json", manifest("run-explicit-path", [
      {kind: "canonical_evidence", path: "canonical.json"},
    ])),
    explicitPathFile("explicit/canonical.json", canonical),
  ]);
  const whitespaceKindBundle = await new RunDataStore().replace([
    file("run-manifest.json", manifest("run-kind-whitespace", [
      {kind: " canonical_evidence ", path: "canonical.json"},
    ])),
    file("canonical.json", canonical),
  ]);
  const whitespaceKindSnapshot = whitespaceKindBundle.snapshot;
  const viewerArtifact = (whitespaceKindSnapshot.manifest?.artifacts || [])
    .find((artifact) => artifact.kind === "canonical_evidence");

  function reachableValuesAreFrozen(value, seen = new Set()) {
    if (!value || typeof value !== "object" || seen.has(value)) return true;
    seen.add(value);
    return Object.isFrozen(value) && Object.values(value)
      .every((item) => reachableValuesAreFrozen(item, seen));
  }

  process.stdout.write(JSON.stringify({
    indexedPaths: indexed.paths,
    committed: committed.ok,
    runId: snapshot.manifest.run_id,
    manifestPath: snapshot.manifestMetadata.path,
    manifestBasePath: snapshot.manifestMetadata.basePath,
    canonicalPath: snapshot.artifacts.canonical_evidence.path,
    canonicalResolvedPath: snapshot.artifacts.canonical_evidence.resolvedPath,
    canonicalStatus: snapshot.availability.canonical_evidence.status,
    screeningStatus: snapshot.availability.screening_input_view.status,
    optionalParseStatus: snapshot.availability.model_evaluation.status,
    committedCodes: codes(committed),
    frozen: [
      snapshot,
      snapshot.manifest,
      snapshot.manifestMetadata,
      snapshot.artifacts,
      snapshot.artifacts.canonical_evidence,
      snapshot.artifacts.canonical_evidence.payload,
      snapshot.availability,
      snapshot.diagnostics,
    ].every(Object.isFrozen),
    mutationBlocked: snapshot.artifacts.canonical_evidence.payload.records[0].candidate_id === beforeCandidateId,
    basenameOnly: {ok: basenameOnly.ok, codes: codes(basenameOnly)},
    duplicateKind: codes(duplicateKind),
    duplicateManifestPath: codes(duplicateManifestPath),
    duplicateInputPath: codes(duplicateInputPath),
    unsafePath: codes(unsafePath),
    mixedRun: {
      ok: mixedRun.ok,
      codes: codes(mixedRun),
      retainedRunId: mixedRun.retainedRunId,
      sameSnapshot: afterFailedReplacement === snapshot,
      committedRunId: afterFailedReplacement.manifest.run_id,
    },
    duplicateCandidates: codes(duplicateCandidates),
    nullCanonical: codes(nullCanonical),
    missingCandidateId: codes(missingCandidateId),
    exactIdentity: {
      committed: exactIdentityCommit.ok,
      manifestRunId: exactIdentityCommit.snapshot.manifest.run_id,
      metadataRunId: exactIdentityCommit.snapshot.manifestMetadata.runId,
      mismatchOk: whitespaceMismatch.ok,
      mismatchCodes: codes(whitespaceMismatch),
      retainedRunId: whitespaceMismatch.retainedRunId,
      retainedManifestRunId: exactIdentityStore.snapshot().manifest.run_id,
      retainedMetadataRunId: exactIdentityStore.snapshot().manifestMetadata.runId,
    },
    reservedKeys: {
      committed: reservedCommit.ok,
      indexedOwnEntry: Object.prototype.hasOwnProperty.call(reservedIndexed.entries, "__proto__"),
      artifactOwnEntry: Object.prototype.hasOwnProperty.call(reservedSnapshot.artifacts, "__proto__"),
      availabilityOwnEntry: Object.prototype.hasOwnProperty.call(reservedSnapshot.availability, "__proto__"),
      artifactMarker: reservedSnapshot.artifacts.__proto__?.payload?.nested?.marker,
      availabilityStatus: reservedSnapshot.availability.__proto__?.status,
      entriesPrototypeIsNull: Object.getPrototypeOf(reservedIndexed.entries) === null,
      artifactsPrototypeIsNull: Object.getPrototypeOf(reservedSnapshot.artifacts) === null,
      availabilityPrototypeIsNull: Object.getPrototypeOf(reservedSnapshot.availability) === null,
      entriesFrozen: reachableValuesAreFrozen(reservedIndexed.entries),
      artifactsFrozen: reachableValuesAreFrozen(reservedSnapshot.artifacts),
      availabilityFrozen: reachableValuesAreFrozen(reservedSnapshot.availability),
    },
    manifestFormats: {
      authoritativeCommit: formatAuthority.ok,
      authoritativeCandidateId: formatAuthority.snapshot.artifacts.canonical_evidence?.payload?.records?.[0]?.candidate_id,
      unsupportedCanonicalOk: unsupportedCanonicalFormat.ok,
      unsupportedCanonicalCodes: codes(unsupportedCanonicalFormat),
      missingOptionalOk: missingOptionalFormat.ok,
      missingOptionalStatus: missingOptionalFormat.snapshot.availability.model_evaluation?.status,
      missingOptionalCodes: codes(missingOptionalFormat),
    },
    jsonlPayloadIdentity: {
      conflictOk: jsonlPayloadConflict.ok,
      conflictCodes: codes(jsonlPayloadConflict),
      conflictRecordIndex: jsonlConflictDiagnostic?.recordIndex,
      conflictActualRunId: jsonlConflictDiagnostic?.actualRunId,
      missingRunIdOk: jsonlPayloadWithoutRunId.ok,
    },
    explicitInputPaths: {
      nameOnlyOk: nameOnlyBundle.ok,
      nameOnlyCodes: codes(nameOnlyBundle),
      explicitRelativePathOk: explicitPathBundle.ok,
      webkitRelativePathOk: committed.ok,
    },
    whitespaceKind: {
      ok: whitespaceKindBundle.ok,
      codes: codes(whitespaceKindBundle),
      committedManifestKind: whitespaceKindSnapshot.manifest?.artifacts?.[0]?.kind ?? null,
      normalizedArtifactOwn: Object.prototype.hasOwnProperty.call(
        whitespaceKindSnapshot.artifacts,
        "canonical_evidence"
      ),
      viewerResolvable: Boolean(
        viewerArtifact?.path && whitespaceKindSnapshot.artifacts.canonical_evidence
      ),
    },
  }));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as file:
            file.write(runner)
            runner_path = Path(file.name)
        try:
            result = subprocess.run(
                ["node", str(runner_path), str(store_script)],
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            runner_path.unlink(missing_ok=True)

        observed = json.loads(result.stdout)
        self.assertEqual(
            observed["indexedPaths"],
            [
                "chosen-run/data/canonical.json",
                "chosen-run/derived/screening.json",
                "chosen-run/diagnostics/model.json",
                "chosen-run/run-manifest.json",
            ],
        )
        self.assertTrue(observed["committed"])
        self.assertEqual(observed["runId"], "run-good")
        self.assertEqual(observed["manifestPath"], "chosen-run/run-manifest.json")
        self.assertEqual(observed["manifestBasePath"], "chosen-run")
        self.assertEqual(observed["canonicalPath"], "data/canonical.json")
        self.assertEqual(observed["canonicalResolvedPath"], "chosen-run/data/canonical.json")
        self.assertEqual(observed["canonicalStatus"], "available")
        self.assertEqual(observed["screeningStatus"], "available")
        self.assertEqual(observed["optionalParseStatus"], "parse_error")
        self.assertIn("artifact_parse_error", observed["committedCodes"])
        self.assertTrue(observed["frozen"])
        self.assertTrue(observed["mutationBlocked"])
        self.assertFalse(observed["basenameOnly"]["ok"])
        self.assertIn("artifact_missing", observed["basenameOnly"]["codes"])
        self.assertIn("duplicate_artifact_kind", observed["duplicateKind"])
        self.assertIn("duplicate_artifact_path", observed["duplicateManifestPath"])
        self.assertIn("duplicate_relative_path", observed["duplicateInputPath"])
        self.assertIn("unsafe_artifact_path", observed["unsafePath"])
        self.assertFalse(observed["mixedRun"]["ok"])
        self.assertIn("artifact_run_id_conflict", observed["mixedRun"]["codes"])
        self.assertEqual(observed["mixedRun"]["retainedRunId"], "run-good")
        self.assertTrue(observed["mixedRun"]["sameSnapshot"])
        self.assertEqual(observed["mixedRun"]["committedRunId"], "run-good")
        self.assertIn("duplicate_candidate_id", observed["duplicateCandidates"])
        self.assertIn("canonical_evidence_invalid", observed["nullCanonical"])
        self.assertIn("candidate_id_missing", observed["missingCandidateId"])
        exact_identity = observed["exactIdentity"]
        self.assertTrue(exact_identity["committed"])
        self.assertEqual(exact_identity["manifestRunId"], " run-exact ")
        self.assertEqual(exact_identity["metadataRunId"], " run-exact ")
        self.assertFalse(exact_identity["mismatchOk"])
        self.assertIn("artifact_run_id_conflict", exact_identity["mismatchCodes"])
        self.assertEqual(exact_identity["retainedRunId"], " run-exact ")
        self.assertEqual(exact_identity["retainedManifestRunId"], " run-exact ")
        self.assertEqual(exact_identity["retainedMetadataRunId"], " run-exact ")
        reserved_keys = observed["reservedKeys"]
        self.assertTrue(reserved_keys["committed"])
        self.assertTrue(reserved_keys["indexedOwnEntry"])
        self.assertTrue(reserved_keys["artifactOwnEntry"])
        self.assertTrue(reserved_keys["availabilityOwnEntry"])
        self.assertEqual(reserved_keys["artifactMarker"], "reserved")
        self.assertEqual(reserved_keys["availabilityStatus"], "available")
        self.assertTrue(reserved_keys["entriesPrototypeIsNull"])
        self.assertTrue(reserved_keys["artifactsPrototypeIsNull"])
        self.assertTrue(reserved_keys["availabilityPrototypeIsNull"])
        self.assertTrue(reserved_keys["entriesFrozen"])
        self.assertTrue(reserved_keys["artifactsFrozen"])
        self.assertTrue(reserved_keys["availabilityFrozen"])
        manifest_formats = observed["manifestFormats"]
        self.assertTrue(manifest_formats["authoritativeCommit"])
        self.assertEqual(manifest_formats["authoritativeCandidateId"], "candidate-1")
        self.assertFalse(manifest_formats["unsupportedCanonicalOk"])
        self.assertIn("artifact_format_unsupported", manifest_formats["unsupportedCanonicalCodes"])
        self.assertTrue(manifest_formats["missingOptionalOk"])
        self.assertEqual(manifest_formats["missingOptionalStatus"], "unsupported_format")
        self.assertIn("artifact_format_unsupported", manifest_formats["missingOptionalCodes"])
        jsonl_identity = observed["jsonlPayloadIdentity"]
        self.assertFalse(jsonl_identity["conflictOk"])
        self.assertIn("artifact_run_id_conflict", jsonl_identity["conflictCodes"])
        self.assertEqual(jsonl_identity["conflictRecordIndex"], 0)
        self.assertEqual(jsonl_identity["conflictActualRunId"], "other-run")
        self.assertTrue(jsonl_identity["missingRunIdOk"])
        explicit_paths = observed["explicitInputPaths"]
        self.assertFalse(explicit_paths["nameOnlyOk"])
        self.assertIn("relative_path_missing", explicit_paths["nameOnlyCodes"])
        self.assertTrue(explicit_paths["explicitRelativePathOk"])
        self.assertTrue(explicit_paths["webkitRelativePathOk"])
        whitespace_kind = observed["whitespaceKind"]
        self.assertFalse(whitespace_kind["ok"], whitespace_kind)
        self.assertIn("artifact_kind_invalid", whitespace_kind["codes"])
        self.assertIsNone(whitespace_kind["committedManifestKind"])
        self.assertFalse(whitespace_kind["normalizedArtifactOwn"])
        self.assertFalse(whitespace_kind["viewerResolvable"])

    def test_readonly_envelope_adapter_normalizes_to_bundle_projection_and_fails_closed(self):
        self.assertIsNotNone(shutil.which("node"), "node is required for read-only envelope adapter test")
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const context = {console, JSON, Map, Set, Object, Array, String, Number, Error, Promise};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);
vm.runInContext(fs.readFileSync(process.argv[3], "utf8"), context);

const {
  RelativePathBundleAdapter,
  ReadonlyEnvelopeAdapter,
  RunDataStore,
  DiagnosticProjection,
} = context.SpiroRunData;

function bundleFile(relativePath, payload) {
  return {
    relativePath,
    text: async () => typeof payload === "string" ? payload : JSON.stringify(payload),
  };
}

function envelopeFile(name, payload) {
  return {
    name,
    text: async () => JSON.stringify(payload),
  };
}

function envelope(surface, runId, artifactKind, payload, status = "available", severity = "info", unavailable = null) {
  return {
    schema_version: "v11.readonly_api.envelope.v1",
    status,
    severity,
    surface,
    read_only: true,
    run_id: runId,
    artifact_kind: artifactKind,
    source: {backend: "json_artifact_repository", manifest_path: "run-manifest.json"},
    payload,
    unavailable,
  };
}

function manifest(runId) {
  return {
    schema_version: "v6.run_manifest.v1",
    run_id: runId,
    artifacts: [
      {kind: "canonical_evidence", path: "canonical.json", format: "json", run_id: runId, schema_ref: "schemas/canonical-evidence.schema.json"},
      {kind: "screening_input_view", path: "screening.json", format: "json", run_id: runId, schema_ref: "schemas/screening-input-view.schema.json"},
      {kind: "review_events", path: "review-events.jsonl", format: "jsonl", run_id: runId, schema_ref: "schemas/review-event.schema.json"},
      {kind: "model_evaluation", path: "model.json", format: "json", run_id: runId, schema_ref: "schemas/model-evaluation.schema.json"},
    ],
  };
}

function artifactEnvelope(runId, kind, path, format, payload) {
  const metadata = {kind, path, format, run_id: runId, schema_ref: `schemas/${kind}.schema.json`};
  return envelope("artifact_by_kind", runId, kind, {
    kind,
    path,
    format,
    schema_ref: metadata.schema_ref,
    metadata,
    schema_validation: {status: "valid"},
    data: format === "json" ? payload : null,
    records: format === "jsonl" ? payload : [],
    record_count: format === "jsonl" ? payload.length : null,
  });
}

function codes(result) {
  return result.diagnostics.map((item) => item.code);
}

function groupIds(projection) {
  return Object.fromEntries(
    Object.entries(projection.groups).map(([group, candidates]) => [
      group,
      candidates.map((candidate) => candidate.candidateId),
    ])
  );
}

async function main() {
  const runId = "run-envelope";
  const runManifest = manifest(runId);
  const canonical = {records: [{candidate_id: "candidate-1"}]};
  const screening = {candidates: [{candidate_id: "candidate-1", status: "pass"}]};
  const reviewEvents = [{event_id: "event-1", run_id: runId, decision: "accept"}];
  const unavailable = {reason: "artifact_missing", status: "unavailable", kind: "model_evaluation", path: "model.json"};

  const bundleFiles = [
    bundleFile("run-manifest.json", runManifest),
    bundleFile("canonical.json", canonical),
    bundleFile("screening.json", screening),
    bundleFile("review-events.jsonl", reviewEvents.map((event) => JSON.stringify(event)).join("\n")),
  ];
  const envelopeFiles = [
    envelopeFile("manifest.json", envelope("manifest", runId, null, runManifest)),
    envelopeFile("canonical-envelope.json", artifactEnvelope(runId, "canonical_evidence", "canonical.json", "json", canonical)),
    envelopeFile("screening-envelope.json", artifactEnvelope(runId, "screening_input_view", "screening.json", "json", screening)),
    envelopeFile("review-events-envelope.json", artifactEnvelope(runId, "review_events", "review-events.jsonl", "jsonl", reviewEvents)),
    envelopeFile("model-envelope.json", envelope("artifact_by_kind", runId, "model_evaluation", null, "unavailable", "warning", unavailable)),
  ];

  const bundle = await new RunDataStore(new RelativePathBundleAdapter()).replace(bundleFiles);
  const envelopeResult = await new RunDataStore(new ReadonlyEnvelopeAdapter()).replace(envelopeFiles);
  const autoEnvelope = await new RunDataStore().replace(envelopeFiles);
  const bundleProjection = context.SpiroCandidateProjection.project(bundle.snapshot);
  const envelopeProjection = context.SpiroCandidateProjection.project(envelopeResult.snapshot);
  const envelopeDiagnostics = DiagnosticProjection.project(envelopeResult.snapshot);

  const notReadonly = await new RunDataStore(new ReadonlyEnvelopeAdapter()).replace([
    envelopeFile("bad.json", {...envelope("manifest", runId, null, runManifest), read_only: false}),
  ]);
  const unknownSchema = await new RunDataStore(new ReadonlyEnvelopeAdapter()).replace([
    envelopeFile("bad.json", {...envelope("manifest", runId, null, runManifest), schema_version: "v0"}),
  ]);
  const mixedRun = await new RunDataStore(new ReadonlyEnvelopeAdapter()).replace([
    envelopeFile("manifest.json", envelope("manifest", runId, null, runManifest)),
    envelopeFile("canonical-envelope.json", artifactEnvelope("other-run", "canonical_evidence", "canonical.json", "json", canonical)),
  ]);
  const duplicateKind = await new RunDataStore(new ReadonlyEnvelopeAdapter()).replace([
    envelopeFile("manifest.json", envelope("manifest", runId, null, runManifest)),
    envelopeFile("canonical-a.json", artifactEnvelope(runId, "canonical_evidence", "canonical.json", "json", canonical)),
    envelopeFile("canonical-b.json", artifactEnvelope(runId, "canonical_evidence", "canonical.json", "json", canonical)),
  ]);
  const metadataConflict = await new RunDataStore(new ReadonlyEnvelopeAdapter()).replace([
    envelopeFile("manifest.json", envelope("manifest", runId, null, runManifest)),
    envelopeFile("canonical-envelope.json", artifactEnvelope(runId, "canonical_evidence", "other.json", "json", canonical)),
  ]);

  process.stdout.write(JSON.stringify({
    bundleOk: bundle.ok,
    envelopeOk: envelopeResult.ok,
    autoOk: autoEnvelope.ok,
    manifestPath: envelopeResult.snapshot.manifestMetadata.path,
    canonicalCandidate: envelopeResult.snapshot.artifacts.canonical_evidence.payload.records[0].candidate_id,
    reviewEventCount: envelopeResult.snapshot.artifacts.review_events.payload.length,
    envelopeMetadataStatus: envelopeResult.snapshot.artifacts.canonical_evidence.readonlyEnvelope.schemaValidation.status,
    envelopeReadOnly: envelopeResult.snapshot.artifacts.canonical_evidence.readonlyEnvelope.readOnly,
    bundleGroups: groupIds(bundleProjection),
    envelopeGroups: groupIds(envelopeProjection),
    modelState: envelopeDiagnostics.panels.model_evaluation.state,
    modelAvailability: envelopeResult.snapshot.availability.model_evaluation,
    notReadonly: codes(notReadonly),
    unknownSchema: codes(unknownSchema),
    mixedRun: {ok: mixedRun.ok, codes: codes(mixedRun)},
    duplicateKind: codes(duplicateKind),
    metadataConflict: codes(metadataConflict),
  }));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as file:
            file.write(runner)
            runner_path = Path(file.name)
        try:
            result = subprocess.run(
                [
                    "node",
                    str(runner_path),
                    "frontend/artifact-viewer/run-data-store.js",
                    "frontend/artifact-viewer/candidate-projection.js",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            runner_path.unlink(missing_ok=True)

        observed = json.loads(result.stdout)
        self.assertTrue(observed["bundleOk"])
        self.assertTrue(observed["envelopeOk"])
        self.assertTrue(observed["autoOk"])
        self.assertEqual(observed["manifestPath"], "run-manifest.json")
        self.assertEqual(observed["canonicalCandidate"], "candidate-1")
        self.assertEqual(observed["reviewEventCount"], 1)
        self.assertEqual(observed["envelopeMetadataStatus"], "valid")
        self.assertTrue(observed["envelopeReadOnly"])
        self.assertEqual(observed["bundleGroups"], observed["envelopeGroups"])
        flattened_ids = [
            candidate_id
            for candidate_ids in observed["envelopeGroups"].values()
            for candidate_id in candidate_ids
        ]
        self.assertIn("candidate-1", flattened_ids)
        self.assertEqual(observed["modelState"], "unavailable")
        self.assertEqual(observed["modelAvailability"]["status"], "unavailable")
        self.assertEqual(observed["modelAvailability"]["unavailable"]["reason"], "artifact_missing")
        self.assertIn("readonly_envelope_not_read_only", observed["notReadonly"])
        self.assertIn("readonly_envelope_schema_version", observed["unknownSchema"])
        self.assertFalse(observed["mixedRun"]["ok"])
        self.assertIn("readonly_envelope_run_id_conflict", observed["mixedRun"]["codes"])
        self.assertIn("duplicate_artifact_kind", observed["duplicateKind"])
        self.assertIn("readonly_envelope_metadata_conflict", observed["metadataConflict"])

    def test_project_store_loads_nested_project_bundle_and_selects_runs_atomically(self):
        self.assertIsNotNone(shutil.which("node"), "node is required for project store test")
        runner = r"""
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const context = {console, JSON, Map, Set, Object, Array, String, Number, Error, Promise};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);
const {
  ProjectBundleAdapter,
  ProjectSelectorProjection,
  ProjectStore,
} = context.SpiroRunData;

function file(relativePath, payload) {
  return {
    name: relativePath.split("/").pop(),
    relativePath,
    webkitRelativePath: relativePath,
    text: async () => typeof payload === "string" ? payload : JSON.stringify(payload),
  };
}

function fixtureFiles(root, prefix = "") {
  const out = [];
  function walk(dir) {
    for (const entry of fs.readdirSync(dir, {withFileTypes: true})) {
      const absolute = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(absolute);
      } else {
        const rel = path.relative(root, absolute).replaceAll("\\", "/");
        out.push(file(prefix ? `${prefix}/${rel}` : rel, fs.readFileSync(absolute, "utf8")));
      }
    }
  }
  walk(root);
  return out;
}

(async () => {
  const fixtureRoot = process.argv[3];
  const store = new ProjectStore(new ProjectBundleAdapter());
  const committed = await store.replace(fixtureFiles(fixtureRoot, "nested/project"));
  const snapshot = store.snapshot();
  const beforeSelection = JSON.stringify(snapshot.runs[0].snapshot.artifacts);
  const selection = store.selectRuns("run-001", "run-002");
  const afterSelection = JSON.stringify(snapshot.runs[0].snapshot.artifacts);
  const selector = ProjectSelectorProjection.project(snapshot, selection);
  const html = ProjectSelectorProjection.render(selector);
  const keyboardNext = ProjectSelectorProjection.nextRunId(snapshot.runIds, "run-001", "ArrowRight");
  const keyboardHome = ProjectSelectorProjection.nextRunId(snapshot.runIds, "run-002", "Home");
  const escaping = ProjectSelectorProjection.render(ProjectSelectorProjection.project({
    ...snapshot,
    runs: [{...snapshot.runs[0], runId: "<bad&run>"}],
    runIds: ["<bad&run>"],
  }, {sourceRunId: "<bad&run>", targetRunId: null}));

  const staleFailure = await store.replace([
    file("nested/project/project-run-index.json", {...snapshot.index, project_id: "bad-project", runs: [
      {...snapshot.index.runs[0], project_id: "bad-project"},
      {...snapshot.index.runs[1], project_id: "other-project"},
    ]}),
  ]);
  const afterFailure = store.snapshot();
  const duplicate = await new ProjectStore(new ProjectBundleAdapter()).replace([
    file("project/project-run-index.json", snapshot.index),
    file("project/project-run-index.json", snapshot.index),
  ]);

  process.stdout.write(JSON.stringify({
    committedOk: committed.ok,
    projectId: snapshot.projectId,
    runIds: snapshot.runIds,
    runCount: snapshot.runs.length,
    comparisonStatuses: snapshot.comparisons.map((item) => item.compatibilityStatus),
    sourceManifestPath: snapshot.runs[0].snapshot.manifestMetadata.path,
    sourceCanonicalResolvedPath: snapshot.runs[0].snapshot.artifacts.canonical_evidence.resolvedPath,
    selection,
    selectorState: selector.state,
    selectorHtml: html,
    keyboardNext,
    keyboardHome,
    escaping,
    selectionMutatedRun: beforeSelection !== afterSelection,
    staleFailureOk: staleFailure.ok,
    afterFailureRunCount: afterFailure.runs.length,
    duplicateCodes: duplicate.diagnostics.map((item) => item.code),
  }));
})();
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as file:
            file.write(runner)
            runner_path = Path(file.name)
        try:
            result = subprocess.run(
                [
                    "node",
                    str(runner_path),
                    "frontend/artifact-viewer/run-data-store.js",
                    "tests/fixtures/v20_project_evolution",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            runner_path.unlink(missing_ok=True)

        observed = json.loads(result.stdout)
        self.assertTrue(observed["committedOk"])
        self.assertEqual(observed["projectId"], "project-v20-fixture")
        self.assertEqual(observed["runIds"], ["run-001", "run-002"])
        self.assertEqual(observed["runCount"], 2)
        self.assertEqual(observed["comparisonStatuses"], ["partially_comparable"])
        self.assertEqual(observed["sourceManifestPath"], "nested/project/run-001/run-manifest.json")
        self.assertEqual(observed["sourceCanonicalResolvedPath"], "nested/project/run-001/canonical-evidence.json")
        self.assertEqual(observed["selection"]["compatibilityStatus"], "partially_comparable")
        self.assertEqual(observed["selection"]["sourceValidationStatus"], "valid")
        self.assertEqual(observed["selectorState"], "ready")
        self.assertIn('role="listbox"', observed["selectorHtml"])
        self.assertIn('data-run-id="run-001"', observed["selectorHtml"])
        self.assertEqual(observed["keyboardNext"], "run-002")
        self.assertEqual(observed["keyboardHome"], "run-001")
        self.assertIn("&lt;bad&amp;run&gt;", observed["escaping"])
        self.assertFalse(observed["selectionMutatedRun"])
        self.assertFalse(observed["staleFailureOk"])
        self.assertEqual(observed["afterFailureRunCount"], 0)
        self.assertIn("duplicate_project_path", observed["duplicateCodes"])

    def test_candidate_history_and_project_diagnostics_render_backend_delta_fail_closed(self):
        self.assertIsNotNone(shutil.which("node"), "node is required for candidate history test")
        runner = r"""
const fs = require("fs");
const path = require("path");
const vm = require("vm");
const context = {console, JSON, Map, Set, Object, Array, String, Number, Error, Promise};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);
const {
  CandidateHistoryProjection,
  ProjectBundleAdapter,
  ProjectDiagnosticsProjection,
  ProjectStore,
} = context.SpiroRunData;

function file(relativePath, payload) {
  return {
    name: relativePath.split("/").pop(),
    relativePath,
    webkitRelativePath: relativePath,
    text: async () => typeof payload === "string" ? payload : JSON.stringify(payload),
  };
}

function fixtureFiles(root) {
  const out = [];
  function walk(dir) {
    for (const entry of fs.readdirSync(dir, {withFileTypes: true})) {
      const absolute = path.join(dir, entry.name);
      if (entry.isDirectory()) walk(absolute);
      else out.push(file(path.relative(root, absolute).replaceAll("\\", "/"), fs.readFileSync(absolute, "utf8")));
    }
  }
  walk(root);
  return out;
}

(async () => {
  const store = new ProjectStore(new ProjectBundleAdapter());
  await store.replace(fixtureFiles(process.argv[3]));
  const snapshot = store.snapshot();
  const selection = store.selectRuns("run-001", "run-002");
  const history = CandidateHistoryProjection.project(snapshot, selection);
  const historyHtml = CandidateHistoryProjection.render(history);
  const diagnostics = ProjectDiagnosticsProjection.project(snapshot);
  const diagnosticsHtml = ProjectDiagnosticsProjection.render(diagnostics);
  const ambiguousSnapshot = {
    ...snapshot,
    comparisons: [{
      ...snapshot.comparisons[0],
      delta: {
        ...snapshot.comparisons[0].delta,
        candidate_deltas: [{candidate_id: "", status_transition: {from: "pass", to: "reject", reason_codes: ["AMBIGUOUS"]}}],
      },
    }],
  };
  const ambiguousHistory = CandidateHistoryProjection.project(ambiguousSnapshot, selection);
  const staleFailure = await store.replace([
    file("project-run-index.json", {...snapshot.index, project_id: "bad-project", runs: [
      {...snapshot.index.runs[0], project_id: "bad-project"},
      {...snapshot.index.runs[1], project_id: "other-project"},
    ]}),
  ]);
  const failureDiagnostics = ProjectDiagnosticsProjection.project(staleFailure.snapshot);

  process.stdout.write(JSON.stringify({
    state: history.state,
    candidateIds: history.candidates.map((item) => item.candidateId),
    transition: history.candidates[0].statusTransition,
    evidenceAdded: history.candidates[0].evidenceChange.added,
    blockerResolved: history.candidates[0].blockerChange.resolved,
    scoreStatus: history.candidates[0].scoreRank.status,
    html: historyHtml,
    diagnosticsCodes: diagnostics.items.map((item) => item.code),
    diagnosticsHtml,
    ambiguousRows: ambiguousHistory.candidates.length,
    ambiguousCodes: ambiguousHistory.diagnostics.map((item) => item.code),
    failureOk: staleFailure.ok,
    failureCodes: failureDiagnostics.items.map((item) => item.code),
  }));
})();
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as file:
            file.write(runner)
            runner_path = Path(file.name)
        try:
            result = subprocess.run(
                [
                    "node",
                    str(runner_path),
                    "frontend/artifact-viewer/run-data-store.js",
                    "tests/fixtures/v20_project_evolution",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            runner_path.unlink(missing_ok=True)

        observed = json.loads(result.stdout)
        self.assertEqual(observed["state"], "ready")
        self.assertEqual(observed["candidateIds"], ["candidate-transition", "candidate-unchanged"])
        self.assertEqual(observed["transition"]["from"], "defer")
        self.assertEqual(observed["transition"]["to"], "pass")
        self.assertEqual(observed["evidenceAdded"], ["ev-transition-lumo"])
        self.assertEqual(observed["blockerResolved"], ["review-transition"])
        self.assertEqual(observed["scoreStatus"], "non_comparable")
        self.assertIn("DATASET_SNAPSHOT_CHANGED", observed["html"])
        self.assertNotIn("score_delta", observed["html"])
        self.assertIn("project_comparison_degraded", observed["diagnosticsCodes"])
        self.assertIn("partially_comparable", observed["diagnosticsHtml"])
        self.assertEqual(observed["ambiguousRows"], 0)
        self.assertIn("candidate_identity_unavailable", observed["ambiguousCodes"])
        self.assertFalse(observed["failureOk"])
        self.assertIn("mixed_project_id", observed["failureCodes"])

    def test_diagnostic_projection_lifecycle_and_stale_load_guard(self):
        self.assertIsNotNone(shutil.which("node"), "node is required for run store lifecycle test")
        runner = r"""
const fs = require("fs");
const vm = require("vm");
const context = {console, JSON, Map, Set, Object, Array, String, Number, Error, Promise};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);
const {RunDataStore, DiagnosticProjection} = context.SpiroRunData;

function artifact(kind, path, format = "json") {
  return {kind, path, format, run_id: "run-1"};
}
const snapshot = {
  manifest: {run_id: "run-1", artifacts: [
    artifact("canonical_evidence", "canonical.json"),
    artifact("screening_input_view", "screening.json"),
    artifact("review_events", "review-events.jsonl", "jsonl"),
    artifact("optional_missing", "optional.json"),
    artifact("optional_bad", "optional-bad.json"),
  ]},
  manifestMetadata: {runId: "run-1"},
  artifacts: {
    canonical_evidence: {payload: {records: [{candidate_id: "c-1"}]}},
    screening_input_view: {payload: {candidates: []}},
    review_events: {payload: []},
  },
  availability: {
    canonical_evidence: {kind: "canonical_evidence", status: "available", path: "canonical.json"},
    screening_input_view: {kind: "screening_input_view", status: "available", path: "screening.json"},
    review_events: {kind: "review_events", status: "available", path: "review-events.jsonl"},
    optional_missing: {kind: "optional_missing", status: "missing", path: "optional.json", diagnosticCodes: ["artifact_missing"]},
    optional_bad: {kind: "optional_bad", status: "parse_error", path: "optional-bad.json", diagnosticCodes: ["artifact_parse_error"]},
  },
  diagnostics: [
    {code: "artifact_missing", severity: "warning", kind: "optional_missing", path: "optional.json", message: "missing optional"},
    {code: "artifact_parse_error", severity: "warning", kind: "optional_bad", path: "optional-bad.json", message: "bad optional"},
  ],
};
const lifecycle = DiagnosticProjection.project(snapshot);

function file(relativePath, payload) {
  return {
    relativePath,
    text: async () => typeof payload === "string" ? payload : JSON.stringify(payload),
  };
}
function manifest(runId) {
  return {
    run_id: runId,
    artifacts: [{kind: "canonical_evidence", path: "canonical.json", format: "json", run_id: runId}],
  };
}
class DelayedAdapter {
  constructor() {
    this.calls = [];
  }
  async index(files) {
    const call = files[0];
    this.calls.push(call.label);
    await call.delay;
    return {
      ok: true,
      paths: ["run-manifest.json", "canonical.json"],
      manifestPath: "run-manifest.json",
      entries: {
        "run-manifest.json": {path: "run-manifest.json", text: JSON.stringify(manifest(call.runId))},
        "canonical.json": {path: "canonical.json", text: JSON.stringify({records: [{candidate_id: call.runId}]})},
      },
      diagnostics: [],
    };
  }
}
let releaseSlow;
let releaseFast;
const slowDelay = new Promise((resolve) => { releaseSlow = resolve; });
const fastDelay = new Promise((resolve) => { releaseFast = resolve; });
const adapter = new DelayedAdapter();
const store = new RunDataStore(adapter);
const slow = store.replace([{label: "slow", runId: "slow-run", delay: slowDelay}]);
const fast = store.replace([{label: "fast", runId: "fast-run", delay: fastDelay}]);
releaseFast();
fast.then(() => releaseSlow());
Promise.all([slow, fast]).then(([slowResult, fastResult]) => {
  process.stdout.write(JSON.stringify({
    available: lifecycle.panels.canonical_evidence,
    empty: lifecycle.panels.review_events,
    degraded: lifecycle.panels.optional_missing,
    invalid: lifecycle.panels.optional_bad,
    unavailable: lifecycle.panels.model_evaluation,
    fastOk: fastResult.ok,
    slowOk: slowResult.ok,
    slowCodes: slowResult.diagnostics.map((item) => item.code),
    committedRunId: store.snapshot().manifest.run_id,
  }));
}).catch((error) => {
  console.error(error.stack || error.message);
  process.exit(1);
});
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as file:
            file.write(runner)
            runner_path = Path(file.name)
        try:
            result = subprocess.run(
                ["node", str(runner_path), "frontend/artifact-viewer/run-data-store.js"],
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            runner_path.unlink(missing_ok=True)
        observed = json.loads(result.stdout)
        self.assertEqual(observed["available"]["state"], "available")
        self.assertEqual(observed["empty"]["state"], "empty")
        self.assertEqual(observed["degraded"]["state"], "degraded")
        self.assertEqual(observed["invalid"]["state"], "invalid")
        self.assertEqual(observed["unavailable"]["state"], "unavailable")
        self.assertTrue(observed["fastOk"])
        self.assertFalse(observed["slowOk"])
        self.assertIn("stale_load_generation", observed["slowCodes"])
        self.assertEqual(observed["committedRunId"], "fast-run")

    def test_viewer_script_renders_manifest_artifacts(self):
        script = Path("frontend/artifact-viewer/viewer.js").read_text(encoding="utf-8")

        self.assertNotIn("function parseArtifact", script)
        self.assertNotIn("function parseJsonl", script)
        self.assertIn("function renderManifest", script)
        self.assertIn("function renderRecommendations", script)
        self.assertIn("function renderTimeline", script)
        self.assertIn("function renderEnrichmentFlow", script)
        self.assertIn("function renderCanonicalEvidence", script)
        self.assertIn("function renderScoringView", script)
        self.assertIn("function renderReviewClosure", script)
        self.assertIn("function getArtifact", script)
        self.assertIn("runDataStore.replace", script)
        self.assertIn("function renderCandidateTracer", script)
        self.assertNotIn("legacyFileName", script)
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

    def test_viewer_renders_paper_diagnostics_without_candidate_join_or_validation_claims(self):
        self.assertIsNotNone(shutil.which("node"), "node is required for paper diagnostics test")
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
  console, JSON, Map, Set, Object, Array, String, Number, Error,
  document: {getElementById: element},
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);
context.renderPaperDiagnostics(
  [
    {asset_id: "asset-1", doi: "10.123/test", rights: "open <unsafe>", sha256: "sha-source", license: "CC-BY"},
  ],
  [
    {claim_id: "claim-1", asset_id: "asset-1", chunk_id: "chunk-1", doi: "10.123/test", property_name: "pce_percent", value: 20.1, unit: "%", confidence: 0.8, text_span: "<span>unsafe</span>", review_required: true, lineage: {extractor: "fixture"}},
    {claim_id: "claim-name-only", candidate_name: "Spiro-ish", formula: "C1", text_span: "must stay run scoped"},
  ],
  {papers: [{doi: "10.123/test", status: "stored"}]},
  {matches: [{doi: "10.123/test", note: "internal only"}]},
  {note_count: 2}
);
process.stdout.write(JSON.stringify({
  html: element("paperDiagnosticsList").innerHTML,
  count: element("paperDiagnosticsCount").textContent,
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
        observed = json.loads(result.stdout)
        self.assertIn("1 source assets / 2 claims", observed["count"])
        self.assertIn("asset-1", observed["html"])
        self.assertIn("sha-source", observed["html"])
        self.assertIn("CC-BY", observed["html"])
        self.assertIn("claim-1", observed["html"])
        self.assertIn("chunk-1", observed["html"])
        self.assertIn("review required", observed["html"])
        self.assertIn("internal diagnostic context", observed["html"])
        self.assertIn("candidate paper tab remains unavailable", observed["html"])
        self.assertIn("&lt;span&gt;unsafe&lt;/span&gt;", observed["html"])
        self.assertNotIn("<span>unsafe</span>", observed["html"])
        self.assertNotIn("external validation", observed["html"].lower())
        self.assertNotIn("candidate association", observed["html"].lower())

    def test_screening_status_display_never_invents_a_defer_decision(self):
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

const screening = {
  candidates: [
    {candidate_id: "missing-status"},
    {candidate_id: "empty-status", status: ""},
    {candidate_id: "unknown-status", status: "queued"},
    {candidate_id: "pass-status", status: "pass"},
    {candidate_id: "defer-status", status: "defer"},
    {candidate_id: "reject-status", status: "reject"},
  ],
};
context.renderCandidateTracer(screening, {records: []});
context.renderScreeningEligibility(screening);

function badge(html, candidateId) {
  const candidateStart = html.indexOf(`>${candidateId}</span>`);
  if (candidateStart === -1) throw new Error(`candidate ${candidateId} was not rendered`);
  const segment = html.slice(candidateStart, candidateStart + 500);
  const match = segment.match(/class="gate-status gate-([^" ]+)"(?: title="([^"]*)")?[^>]*>([^<]+)<\/span>/);
  if (!match) throw new Error(`candidate ${candidateId} badge was not rendered`);
  return {classStatus: match[1], reason: match[2] || "", text: match[3]};
}

const tracerHtml = element("candidateTable").innerHTML;
const eligibilityHtml = element("screeningEligibilityList").innerHTML;
vm.runInContext('state.selectedCandidateId = "unknown-status"', context);
context.renderCandidateTracer(screening, {records: []});
const unknownDetail = element("candidateDetail").innerHTML;
vm.runInContext('state.selectedCandidateId = "pass-status"', context);
context.renderCandidateTracer(screening, {records: []});
const passDetail = element("candidateDetail").innerHTML;
const ids = screening.candidates.map((candidate) => candidate.candidate_id);
process.stdout.write(JSON.stringify({
  tracer: Object.fromEntries(ids.map((id) => [id, badge(tracerHtml, id)])),
  eligibility: Object.fromEntries(ids.map((id) => [id, badge(eligibilityHtml, id)])),
  needsReviewCount: element("needsReviewCount").textContent,
  unknownDetail,
  passDetail,
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

        observed = json.loads(result.stdout)
        for surface_name in ("tracer", "eligibility"):
            surface = observed[surface_name]
            for candidate_id in ("missing-status", "empty-status"):
                self.assertEqual(surface[candidate_id]["classStatus"], "unavailable")
                self.assertEqual(surface[candidate_id]["text"], "unavailable")
                self.assertIn("not provided", surface[candidate_id]["reason"])
            self.assertEqual(surface["unknown-status"]["classStatus"], "unavailable")
            self.assertEqual(surface["unknown-status"]["text"], "unavailable")
            self.assertIn("Unsupported screening status: queued", surface["unknown-status"]["reason"])
            for status in ("pass", "defer", "reject"):
                candidate_id = f"{status}-status"
                self.assertEqual(surface[candidate_id]["classStatus"], status)
                self.assertEqual(surface[candidate_id]["text"], status)
        self.assertEqual(observed["needsReviewCount"], "1")
        self.assertIn("status unavailable", observed["unknownDetail"])
        self.assertIn("Unsupported screening status: queued", observed["unknownDetail"])
        self.assertNotIn("status queued", observed["unknownDetail"])
        self.assertIn("status pass", observed["passDetail"])
        self.assertNotIn("Unsupported screening status", observed["passDetail"])

    def test_bundle_bootstrap_renders_v13_candidate_and_retains_prior_run_on_failure(self):
        self.assertIsNotNone(shutil.which("node"), "node is required for viewer behavior test")
        runner = r"""
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const elements = new Map();
const listeners = new Map();
function element(id) {
  if (!elements.has(id)) {
    elements.set(id, {
      id,
      textContent: "",
      innerHTML: "",
      style: {},
      addEventListener: (type, handler) => listeners.set(`${id}:${type}`, handler),
    });
  }
  return elements.get(id);
}
const context = {
  console,
  Map,
  Set,
  Number,
  String,
  JSON,
  Object,
  Array,
  Error,
  Promise,
  document: {getElementById: element},
};
vm.createContext(context);
vm.runInContext(fs.readFileSync(process.argv[2], "utf8"), context);
vm.runInContext(fs.readFileSync(process.argv[3], "utf8"), context);
vm.runInContext(fs.readFileSync(process.argv[4], "utf8"), context);

function selectedFile(relativePath, text) {
  return {
    name: path.basename(relativePath),
    webkitRelativePath: relativePath.replaceAll("\\", "/"),
    text: async () => text,
  };
}

function fixtureFiles(directory) {
  const rootName = path.basename(directory);
  return fs.readdirSync(directory).map((name) => selectedFile(
    `${rootName}/${name}`,
    fs.readFileSync(path.join(directory, name), "utf8")
  ));
}

async function main() {
  const load = listeners.get("bundleFiles:change");
  if (!load) throw new Error("bundleFiles change handler was not registered");

  const noPriorManifest = {
    schema_version: "v6.run_manifest.v1",
    run_id: "failed-without-prior",
    artifacts: [],
  };
  await load({target: {files: [selectedFile(
    "failed/run-manifest.json",
    JSON.stringify(noPriorManifest)
  )]}});
  const noPrior = {
    runSummary: element("runSummary").textContent,
    candidateTable: element("candidateTable").innerHTML,
    error: element("errorState").textContent,
  };

  const files = fixtureFiles(process.argv[5]);
  await load({target: {files}});
  const committed = {
    runSummary: element("runSummary").textContent,
    candidateTable: element("candidateTable").innerHTML,
    candidateDetail: element("candidateDetail").innerHTML,
    artifactTable: element("artifactTable").innerHTML,
    loadState: element("loadState").textContent,
    errorDisplay: element("errorState").style.display,
  };
  const selectCandidate = listeners.get("candidateTable:click");
  if (!selectCandidate) throw new Error("candidateTable click handler was not registered");
  selectCandidate({target: {closest: () => ({dataset: {candidateId: "defer-1"}})}});
  const selected = {
    candidateTable: element("candidateTable").innerHTML,
    candidateDetail: element("candidateDetail").innerHTML,
  };

  const originalManifestFile = files.find((item) => item.name === "run-manifest.json");
  const originalManifest = JSON.parse(await originalManifestFile.text());
  const failedManifest = {
    ...originalManifest,
    run_id: "failed-replacement",
  };
  await load({target: {files: [selectedFile(
    "failed/run-manifest.json",
    JSON.stringify(failedManifest)
  )]}});
  const failedReplacement = {
    runSummary: element("runSummary").textContent,
    candidateTable: element("candidateTable").innerHTML,
    candidateDetail: element("candidateDetail").innerHTML,
    artifactTable: element("artifactTable").innerHTML,
    loadState: element("loadState").textContent,
    error: element("errorState").textContent,
  };

  process.stdout.write(JSON.stringify({noPrior, committed, selected, failedReplacement}));
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
"""
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as file:
            file.write(runner)
            runner_path = Path(file.name)
        try:
            result = subprocess.run(
                [
                    "node",
                    str(runner_path),
                    "frontend/artifact-viewer/run-data-store.js",
                    "frontend/artifact-viewer/candidate-projection.js",
                    "frontend/artifact-viewer/viewer.js",
                    "tests/fixtures/artifact_viewer/v13_algorithm_run",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            runner_path.unlink(missing_ok=True)

        observed = json.loads(result.stdout)
        self.assertEqual(observed["noPrior"]["runSummary"], "No run loaded")
        self.assertIn("No candidates loaded", observed["noPrior"]["candidateTable"])
        self.assertIn("Load failed", observed["noPrior"]["error"])
        self.assertNotIn("retained prior run", observed["noPrior"]["error"])

        committed = observed["committed"]
        self.assertIn("v13-algorithm-diagnostic-001", committed["runSummary"])
        self.assertIn('data-candidate-id="pass-1"', committed["candidateTable"])
        self.assertIn('data-candidate-id="defer-1"', committed["candidateTable"])
        self.assertIn("pass-1", committed["candidateDetail"])
        self.assertIn("small_molecule", committed["candidateDetail"])
        self.assertIn("status pass", committed["candidateDetail"])
        self.assertIn("screening-input-view.json", committed["artifactTable"])
        self.assertIn("available", committed["artifactTable"])
        self.assertIn("15 available", committed["loadState"])
        self.assertEqual(committed["errorDisplay"], "none")

        selected = observed["selected"]
        self.assertIn('data-candidate-id="defer-1"', selected["candidateTable"])
        self.assertIn('aria-pressed="true"', selected["candidateTable"])
        self.assertIn("defer-1", selected["candidateDetail"])
        self.assertIn("status defer", selected["candidateDetail"])

        failed = observed["failedReplacement"]
        self.assertEqual(failed["runSummary"], committed["runSummary"])
        self.assertEqual(failed["candidateTable"], selected["candidateTable"])
        self.assertEqual(failed["candidateDetail"], selected["candidateDetail"])
        self.assertEqual(failed["artifactTable"], committed["artifactTable"])
        self.assertIn("Load failed", failed["error"])
        self.assertIn("retained prior run v13-algorithm-diagnostic-001", failed["error"])
        self.assertIn("retained prior run v13-algorithm-diagnostic-001", failed["loadState"])
        self.assertNotIn("failed-replacement", failed["runSummary"])

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
vm.runInContext(fs.readFileSync(process.argv[3], "utf8"), context);

const parsedJsonl = context.SpiroRunData.parseArtifactPayload('{"a":1}\n\n{"b":2}\n', "jsonl");
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
                [
                    "node",
                    str(runner_path),
                    "frontend/artifact-viewer/run-data-store.js",
                    "frontend/artifact-viewer/viewer.js",
                ],
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
vm.runInContext(fs.readFileSync(process.argv[3], "utf8"), context);

let parseError = "";
try {
  context.SpiroRunData.parseArtifactPayload('{"ok":true}\n\n{bad}\n', "jsonl");
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
const matched = context.getArtifact("provider_cache_index");
vm.runInContext('state.artifacts.delete("nested/provider-cache-index.json");', context);
const unmatched = context.getArtifact("provider_cache_index");
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
                [
                    "node",
                    str(runner_path),
                    "frontend/artifact-viewer/run-data-store.js",
                    "frontend/artifact-viewer/viewer.js",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
        finally:
            runner_path.unlink(missing_ok=True)

        rendered = json.loads(result.stdout)
        self.assertIn("line 3", rendered["parseError"])
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
