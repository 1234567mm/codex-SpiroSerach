const state = {
  manifest: null,
  artifacts: new Map(),
  snapshot: null,
  selectedCandidateId: null,
  selectedCandidateTab: "overview",
  candidateProjection: null,
  candidateControls: {search: "", statuses: [], sort: "group"},
  projectEvolution: {documents: [], diagnostics: []},
  projectSnapshot: null,
  projectSelection: null,
};

const CANDIDATE_DETAIL_TABS = Object.freeze([
  {id: "overview", label: "Overview"},
  {id: "explanation", label: "Explanation"},
  {id: "diagnostics", label: "Diagnostics"},
  {id: "paper", label: "Paper Evidence"},
]);

const runDataStore = globalThis.SpiroRunData
  ? new globalThis.SpiroRunData.RunDataStore()
  : null;
const projectStore = globalThis.SpiroRunData
  ? new globalThis.SpiroRunData.ProjectStore()
  : null;

document.getElementById("bundleFiles").addEventListener("change", async (event) => {
  if (!runDataStore) {
    showError("Load failed: run data store is unavailable");
    return;
  }
  const result = await runDataStore.replace(event.target.files);
  if (!result.ok) {
    showLoadFailure(result);
    return;
  }
  applyCommittedSnapshot(result.snapshot);
  clearError();
  renderKnownArtifacts();
});

document.getElementById("projectBundleFiles").addEventListener("change", async (event) => {
  if (!projectStore) {
    showError("Load failed: project store is unavailable");
    return;
  }
  const result = await projectStore.replace(event.target.files);
  state.projectSnapshot = result.snapshot;
  state.projectSelection = result.selection;
  if (!result.ok) {
    showError(`Project load failed: ${result.diagnostics.map((item) => item.code).join(", ") || "unknown error"}`);
    renderProjectSelector();
    renderCandidateHistory();
    return;
  }
  const runIds = result.snapshot.runIds || [];
  if (runIds.length) {
    state.projectSelection = projectStore.selectRuns(runIds[0], runIds[1] || runIds[0]);
    const sourceRun = result.snapshot.runs.find((run) => run.runId === state.projectSelection.sourceRunId);
    if (sourceRun?.snapshot) {
      applyCommittedSnapshot(sourceRun.snapshot);
      renderKnownArtifacts();
    }
  }
  clearError();
  renderProjectSelector();
  renderCandidateHistory();
});

document.getElementById("projectEvolutionFiles").addEventListener("change", async (event) => {
  const result = await loadProjectEvolutionFiles(event.target.files);
  state.projectEvolution = result;
  renderProjectEvolution(result);
});

document.getElementById("projectRunSelector").addEventListener("click", (event) => {
  const button = event.target.closest?.("[data-run-id]");
  if (!button || !projectStore) return;
  const sourceRunId = button.dataset.runId;
  const targetRunId = (state.projectSnapshot?.runIds || []).find((runId) => runId !== sourceRunId) || sourceRunId;
  state.projectSelection = projectStore.selectRuns(sourceRunId, targetRunId);
  const sourceRun = state.projectSnapshot?.runs?.find((run) => run.runId === sourceRunId);
  if (sourceRun?.snapshot) {
    applyCommittedSnapshot(sourceRun.snapshot);
    renderKnownArtifacts();
  }
  renderProjectSelector();
  renderCandidateHistory();
});

document.getElementById("projectRunSelector").addEventListener("keydown", (event) => {
  const button = event.target.closest?.("[data-run-id]");
  if (!button || !globalThis.SpiroRunData?.ProjectSelectorProjection) return;
  const nextRunId = globalThis.SpiroRunData.ProjectSelectorProjection.nextRunId(
    state.projectSnapshot?.runIds || [],
    button.dataset.runId,
    event.key
  );
  if (!nextRunId || nextRunId === button.dataset.runId) return;
  event.preventDefault?.();
  const next = Array.from(document.querySelectorAll?.("[data-run-id]") || [])
    .find((item) => item.dataset?.runId === nextRunId);
  next?.focus?.();
});

document.getElementById("candidateTable").addEventListener("click", (event) => {
  const row = event.target.closest?.("[data-candidate-id]");
  if (!row) return;
  state.selectedCandidateId = row.dataset.candidateId;
  if (state.candidateProjection && globalThis.SpiroCandidateProjection) {
    renderCandidateWorkspace();
  } else {
    renderCandidateTracer(
      getKnownArtifact("screening_input_view"),
      getKnownArtifact("canonical_evidence")
    );
  }
});

document.getElementById("candidateDetail").addEventListener("click", (event) => {
  const tab = event.target.closest?.("[data-candidate-tab]");
  if (!tab) return;
  selectCandidateTab(tab.dataset.candidateTab);
});

document.getElementById("candidateDetail").addEventListener("keydown", (event) => {
  const tab = event.target.closest?.("[data-candidate-tab]");
  if (!tab) return;
  const currentIndex = CANDIDATE_DETAIL_TABS.findIndex((item) => item.id === tab.dataset.candidateTab);
  if (currentIndex < 0) return;
  let nextIndex = currentIndex;
  if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % CANDIDATE_DETAIL_TABS.length;
  else if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + CANDIDATE_DETAIL_TABS.length) % CANDIDATE_DETAIL_TABS.length;
  else if (event.key === "Home") nextIndex = 0;
  else if (event.key === "End") nextIndex = CANDIDATE_DETAIL_TABS.length - 1;
  else if (event.key === "Enter" || event.key === " ") nextIndex = currentIndex;
  else return;
  event.preventDefault?.();
  selectCandidateTab(CANDIDATE_DETAIL_TABS[nextIndex].id, {focus: true});
});

document.getElementById("candidateSearch").addEventListener("input", (event) => {
  state.candidateControls.search = event.target.value || "";
  renderCandidateWorkspace();
});

document.getElementById("candidateStatusFilter").addEventListener("change", (event) => {
  state.candidateControls.statuses = event.target.value === "all" ? [] : [event.target.value];
  renderCandidateWorkspace();
});

document.getElementById("candidateSort").addEventListener("change", (event) => {
  state.candidateControls.sort = event.target.value || "candidate-asc";
  renderCandidateWorkspace();
});

function applyCommittedSnapshot(snapshot) {
  state.snapshot = snapshot;
  state.manifest = snapshot.manifest;
  state.artifacts = new Map(
    Object.values(snapshot.artifacts).map((artifact) => [artifact.path, artifact.payload])
  );
  state.selectedCandidateId = null;
  state.selectedCandidateTab = "overview";
  state.candidateProjection = null;
}

function showLoadFailure(result) {
  const retained = result.retainedRunId
    ? `; retained prior run ${result.retainedRunId}`
    : "";
  const details = result.diagnostics
    .map((item) => `${item.code}: ${item.message}`)
    .join(" | ");
  showError(`Load failed${retained}. Failed input diagnostics: ${details || "unknown error"}`);
  document.getElementById("loadState").textContent = result.retainedRunId
    ? `Load failed; retained prior run ${result.retainedRunId}`
    : "Load failed; no run committed";
}

function renderManifest(manifest) {
  document.getElementById("artifactCount").textContent = String((manifest.artifacts || []).length);
  document.getElementById("candidateCount").textContent = String(manifest.candidate_count ?? 0);
  document.getElementById("needsReviewCount").textContent = String(
    manifest.context?.provider_outcomes?.failure_count ?? 0
  );
  document.getElementById("runSummary").textContent = [
    manifest.run_id ? `run ${manifest.run_id}` : "run pending",
    manifest.dataset_snapshot_id || "",
    manifest.generated_at || "",
  ]
    .filter(Boolean)
    .join(" / ");

  const rows = (manifest.artifacts || []).map((artifact) => {
    const hash = artifact.sha256 ? artifact.sha256.slice(0, 12) : "-";
    const availability = state.snapshot?.availability?.[artifact.kind];
    const artifactDiagnostics = (state.snapshot?.diagnostics || [])
      .filter((item) => item.kind === artifact.kind)
      .map((item) => item.code)
      .join(", ");
    return `<tr>
      <td>${escapeHtml(artifact.kind || "-")}</td>
      <td>${escapeHtml(artifact.path || "-")}</td>
      <td>${escapeHtml(availability?.status || (state.artifacts.has(artifact.path) ? "available" : "not loaded"))}</td>
      <td>${escapeHtml(artifactDiagnostics || "-")}</td>
      <td>${escapeHtml(String(artifact.bytes ?? "-"))}</td>
      <td>${escapeHtml(hash)}</td>
    </tr>`;
  });
  document.getElementById("artifactTable").innerHTML = rows.join("") || `<tr><td colspan="6">No artifacts</td></tr>`;
  if (state.snapshot) {
    const availableCount = Object.values(state.snapshot.availability)
      .filter((item) => item.status === "available").length;
    document.getElementById("loadState").textContent =
      `${availableCount} available / ${state.snapshot.diagnostics.length} diagnostics`;
  } else {
    document.getElementById("loadState").textContent = state.artifacts.size
      ? `${state.artifacts.size} files loaded`
      : "Manifest loaded";
  }
}

function renderKnownArtifacts() {
  const recommendations = getKnownArtifact("recommendations");
  const trace = getKnownArtifact("agent_trace") || [];
  const enrichment = getKnownArtifact("enrichment_results");
  const canonicalEvidence = getKnownArtifact("canonical_evidence");
  const scoringView = getKnownArtifact("scoring_view");
  const screeningInputView = getKnownArtifact("screening_input_view");
  const modelEvaluation = getKnownArtifact("model_evaluation");
  const reviewEvents = getKnownArtifact("review_events") || [];
  const reviewSummary = getKnownArtifact("review_summary");
  const recomputeMarkers = getKnownArtifact("recompute_markers") || [];
  const sourceAssets = getKnownArtifact("source_assets") || [];
  const literatureClaims = getKnownArtifact("literature_claims") || [];
  const paperVaultSummary = getKnownArtifact("paper_vault_summary");
  const paperCrossRefReport = getKnownArtifact("paper_cross_ref_report");
  const obsidianNotes = getKnownArtifact("obsidian_notes");
  const cacheIndex = getKnownArtifact("provider_cache_index");
  const reviewQueue = getKnownArtifact("review_queue") || [];
  if (state.manifest) {
    renderManifest(state.manifest);
  }
  renderRecommendations(recommendations);
  renderTimeline(trace);
  renderEnrichmentFlow(enrichment, cacheIndex, reviewQueue, trace);
  renderCanonicalEvidence(canonicalEvidence);
  renderScoringView(scoringView);
  renderScreeningEligibility(screeningInputView);
  renderModelEvaluation(modelEvaluation);
  renderReviewClosure(reviewEvents, reviewSummary, recomputeMarkers);
  renderPaperDiagnostics(
    sourceAssets,
    literatureClaims,
    paperVaultSummary,
    paperCrossRefReport,
    obsidianNotes
  );
  renderReviewQueue(reviewQueue);
  if (globalThis.SpiroCandidateProjection) {
    state.candidateProjection = globalThis.SpiroCandidateProjection.project(
      state.snapshot || projectionSnapshotFromViewerState()
    );
    renderCandidateWorkspace();
  } else {
    renderCandidateTracer(screeningInputView, canonicalEvidence);
  }
}

async function loadProjectEvolutionFiles(files) {
  const documents = [];
  const diagnostics = [];
  for (const file of Array.from(files || [])) {
    const name = file?.name || "selected document";
    if (!/\.(md|markdown)$/i.test(name)) {
      diagnostics.push({
        code: "project_evolution_unsupported_file",
        severity: "warning",
        message: `${name} was skipped because only Markdown files are imported`,
      });
      continue;
    }
    let text;
    try {
      text = await file.text();
    } catch (error) {
      diagnostics.push({
        code: "project_evolution_read_error",
        severity: "warning",
        message: `${name} could not be read: ${error.message}`,
      });
      continue;
    }
    const parsed = parseProjectEvolutionMarkdown(name, text);
    diagnostics.push(...parsed.diagnostics);
    if (parsed.document) documents.push(parsed.document);
  }
  return {documents, diagnostics};
}

function parseProjectEvolutionMarkdown(filename, text) {
  const diagnostics = [];
  const source = typeof text === "string" ? text : "";
  if (!source.trim()) {
    return {
      document: null,
      diagnostics: [{
        code: "project_evolution_empty_document",
        severity: "warning",
        message: `${filename} is empty and was not imported`,
      }],
    };
  }

  const lines = source.split(/\r?\n/);
  const frontMatter = parseFrontMatter(lines);
  const titleLine = lines.find((line) => /^#\s+/.test(line));
  const headings = lines
    .filter((line) => /^#{1,6}\s+/.test(line))
    .slice(0, 18)
    .map((line) => {
      const match = line.match(/^(#{1,6})\s+(.+)$/);
      return {level: match[1].length, text: match[2].trim()};
    });
  if (!headings.length) {
    diagnostics.push({
      code: "project_evolution_no_headings",
      severity: "warning",
      message: `${filename} has no Markdown headings; imported as context only`,
    });
  }
  const metadata = {
    version: frontMatter.version || findDeclaredValue(lines, "version"),
    status: frontMatter.status || findDeclaredValue(lines, "status"),
  };
  const gateLanguage = lines
    .filter((line) => /\b(gate|exit|acceptance|verification|completion|complete)\b/i.test(line))
    .slice(0, 8)
    .map((line) => line.trim())
    .filter(Boolean);

  return {
    document: {
      filename,
      title: titleLine ? titleLine.replace(/^#\s+/, "").trim() : filename,
      metadata,
      headings,
      gateLanguage,
      lineCount: lines.length,
    },
    diagnostics,
  };
}

function parseFrontMatter(lines) {
  if (lines[0]?.trim() !== "---") return {};
  const metadata = {};
  for (let index = 1; index < lines.length; index += 1) {
    const line = lines[index].trim();
    if (line === "---") break;
    const match = line.match(/^([A-Za-z0-9_-]+)\s*:\s*(.+)$/);
    if (match) metadata[match[1].toLowerCase()] = match[2].trim();
  }
  return metadata;
}

function findDeclaredValue(lines, key) {
  const pattern = new RegExp(`^\\\\s*${key}\\\\s*:\\\\s*(.+)$`, "i");
  const line = lines.find((item) => pattern.test(item));
  return line ? line.match(pattern)[1].trim() : "";
}

function renderProjectEvolution(projectEvolution = state.projectEvolution) {
  const documents = projectEvolution?.documents || [];
  const diagnostics = projectEvolution?.diagnostics || [];
  document.getElementById("projectEvolutionCount").textContent =
    `${documents.length} documents / ${diagnostics.length} diagnostics`;
  const list = document.getElementById("projectEvolutionList");
  const documentHtml = documents.map(renderProjectEvolutionDocument).join("");
  const diagnosticHtml = diagnostics.map((item) => `<div class="projection-diagnostic">
    ${escapeHtml(item.code || "project_evolution_diagnostic")}: ${escapeHtml(item.message || "")}
  </div>`).join("");
  list.innerHTML = documentHtml || `<div class="empty">No project evolution Markdown imported</div>`;
  if (diagnosticHtml) list.innerHTML += diagnosticHtml;
}

function renderProjectEvolutionDocument(document) {
  return `<section class="flow-item project-evolution-document">
    <div class="item-title">
      <span>${escapeHtml(document.title || document.filename)}</span>
      <span class="status">human context only</span>
    </div>
    <div class="item-meta">
      ${compactMeta([
        ["file", document.filename],
        ["version", document.metadata?.version],
        ["declared status", document.metadata?.status],
        ["lines", document.lineCount],
      ])}
    </div>
    <p class="muted">This imported Markdown is separated from immutable run facts and does not prove implementation completion.</p>
    <div class="chip-row">
      ${(document.headings || []).map((heading) =>
        `<span class="chip">h${escapeHtml(heading.level)} ${escapeHtml(heading.text)}</span>`
      ).join("") || `<span class="chip review-chip">no headings declared</span>`}
    </div>
    ${(document.gateLanguage || []).length ? `<div class="context-block">
      <strong>Gate language found in human context</strong>
      ${(document.gateLanguage || []).map((line) => `<p class="item-meta">${escapeHtml(line)}</p>`).join("")}
    </div>` : ""}
  </section>`;
}

function renderProjectSelector() {
  const selector = globalThis.SpiroRunData?.ProjectSelectorProjection?.project(
    state.projectSnapshot,
    state.projectSelection
  );
  const container = document.getElementById("projectRunSelector");
  const count = document.getElementById("projectRunSelectorCount");
  if (!selector || !globalThis.SpiroRunData?.ProjectSelectorProjection) {
    container.innerHTML = `<div class="empty">Project store is unavailable</div>`;
    count.textContent = "No project loaded";
    return;
  }
  container.innerHTML = globalThis.SpiroRunData.ProjectSelectorProjection.render(selector);
  count.textContent = selector.projectId
    ? `${selector.projectId}: ${selector.runs.length} runs / ${selector.comparisons.length} comparisons`
    : "No project loaded";
}

function renderCandidateHistory() {
  const historyProjection = globalThis.SpiroRunData?.CandidateHistoryProjection?.project(
    state.projectSnapshot,
    state.projectSelection
  );
  const diagnosticsProjection = globalThis.SpiroRunData?.ProjectDiagnosticsProjection?.project(
    state.projectSnapshot
  );
  const historyList = document.getElementById("candidateHistoryList");
  const diagnosticsList = document.getElementById("projectDiagnosticsList");
  const count = document.getElementById("candidateHistoryCount");
  if (!historyProjection || !globalThis.SpiroRunData?.CandidateHistoryProjection) {
    historyList.innerHTML = `<div class="empty">Candidate history is unavailable</div>`;
    diagnosticsList.innerHTML = "";
    count.textContent = "No comparison selected";
    return;
  }
  historyList.innerHTML = globalThis.SpiroRunData.CandidateHistoryProjection.render(historyProjection);
  diagnosticsList.innerHTML = globalThis.SpiroRunData.ProjectDiagnosticsProjection?.render(diagnosticsProjection) || "";
  count.textContent = historyProjection.candidates.length
    ? `${historyProjection.candidates.length} candidate deltas`
    : "No candidate deltas";
}

function projectionSnapshotFromViewerState() {
  const artifacts = Object.create(null);
  const availability = Object.create(null);
  for (const metadata of state.manifest?.artifacts || []) {
    if (!metadata?.kind || !metadata.path || !state.artifacts.has(metadata.path)) continue;
    artifacts[metadata.kind] = {
      kind: metadata.kind,
      path: metadata.path,
      metadata,
      payload: state.artifacts.get(metadata.path),
    };
    availability[metadata.kind] = {kind: metadata.kind, path: metadata.path, status: "available"};
  }
  return {
    manifest: state.manifest,
    manifestMetadata: {
      runId: state.manifest?.run_id || null,
      schemaVersion: state.manifest?.schema_version || null,
      generatedAt: state.manifest?.generated_at || null,
    },
    artifacts,
    availability,
    diagnostics: [],
  };
}

function renderCandidateWorkspace() {
  if (!state.candidateProjection || !globalThis.SpiroCandidateProjection) {
    renderCandidateTracer(
      getKnownArtifact("screening_input_view"),
      getKnownArtifact("canonical_evidence")
    );
    return;
  }
  const projection = state.candidateProjection;
  const candidates = globalThis.SpiroCandidateProjection.query(
    projection,
    state.candidateControls
  );
  const table = document.getElementById("candidateTable");
  const detail = document.getElementById("candidateDetail");
  const groupLabels = {
    continue: "Continue",
    review: "Review",
    reject: "Reject",
    "insufficient-data": "Insufficient data",
  };
  document.getElementById("candidateGroups").innerHTML = globalThis.SpiroCandidateProjection.GROUPS
    .map((group) => `<div class="triage-group group-${escapeHtml(group)}">
      <strong>${escapeHtml(groupLabels[group])}</strong>
      <span>${projection.groups[group].length}</span>
    </div>`)
    .join("");
  document.getElementById("candidateDiagnostics").innerHTML = projection.diagnostics.length
    ? projection.diagnostics.map((item) => `<div class="projection-diagnostic">
        <strong>${escapeHtml(item.code)}</strong>
        ${escapeHtml(item.candidateId || "run")}: ${escapeHtml(item.message || "projection diagnostic")}
      </div>`).join("")
    : `<div class="muted">No projection diagnostics</div>`;

  if (!candidates.length) {
    state.selectedCandidateId = null;
    table.innerHTML = `<div class="empty">No candidates match the current controls</div>`;
    detail.innerHTML = `<div class="empty">Adjust search or status filters to inspect a candidate</div>`;
    document.getElementById("candidateCount").textContent = "0";
    document.getElementById("needsReviewCount").textContent = String(projection.groups.review.length);
    return;
  }
  if (!candidates.some((candidate) => candidate.candidateId === state.selectedCandidateId)) {
    state.selectedCandidateId = candidates[0].candidateId;
  }
  table.innerHTML = candidates.map((candidate) => `<button
      type="button"
      class="candidate-row candidate-${escapeHtml(candidate.group)}"
      data-candidate-id="${escapeHtml(candidate.candidateId)}"
      aria-pressed="${candidate.candidateId === state.selectedCandidateId}">
      <span>${escapeHtml(candidate.candidateId)}</span>
      <span class="gate-status gate-${escapeHtml(candidate.group)}">${escapeHtml(candidate.group)}</span>
    </button>`).join("");
  renderProjectedCandidateDetail(candidates.find(
    (candidate) => candidate.candidateId === state.selectedCandidateId
  ));
  document.getElementById("candidateCount").textContent = String(candidates.length);
  document.getElementById("needsReviewCount").textContent = String(projection.groups.review.length);
}

function renderProjectedCandidateDetail(candidate) {
  const detail = document.getElementById("candidateDetail");
  if (!candidate) {
    detail.innerHTML = `<div class="empty">No candidate selected</div>`;
    return;
  }
  if (!CANDIDATE_DETAIL_TABS.some((tab) => tab.id === state.selectedCandidateTab)) {
    state.selectedCandidateTab = "overview";
  }
  const activeTab = state.selectedCandidateTab;
  const panelId = `candidate-panel-${activeTab}`;
  const tabHtml = CANDIDATE_DETAIL_TABS.map((tab) => `<button
      id="candidate-tab-${escapeHtml(tab.id)}"
      class="candidate-detail-tab"
      type="button"
      role="tab"
      data-candidate-tab="${escapeHtml(tab.id)}"
      aria-selected="${tab.id === activeTab}"
      aria-controls="candidate-panel-${escapeHtml(tab.id)}"
      tabindex="${tab.id === activeTab ? "0" : "-1"}">${escapeHtml(tab.label)}</button>`)
    .join("");
  detail.innerHTML = `<section>
    <div class="item-title">
      <span>${escapeHtml(candidate.candidateId)}</span>
      <span class="status">${escapeHtml(candidate.group)}</span>
    </div>
    <div class="candidate-detail-tabs" role="tablist" aria-label="Candidate detail sections">
      ${tabHtml}
    </div>
    <div
      id="${escapeHtml(panelId)}"
      class="candidate-detail-panel"
      role="tabpanel"
      aria-labelledby="candidate-tab-${escapeHtml(activeTab)}">
      ${renderCandidateDetailTab(candidate, activeTab)}
    </div>
  </section>`;
}

function selectCandidateTab(tabId, options = {}) {
  if (!CANDIDATE_DETAIL_TABS.some((tab) => tab.id === tabId)) return;
  state.selectedCandidateTab = tabId;
  if (state.candidateProjection && globalThis.SpiroCandidateProjection) {
    renderCandidateWorkspace();
  }
  if (options.focus) {
    focusCandidateTab(tabId);
  }
}

function focusCandidateTab(tabId) {
  document.getElementById(`candidate-tab-${tabId}`)?.focus?.();
}

function renderCandidateDetailTab(candidate, tabId) {
  if (tabId === "explanation") return renderCandidateExplanationTab(candidate);
  if (tabId === "diagnostics") return renderCandidateDiagnosticsTab(candidate);
  if (tabId === "paper") return renderCandidatePaperEvidenceTab(candidate);
  return renderCandidateOverviewTab(candidate);
}

function renderCandidateOverviewTab(candidate) {
  const requests = candidate.recommendation?.requests || [];
  const events = candidate.lineage?.events || candidate.detail?.diagnostics?.lineageEvents || [];
  const coverage = candidate.evidenceCoverage || {};
  const availability = candidate.detail?.overview?.availability || [];
  return `
    <div class="item-meta">
      ${compactMeta([
        ["status", candidate.backendStatus],
        ["material", candidate.identity?.materialId],
        ["material_kind", candidate.identity?.materialKind],
        ["use_instance", candidate.identity?.useInstanceId],
        ["role", candidate.identity?.role],
        ["supplier", candidate.identity?.supplierStatus],
        ["profile", candidate.screening?.profileVersion],
        ["source", candidate.detail?.overview?.artifactKind],
      ])}
    </div>
    <div class="context-block">
      <strong>Blockers</strong>
      <div class="item-meta">
        blocker codes ${escapeHtml(String((candidate.blockers?.codes || []).length))} /
        blocking reviews ${escapeHtml(String((candidate.blockers?.reviewIds || []).length))}
      </div>
      <div class="chip-row">
        ${(candidate.blockers?.codes || []).map((code) => `<span class="chip review-chip">${escapeHtml(code)}</span>`).join("") || `<span class="muted">No declared blocker codes</span>`}
      </div>
      <div class="chip-row">
        ${(candidate.blockers?.reviewIds || []).map((reviewId) => `<span class="chip review-chip">${escapeHtml(reviewId)}</span>`).join("") || `<span class="muted">No blocking review IDs</span>`}
      </div>
    </div>
    <div class="context-block">
      <strong>Evidence coverage</strong>
      <div class="item-meta">evidence coverage ${escapeHtml(String(coverage.joined ?? 0))} / ${escapeHtml(String(coverage.declared ?? 0))}</div>
    </div>
    <div class="context-block">
      <strong>Lineage</strong>
      <div class="item-meta">lineage ${escapeHtml(candidate.lineage?.capability || "unavailable")}; ${events.length} explicit events</div>
    </div>
    <div class="context-block recommendation-context">
      <strong>Recommendation context</strong>
      <div class="item-meta">recommendation context only; never changes screening disposition</div>
      ${requests.map((request) => `<div class="chip">
        ${escapeHtml(request.request_id || "request")} score ${formatNumber(request.acquisition_score)}
      </div>`).join("") || `<div class="muted">No recommendation joined</div>`}
    </div>
    <div class="context-block">
      <strong>Availability summary</strong>
      <div class="chip-row">
        ${availability.map((item) => `<span class="chip">${escapeHtml(item.kind)} ${escapeHtml(item.status)}</span>`).join("") || `<span class="muted">No detail availability metadata</span>`}
      </div>
    </div>
    ${candidate.diagnostic ? `<div class="projection-diagnostic">
      <strong>Insufficient data</strong>
      source ${escapeHtml(candidate.diagnostic.source || "unknown")}: ${escapeHtml(candidate.diagnostic.reason || "unknown")}
    </div>` : ""}
  `;
}

function renderCandidateExplanationTab(candidate) {
  const explanation = candidate.detail?.explanation || {};
  const components = explanation.components || candidate.screening?.components || [];
  const evidence = explanation.eligibleScoringEvidence || [];
  const unavailable = explanation.unavailableEvidenceIds || candidate.evidenceCoverage?.missingEvidenceIds || [];
  const diagnostics = explanation.diagnostics || [];
  const acquisition = explanation.acquisition;
  return `
    <div class="context-block">
      <strong>Frozen screening components</strong>
      <div class="item-meta">backend output from screening_input_view; frontend does not recompute weighted utility</div>
      ${components.map((component) => `<div class="detail-row">
        <strong>${escapeHtml(component.name || "component")}</strong>
        <span>${compactMeta([
          ["source", component.artifactKind || "screening_input_view"],
          ["utility", formatNumber(component.utility)],
          ["quality", formatNumber(component.quality)],
          ["observed", component.observed === null || component.observed === undefined ? null : String(component.observed)],
          ["evidence", (component.evidenceIds || []).join(", ")],
        ])}</span>
      </div>`).join("") || `<div class="muted">No screening components joined</div>`}
    </div>
    <div class="context-block">
      <strong>ScoringView eligible evidence</strong>
      <div class="item-meta">Only policy-admitted scoring_view facts are described as eligible scoring evidence</div>
      ${evidence.map((fact) => `<div class="detail-row">
        <strong>${escapeHtml(fact.evidenceId || "evidence")}</strong>
        <span>${compactMeta([
          ["source", fact.artifactKind || "scoring_view"],
          ["property", fact.propertyName],
          ["value_ev", formatNumber(fact.valueEv)],
          ["unit", fact.unit],
          ["method", fact.method],
          ["reference", fact.referenceScale],
          ["trust", fact.quality?.trust_level],
          ["curation", fact.quality?.curation_status],
        ])}</span>
      </div>`).join("") || `<div class="muted">No eligible ScoringView facts joined for this candidate</div>`}
      ${unavailable.length ? `<div class="projection-diagnostic">
        <strong>Evidence not described as eligible</strong>
        ${unavailable.map((id) => `<span class="chip review-chip">${escapeHtml(id)}</span>`).join("")}
      </div>` : ""}
    </div>
    <div class="context-block">
      <strong>Acquisition context</strong>
      ${acquisition ? `<div class="item-meta">${compactMeta([
        ["source", acquisition.artifactKind],
        ["request", acquisition.requestId],
        ["model", acquisition.modelVersion],
        ["strategy", acquisition.strategy],
        ["model_score", formatNumber(acquisition.modelScore)],
        ["heuristic_score", formatNumber(acquisition.heuristicScore)],
        ["model_selected", acquisition.modelSelected === null || acquisition.modelSelected === undefined ? null : String(acquisition.modelSelected)],
      ])}</div>` : `<div class="muted">No acquisition breakdown joined</div>`}
    </div>
    ${renderProjectionDiagnostics(diagnostics)}
  `;
}

function renderCandidateDiagnosticsTab(candidate) {
  const diagnostics = candidate.detail?.diagnostics || {};
  const blockingReviews = diagnostics.blockingReviews || (candidate.blockers?.joinedReviews || []);
  const appliedEvents = diagnostics.appliedReviewEvents || [];
  const auditEvents = diagnostics.auditReviewEvents || [];
  const markers = diagnostics.recomputeMarkers || [];
  const artifactStatuses = diagnostics.artifactStatuses || [];
  const contradictions = diagnostics.contradictions || [];
  const reviewSummary = diagnostics.reviewSummary;
  return `
    <div class="context-block">
      <strong>Blocking reviews</strong>
      ${blockingReviews.map((review) => `<div class="detail-row">
        <strong>${escapeHtml(review.reviewItemId || review.review_item_id || "review")}</strong>
        <span>${compactMeta([
          ["source", review.artifactKind || "review_queue"],
          ["target_type", review.targetType || review.target_type],
          ["target_id", review.targetId || review.target_id],
          ["status", review.resolutionStatus || review.resolution_status],
          ["reason", review.reason || review.reason_code],
        ])}</span>
      </div>`).join("") || `<div class="muted">No joined blocking reviews</div>`}
    </div>
    <div class="context-block">
      <strong>Applied review events</strong>
      <div class="item-meta">Applied closure requires exact review_item_id, target_type, and target_id</div>
      ${appliedEvents.map((event) => `<div class="detail-row">
        <strong>${escapeHtml(event.eventId || "event")}</strong>
        <span>${compactMeta([
          ["source", event.artifactKind],
          ["review", event.reviewItemId],
          ["target_type", event.targetType],
          ["target_id", event.targetId],
          ["decision", event.decision],
          ["status", event.resolutionStatus],
        ])}</span>
      </div>`).join("") || `<div class="muted">No applied review events</div>`}
      ${auditEvents.length ? `<div class="projection-diagnostic">
        <strong>Wrong-target review events</strong>
        ${auditEvents.map((event) => `<span class="chip review-chip">${escapeHtml(event.eventId || event.reviewItemId || "event")}</span>`).join("")}
      </div>` : ""}
    </div>
    <div class="context-block">
      <strong>Observed immutable recompute markers</strong>
      <div class="item-meta">Viewer displays recompute markers as artifacts only; it cannot execute recompute</div>
      ${markers.map((marker) => `<div class="detail-row">
        <strong>${escapeHtml(marker.markerId || "marker")}</strong>
        <span>${compactMeta([
          ["source", marker.artifactKind],
          ["event", marker.reviewEventId],
          ["review", marker.reviewItemId],
          ["target_type", marker.targetType],
          ["target_id", marker.targetId],
          ["status", marker.status],
          ["affected", (marker.affectedArtifacts || []).join(", ")],
        ])}</span>
      </div>`).join("") || `<div class="muted">No recompute markers observed for this candidate</div>`}
    </div>
    <div class="context-block">
      <strong>Review summary</strong>
      ${reviewSummary ? `<div class="item-meta">${compactMeta([
        ["source", reviewSummary.artifactKind],
        ["reviews", reviewSummary.reviewCount],
        ["events", reviewSummary.eventCount],
        ["applied", reviewSummary.appliedEventCount],
        ["open_blocking", reviewSummary.openBlockingCount],
      ])}</div>` : `<div class="muted">No review summary artifact joined</div>`}
    </div>
    <div class="context-block">
      <strong>Artifact/schema status</strong>
      <div class="chip-row">
        ${artifactStatuses.map((item) => `<span class="chip">${escapeHtml(item.kind)} ${escapeHtml(item.status || "unknown")}</span>`).join("") || `<span class="muted">No artifact status metadata</span>`}
      </div>
    </div>
    ${renderProjectionDiagnostics(contradictions)}
  `;
}

function renderCandidatePaperEvidenceTab(candidate) {
  const paper = candidate.detail?.paperEvidence || {
    status: "unavailable",
    message: "No explicit backend candidate-to-paper join; literature is available only at run/DOI scope.",
    records: [],
    runArtifacts: [],
    diagnostics: [],
  };
  return `
    <div class="context-block">
      <strong>Paper Evidence</strong>
      <div class="item-meta">status ${escapeHtml(paper.status || "unavailable")}</div>
      <p>${escapeHtml(paper.message || "No explicit backend candidate-to-paper join; literature is available only at run/DOI scope.")}</p>
      ${(paper.records || []).map((record) => `<div class="detail-row">
        <strong>${escapeHtml(record.evidenceId || record.claim_id || record.asset_id || record.doi || "paper-record")}</strong>
        <span>${compactMeta([
          ["source", record.artifactKind || "candidate_paper_evidence"],
          ["doi", record.doi],
          ["source_id", record.sourceId],
          ["title", record.title],
          ["asset", record.asset_id],
          ["chunk", record.chunk_id],
          ["reviewer_state", record.reviewerState],
          ["confidence", record.confidenceCategory],
        ])}</span>
      </div>`).join("")}
    </div>
    ${renderProjectionDiagnostics(paper.diagnostics || [])}
    <div class="context-block">
      <strong>Run/DOI-scope literature artifacts</strong>
      <div class="chip-row">
        ${(paper.runArtifacts || []).map((item) => `<span class="chip">${escapeHtml(item.kind)} ${escapeHtml(item.status || "unknown")}</span>`).join("") || `<span class="muted">No run-level paper artifacts declared</span>`}
      </div>
    </div>
  `;
}

function renderProjectionDiagnostics(items) {
  const diagnostics = items || [];
  if (!diagnostics.length) return "";
  return `<div class="context-block">
    <strong>Detail diagnostics</strong>
    ${diagnostics.map((item) => `<div class="projection-diagnostic">
      <strong>${escapeHtml(item.code || "diagnostic")}</strong>
      ${compactMeta([
        ["source", item.source],
        ["candidate", item.candidateId],
        ["evidence", item.evidenceId],
        ["review", item.reviewItemId],
      ])}
      ${escapeHtml(item.message || "")}
    </div>`).join("")}
  </div>`;
}

function renderRunCompatibilityDiagnostics(compatibility) {
  if (!compatibility) {
    return `<div class="empty">No run compatibility loaded</div>`;
  }
  const dimensions = Array.isArray(compatibility.dimensions) ? compatibility.dimensions : [];
  const reasonCodes = Array.isArray(compatibility.reason_codes) ? compatibility.reason_codes : [];
  const rows = dimensions.map((dimension) => {
    const codes = Array.isArray(dimension.reason_codes) ? dimension.reason_codes : [];
    const label = dimension.status === "non_comparable" ? "non-comparable raw values only" : "comparable";
    return `<tr>
      <td>${escapeHtml(dimension.dimension || "-")}</td>
      <td>${escapeHtml(dimension.status || "-")}</td>
      <td>${escapeHtml(label)}</td>
      <td>${escapeHtml(codes.join(", ") || "-")}</td>
    </tr>`;
  }).join("");
  return `<section class="panel compatibility-panel">
    <h3>Run Compatibility</h3>
    <p>Status: <strong>${escapeHtml(compatibility.status || "unknown")}</strong></p>
    <p>Reason codes: ${escapeHtml(reasonCodes.join(", ") || "-")}</p>
    <table>
      <thead><tr><th>Dimension</th><th>Status</th><th>Display rule</th><th>Codes</th></tr></thead>
      <tbody>${rows || `<tr><td colspan="4">No dimensions declared</td></tr>`}</tbody>
    </table>
  </section>`;
}

globalThis.renderRunCompatibilityDiagnostics = renderRunCompatibilityDiagnostics;

function getKnownArtifact(kind) {
  return getArtifact(kind);
}

function getArtifact(kind) {
  const artifact = (state.manifest?.artifacts || []).find((item) => item.kind === kind);
  if (!artifact?.path) return null;
  return state.artifacts.get(artifact.path) || null;
}

function screeningStatusDisplay(value) {
  if (value === "pass" || value === "defer" || value === "reject") {
    return {status: value, reason: "Evidence eligibility status"};
  }
  const missing = value === undefined || value === null ||
    (typeof value === "string" && !value.trim());
  return {
    status: "unavailable",
    reason: missing
      ? "Screening status was not provided"
      : `Unsupported screening status: ${String(value)}`,
  };
}

function renderScreeningStatusBadge(value) {
  const display = screeningStatusDisplay(value);
  return `<span class="gate-status gate-${escapeHtml(display.status)}" title="${escapeHtml(display.reason)}">${escapeHtml(display.status)}</span>`;
}

function renderCandidateTracer(screeningInputView, canonicalEvidence) {
  const table = document.getElementById("candidateTable");
  const candidates = screeningInputView?.candidates || [];
  const canonicalByCandidate = new Map(
    (canonicalEvidence?.records || []).map((record) => [record.candidate_id, record])
  );
  if (!candidates.length) {
    state.selectedCandidateId = null;
    table.innerHTML = `<div class="empty">No candidates loaded</div>`;
    document.getElementById("candidateDetail").innerHTML =
      `<div class="empty">Select a coherent run bundle to inspect a candidate</div>`;
    return;
  }

  if (!candidates.some((candidate) => candidate.candidate_id === state.selectedCandidateId)) {
    state.selectedCandidateId = candidates[0].candidate_id;
  }
  table.innerHTML = candidates
    .map((candidate) => `<button
      type="button"
      class="candidate-row"
      data-candidate-id="${escapeHtml(candidate.candidate_id || "")}"
      aria-pressed="${candidate.candidate_id === state.selectedCandidateId}">
      <span>${escapeHtml(candidate.candidate_id || "-")}</span>
      ${renderScreeningStatusBadge(candidate.status)}
    </button>`)
    .join("");

  const selected = candidates.find(
    (candidate) => candidate.candidate_id === state.selectedCandidateId
  );
  renderCandidateDetail(selected, canonicalByCandidate.get(state.selectedCandidateId));
  document.getElementById("candidateCount").textContent = String(candidates.length);
  document.getElementById("needsReviewCount").textContent = String(
    candidates.filter((candidate) => screeningStatusDisplay(candidate.status).status === "defer").length
  );
}

function renderCandidateDetail(candidate, canonicalRecord) {
  const detail = document.getElementById("candidateDetail");
  if (!candidate) {
    detail.innerHTML = `<div class="empty">No candidate selected</div>`;
    return;
  }
  const material = canonicalRecord?.material || {};
  const useInstance = canonicalRecord?.use_instance || {};
  const energyEvidence = canonicalRecord?.energy_evidence || [];
  const statusDisplay = screeningStatusDisplay(candidate.status);
  detail.innerHTML = `<section>
    <div class="item-title">
      <span>${escapeHtml(candidate.candidate_id || "-")}</span>
      <span class="status">${escapeHtml(material.material_kind || "canonical evidence unavailable")}</span>
    </div>
    <div class="item-meta">
      ${compactMeta([
        ["status", statusDisplay.status],
        ["status_reason", statusDisplay.status === "unavailable" ? statusDisplay.reason : null],
        ["utility", formatNumber(candidate.weighted_utility)],
        ["coverage", formatNumber(candidate.coverage)],
        ["profile", candidate.profile_version],
        ["use", useInstance.role],
        ["supplier", material.supplier_status],
      ])}
    </div>
    <div class="chip-row">
      ${energyEvidence.map(renderEnergyEvidenceChip).join("") || `<span class="chip muted">no energy evidence</span>`}
    </div>
    <div class="review-inline">
      ${(candidate.codes || []).map((code) => `<span class="chip review-chip">${escapeHtml(code)}</span>`).join("") || `<span class="muted">No blocking codes</span>`}
    </div>
  </section>`;
}

function renderRecommendations(recommendations) {
  const list = document.getElementById("recommendationList");
  const requests = recommendations?.requests || [];
  document.getElementById("recommendationCount").textContent = String(requests.length);
  document.getElementById("totalEstimatedCost").textContent =
    recommendations?.total_estimated_cost === undefined
      ? "-"
      : `cost ${formatNumber(recommendations.total_estimated_cost)}`;
  if (!requests.length) {
    list.innerHTML = `<li class="empty">No recommendations loaded</li>`;
    return;
  }
  list.innerHTML = requests
    .map((request) => `<li>
      <div class="item-title">
        <span>${escapeHtml(request.candidate_id)}</span>
        <span class="score">${formatNumber(request.acquisition_score)}</span>
      </div>
      <div class="item-meta">
        ${escapeHtml(request.request_id)}<br>
        estimated cost ${formatNumber(request.estimated_cost)}
      </div>
    </li>`)
    .join("");
}

function renderTimeline(trace) {
  const timeline = document.getElementById("timeline");
  document.getElementById("traceCount").textContent = `${trace.length} events`;
  if (!trace.length) {
    timeline.innerHTML = `<div class="empty">No trace loaded</div>`;
    return;
  }
  timeline.innerHTML = trace
    .map((event) => `<div class="timeline-item">
      <div class="item-title">
        <span>${escapeHtml(event.event_type || "event")}</span>
        <span>${escapeHtml(event.actor || "-")}</span>
      </div>
      <div class="item-meta">
        candidates ${safeCount(event.candidate_count)} / recommended ${safeCount(event.recommended_count)} / observations ${safeCount(event.observation_count)}<br>
        ${compactMeta([
          ["candidate", event.candidate_id],
          ["provider", event.provider],
          ["cache", event.cache_status],
          ["outcome", event.outcome],
          ["event", shortId(event.event_id)],
          ["lookup", shortId(event.lookup_id)],
          ["response", shortId(event.response_id)],
          ["reason", event.reason],
        ])}
      </div>
    </div>`)
    .join("");
}

function renderEnrichmentFlow(enrichment, cacheIndex, reviewQueue, trace) {
  const container = document.getElementById("candidateFlow");
  const records = enrichment?.records || [];
  const cacheEntries = cacheIndex?.entries || [];
  const traceById = new Map((trace || []).map((event) => [event.event_id, event]));
  const reviewsById = new Map((reviewQueue || []).map((item) => [item.review_item_id, item]));
  const reviewsByTarget = groupBy(reviewQueue || [], (item) => item.target_id);
  const cacheByCandidate = groupBy(cacheEntries, (entry) => entry.candidate_id);
  document.getElementById("cacheSummary").textContent = cacheIndex
    ? `hit ${safeCount(cacheIndex.hit_count)} / miss ${safeCount(cacheIndex.miss_count)} / failed ${safeCount(cacheIndex.failure_count)}`
    : "No cache data";
  if (enrichment) {
    document.getElementById("candidateCount").textContent = String(records.length);
    document.getElementById("needsReviewCount").textContent = String(records.filter((record) => record.status === "needs_review").length);
  }
  if (!records.length) {
    container.innerHTML = `<div class="empty">No enrichment results loaded</div>`;
    return;
  }
  container.innerHTML = records
    .map((record) => {
      const entries = cacheByCandidate.get(record.candidate_id) || [];
      const reviews = reviewsForRecord(record, reviewsById, reviewsByTarget);
      return `<section class="flow-item">
        <div class="item-title">
          <span>${escapeHtml(record.candidate_id || "-")}</span>
          <span class="status">${escapeHtml(record.status || "-")}</span>
        </div>
        <div class="item-meta">${escapeHtml(record.name || "")}${record.missing_fields?.length ? `<br>missing ${escapeHtml(record.missing_fields.join(", "))}` : ""}</div>
        <div class="chip-row">
          ${entries.map((entry) => renderCacheChip(entry, traceById.get(entry.trace_event_id))).join("") || `<span class="chip muted">local only</span>`}
        </div>
        <div class="review-inline">
          ${reviews.map((item) => renderReviewChip(item, traceById.get(item.trace_event_id))).join("") || `<span class="muted">No review items</span>`}
        </div>
      </section>`;
    })
    .join("");
}

function reviewsForRecord(record, reviewsById, reviewsByTarget) {
  const matched = (record.review_item_ids || [])
    .map((reviewId) => reviewsById.get(reviewId))
    .filter(Boolean);
  if (matched.length) {
    return matched;
  }
  return reviewsByTarget.get(record.candidate_id) || [];
}

function renderReviewQueue(reviewQueue) {
  const list = document.getElementById("reviewQueueList");
  document.getElementById("reviewQueueCount").textContent = `${reviewQueue.length} items`;
  if (!reviewQueue.length) {
    list.innerHTML = `<div class="empty">No review queue loaded</div>`;
    return;
  }
  list.innerHTML = reviewQueue
    .map((item) => `<div class="review-item">
      <div class="item-title">
        <span>${escapeHtml(item.reason || "review")}</span>
        <span>${escapeHtml(item.severity || "-")}</span>
      </div>
      <div class="item-meta">
        ${compactMeta([
          ["candidate_id", item.target_id],
          ["provider", item.provider],
          ["cache_status", item.cache_status],
          ["field", item.field],
          ["review_item_id", shortId(item.review_item_id)],
          ["trace_event_id", shortId(item.trace_event_id)],
          ["lookup_id", shortId(item.lookup_id)],
          ["response_id", shortId(item.response_id)],
          ["raw_hash", shortId(item.raw_hash)],
        ])}
      </div>
    </div>`)
    .join("");
}

function renderCanonicalEvidence(canonicalEvidence) {
  const list = document.getElementById("canonicalEvidenceList");
  const records = canonicalEvidence?.records || [];
  document.getElementById("canonicalEvidenceCount").textContent = `${records.length} records`;
  if (!records.length) {
    list.innerHTML = `<div class="empty">No canonical evidence loaded</div>`;
    return;
  }
  list.innerHTML = records
    .map((record) => {
      const material = record.material || {};
      const useInstance = record.use_instance || {};
      const energyEvidence = record.energy_evidence || [];
      const reviewItems = record.review_items || [];
      return `<section class="flow-item">
        <div class="item-title">
          <span>${escapeHtml(record.candidate_id || material.material_id || "-")}</span>
          <span class="status">${escapeHtml(material.material_kind || "-")}</span>
        </div>
        <div class="item-meta">
          ${compactMeta([
            ["supplier", material.supplier_status],
            ["synthesis", material.synthesis_readiness],
            ["use", useInstance.role],
            ["profile", useInstance.profile],
            ["target", useInstance.target_stack],
          ])}
        </div>
        <div class="chip-row">
          ${energyEvidence.map(renderEnergyEvidenceChip).join("") || `<span class="chip muted">no energy evidence</span>`}
        </div>
        <div class="review-inline">
          ${reviewItems.map(renderCanonicalReviewChip).join("") || `<span class="muted">No canonical review items</span>`}
        </div>
      </section>`;
    })
    .join("");
}

function renderScoringView(scoringView) {
  const list = document.getElementById("scoringViewList");
  const facts = scoringView?.energy_facts || [];
  document.getElementById("scoringFactCount").textContent = `${facts.length} facts`;
  if (!facts.length) {
    list.innerHTML = `<div class="empty">No scoring view loaded</div>`;
    return;
  }
  list.innerHTML = facts
    .map((fact) => {
      const quality = fact.quality || {};
      return `<section class="flow-item">
        <div class="item-title">
          <span>${escapeHtml(fact.material_id || "-")}</span>
          <span class="status">${escapeHtml(fact.property_name || "-")} ${escapeHtml(formatNumber(fact.value_ev))} ${escapeHtml(fact.unit || "")}</span>
        </div>
        <div class="item-meta">
          ${compactMeta([
            ["use", fact.use_instance_id],
            ["method", fact.method],
            ["scale", fact.reference_scale],
            ["computed", fact.computed],
          ])}
        </div>
        <div class="chip-row">
          ${renderScoringQualityChip(fact)}
          <span class="chip" title="${escapeHtml(fact.evidence_id || "")}">evidence ${escapeHtml(shortId(fact.evidence_id))}</span>
        </div>
      </section>`;
    })
    .join("");
}

function renderScreeningEligibility(screeningInputView) {
  const list = document.getElementById("screeningEligibilityList");
  const candidates = screeningInputView?.candidates || [];
  document.getElementById("screeningEligibilityCount").textContent = `${candidates.length} candidates`;
  if (!candidates.length) {
    list.innerHTML = `<div class="empty">No screening input view loaded</div>`;
    return;
  }
  list.innerHTML = candidates
    .map((candidate) => `<section class="flow-item">
      <div class="item-title">
        <span>${escapeHtml(candidate.candidate_id || "-")}</span>
        ${renderScreeningStatusBadge(candidate.status)}
      </div>
      <div class="item-meta">
        ${compactMeta([
          ["utility", formatNumber(candidate.weighted_utility)],
          ["coverage", formatNumber(candidate.coverage)],
          ["profile", candidate.profile_version || screeningInputView.profile_version],
        ])}
      </div>
      <div class="chip-row">
        ${(candidate.codes || []).map((code) => `<span class="chip review-chip">${escapeHtml(code)}</span>`).join("") || `<span class="chip muted">no blocking codes</span>`}
      </div>
    </section>`)
    .join("");
}

function renderModelEvaluation(modelEvaluation) {
  const list = document.getElementById("modelEvaluationList");
  const status = modelEvaluation?.activation_status || "unavailable";
  document.getElementById("modelActivationStatus").textContent = status;
  if (!modelEvaluation) {
    list.innerHTML = `<div class="empty">No model evaluation loaded</div>`;
    return;
  }
  const metrics = modelEvaluation.metrics || {};
  const dummy = modelEvaluation.baselines?.dummy || {};
  const heuristic = modelEvaluation.baselines?.heuristic || {};
  const calibration = modelEvaluation.calibration || {};
  list.innerHTML = `<section class="flow-item">
    <div class="item-title">
      <span>${escapeHtml(modelEvaluation.model_version || "-")}</span>
      <span class="gate-status gate-${escapeHtml(status)}" title="Model activation gate">${escapeHtml(status)}</span>
    </div>
    <div class="item-meta">
      ${compactMeta([
        ["model", modelEvaluation.surrogate_type],
        ["objective", modelEvaluation.objective_name],
        ["rmse", formatNumber(metrics.rmse)],
        ["dummy_rmse", formatNumber(dummy.rmse)],
        ["heuristic_rmse", formatNumber(heuristic.rmse)],
        ["coverage_95", formatNumber(calibration.coverage_95)],
        ["replay", modelEvaluation.replay_status],
        ["folds", (modelEvaluation.folds || []).length],
      ])}
    </div>
    <div class="chip-row">
      ${(modelEvaluation.activation_reasons || []).map((reason) => `<span class="chip review-chip">${escapeHtml(reason)}</span>`).join("") || `<span class="chip">all activation gates passed</span>`}
    </div>
  </section>`;
}

function renderReviewClosure(reviewEvents, reviewSummary, recomputeMarkers) {
  const list = document.getElementById("reviewClosureList");
  const events = reviewEvents || [];
  const markers = recomputeMarkers || [];
  document.getElementById("reviewClosureCount").textContent = `${events.length} events / ${markers.length} markers`;
  if (!events.length && !markers.length && !reviewSummary) {
    list.innerHTML = `<div class="empty">No review closure loaded</div>`;
    return;
  }

  const markerIdsByEvent = groupBy(markers, (marker) => marker.review_event_id);
  const summaryHtml = reviewSummary ? renderReviewSummary(reviewSummary) : "";
  const eventHtml = events.map((event) => renderReviewEvent(event, markerIdsByEvent.get(event.event_id) || [])).join("");
  const markerHtml = markers.map(renderRecomputeMarker).join("");
  list.innerHTML = [summaryHtml, eventHtml, markerHtml].filter(Boolean).join("");
}

function renderPaperDiagnostics(
  sourceAssets,
  literatureClaims,
  paperVaultSummary,
  paperCrossRefReport,
  obsidianNotes
) {
  const list = document.getElementById("paperDiagnosticsList");
  const assets = Array.isArray(sourceAssets) ? sourceAssets : [];
  const claims = Array.isArray(literatureClaims) ? literatureClaims : [];
  document.getElementById("paperDiagnosticsCount").textContent =
    `${assets.length} source assets / ${claims.length} claims`;

  const contextSections = [
    renderPaperContext("paper vault summary", paperVaultSummary),
    renderPaperContext("paper cross-ref report", paperCrossRefReport),
    renderPaperContext("obsidian notes", obsidianNotes),
  ].filter(Boolean);

  const sections = [
    ...assets.map(renderPaperSourceAsset),
    ...claims.map(renderLiteratureClaim),
    ...contextSections,
    renderCandidatePaperUnavailableNotice(),
  ];

  if (!assets.length && !claims.length && !contextSections.length) {
    list.innerHTML = `<div class="empty">No paper diagnostics loaded</div>${renderCandidatePaperUnavailableNotice()}`;
    return;
  }
  list.innerHTML = sections.join("");
}

function renderPaperSourceAsset(asset) {
  const hashes = [
    asset.sha256,
    asset.content_sha256,
    asset.raw_hash,
    asset.source_hash,
  ].filter(Boolean);
  return `<section class="flow-item">
    <div class="item-title">
      <span>${escapeHtml(asset.asset_id || asset.source_asset_id || "source asset")}</span>
      <span class="status">source asset</span>
    </div>
    <div class="item-meta">
      ${compactMeta([
        ["doi", asset.doi],
        ["chunk", asset.chunk_id],
        ["license", asset.license || asset.rights_license],
        ["rights", asset.rights || asset.rights_status],
        ["hash", hashes.join(", ")],
        ["path", asset.path || asset.file_path],
        ["url", asset.url || asset.source_url],
      ])}
    </div>
  </section>`;
}

function renderLiteratureClaim(claim) {
  const reviewLabel = claim.review_required || claim.requires_review ? "review required" : "";
  const lineage = claim.lineage ? stableJson(claim.lineage) : "";
  return `<section class="flow-item">
    <div class="item-title">
      <span>${escapeHtml(claim.claim_id || "literature claim")}</span>
      <span class="status">claim</span>
    </div>
    <div class="item-meta">
      ${compactMeta([
        ["asset", claim.asset_id || claim.source_asset_id],
        ["chunk", claim.chunk_id],
        ["doi", claim.doi],
        ["property", claim.property_name || claim.property],
        ["value", claim.value],
        ["unit", claim.unit],
        ["confidence", claim.confidence],
        ["review", reviewLabel],
        ["lineage", lineage],
      ])}
    </div>
    ${renderClaimSpan(claim)}
  </section>`;
}

function renderClaimSpan(claim) {
  const span = claim.text_span || claim.extracted_span || claim.excerpt || claim.text;
  if (!span) return "";
  return `<p>${escapeHtml(span)}</p>`;
}

function renderPaperContext(title, payload) {
  if (!payload) return "";
  return `<section class="flow-item">
    <div class="item-title">
      <span>${escapeHtml(title)}</span>
      <span class="status">internal diagnostic context</span>
    </div>
    <pre>${escapeHtml(stableJson(payload))}</pre>
  </section>`;
}

function renderCandidatePaperUnavailableNotice() {
  return `<section class="flow-item">
    <div class="item-title">
      <span>candidate paper tab remains unavailable</span>
      <span class="status">fail closed</span>
    </div>
    <p>No backend candidate-to-paper join artifact is loaded for this run.</p>
  </section>`;
}

function renderReviewSummary(summary) {
  const resolutionCounts = summary.by_resolution_status || {};
  const reasonCounts = summary.by_reason_code || {};
  const queueCounts = summary.by_assigned_queue || {};
  return `<section class="flow-item">
    <div class="item-title">
      <span>review summary</span>
      <span class="status">${escapeHtml(safeCount(summary.applied_event_count))} applied</span>
    </div>
    <div class="item-meta">
      ${compactMeta([
        ["run", shortId(summary.run_id)],
        ["generated", summary.generated_at],
        ["review_count", summary.review_count],
        ["event_count", summary.event_count],
        ["open_blocking", summary.open_blocking_count],
        ["resolved", summary.resolved_count],
        ["rejected", summary.rejected_count],
      ])}
    </div>
    <div class="chip-row">
      ${renderCountMapChips("status", resolutionCounts)}
      ${renderCountMapChips("reason", reasonCounts)}
      ${renderCountMapChips("queue", queueCounts)}
    </div>
  </section>`;
}

function renderReviewEvent(event, markers) {
  return `<section class="flow-item">
    <div class="item-title">
      <span>${escapeHtml(event.event_type || "review event")}</span>
      <span class="status">${escapeHtml(event.resolution_status || "-")}</span>
    </div>
    <div class="item-meta">
      ${compactMeta([
        ["event", shortId(event.event_id)],
        ["review", shortId(event.review_item_id)],
        ["target_type", event.target_type],
        ["target_id", event.target_id],
        ["reviewer", reviewerLabel(event.reviewer)],
        ["decision", event.decision],
        ["reason", event.reason],
      ])}
    </div>
    <div class="chip-row">
      ${(markers.length ? markers : event.recompute_marker_ids || [])
        .map((marker) => `<span class="chip review-chip">marker ${escapeHtml(shortId(marker.marker_id || marker))}</span>`)
        .join("") || `<span class="chip muted">no recompute marker</span>`}
    </div>
  </section>`;
}

function renderRecomputeMarker(marker) {
  return `<section class="flow-item">
    <div class="item-title">
      <span>recompute marker</span>
      <span class="status">${escapeHtml(marker.status || "-")}</span>
    </div>
    <div class="item-meta">
      ${compactMeta([
        ["marker", shortId(marker.marker_id)],
        ["event", shortId(marker.review_event_id)],
        ["review", shortId(marker.review_item_id)],
        ["candidate", marker.candidate_id],
        ["target_type", marker.target_type],
        ["target_id", marker.target_id],
        ["reason", marker.reason],
      ])}
    </div>
    <div class="chip-row">
      ${(marker.affected_artifacts || [])
        .map((artifact) => `<span class="chip">${escapeHtml(artifact)}</span>`)
        .join("") || `<span class="chip muted">no affected artifacts</span>`}
    </div>
  </section>`;
}

function renderCountMapChips(label, counts) {
  return Object.entries(counts || {})
    .map(([key, value]) => `<span class="chip">${escapeHtml(label)} ${escapeHtml(key)} ${escapeHtml(value)}</span>`)
    .join("");
}

function renderScoringQualityChip(fact) {
  const quality = fact.quality || {};
  const blocked = quality.eligible_for_scoring === false || Number(quality.blocking_review_count || 0) > 0;
  const className = blocked ? "chip review-chip" : "chip";
  return `<span class="${className}">
    quality ${escapeHtml(formatNumber(quality.quality_score))}
    <small>${compactMeta([
      ["trust", quality.trust_level],
      ["curation", quality.curation_status],
      ["eligible", quality.eligible_for_scoring],
      ["blocks", quality.blocking_review_count],
    ])}</small>
  </span>`;
}

function renderEnergyEvidenceChip(item) {
  const provenance = item.provenance || {};
  const eligibility = item.eligible_for_scoring ? "eligible" : "not eligible";
  return `<span class="chip" title="${escapeHtml(item.energy_evidence_id || "")}">
    ${escapeHtml(item.property_name || "-")} ${escapeHtml(formatNumber(item.value_ev))} ${escapeHtml(item.unit || "")}
    <small>${escapeHtml(eligibility)} / ${escapeHtml(provenance.provider_name || "-")} / ${escapeHtml(provenance.trust_level || "-")}</small>
  </span>`;
}

function renderCanonicalReviewChip(item) {
  return `<span class="chip review-chip">
    ${escapeHtml(item.reason_code || "review")}
    <small>${compactMeta([
      ["severity", item.severity],
      ["queue", item.assigned_queue],
      ["surface", item.blocking_surface],
    ])}</small>
  </span>`;
}

function renderCacheChip(entry, event) {
  return `<span class="chip" title="${escapeHtml(entry.cache_key || "")}">
    ${escapeHtml(entry.provider || "-")} ${escapeHtml(entry.cache_status || "-")}
    ${entry.outcome ? escapeHtml(entry.outcome) : escapeHtml(event?.outcome || "")}
    <small>${escapeHtml(shortId(entry.cache_key))} ${escapeHtml(shortId(entry.raw_hash))}</small>
  </span>`;
}

function renderReviewChip(item, event) {
  return `<span class="chip review-chip">
    ${escapeHtml(item.reason || "review")}
    <small>${compactMeta([
      ["provider", item.provider],
      ["cache", item.cache_status],
      ["outcome", event?.outcome],
      ["trace", shortId(item.trace_event_id)],
      ["lookup", shortId(item.lookup_id)],
      ["response", shortId(item.response_id)],
      ["review", shortId(item.review_item_id)],
    ])}</small>
  </span>`;
}

function groupBy(items, keyFn) {
  const grouped = new Map();
  for (const item of items || []) {
    const key = keyFn(item) || "";
    if (!grouped.has(key)) grouped.set(key, []);
    grouped.get(key).push(item);
  }
  return grouped;
}

function compactMeta(pairs) {
  return pairs
    .filter(([, value]) => value !== undefined && value !== null && value !== "")
    .map(([label, value]) => `${escapeHtml(label)} ${escapeHtml(value)}`)
    .join(" / ");
}

function stableJson(value) {
  try {
    return JSON.stringify(value);
  } catch (error) {
    return String(value);
  }
}

function shortId(value) {
  if (!value) return "";
  return String(value).slice(0, 12);
}

function formatNumber(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return number.toFixed(3).replace(/\.?0+$/, "");
}

function reviewerLabel(value) {
  if (!value) return "";
  return "human reviewer";
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function safeCount(value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return "-";
  return escapeHtml(String(number));
}

function showError(message) {
  const errorState = document.getElementById("errorState");
  errorState.textContent = message;
  errorState.style.display = "block";
}

function clearError() {
  const errorState = document.getElementById("errorState");
  errorState.textContent = "";
  errorState.style.display = "none";
}

document.getElementById("runSummary").textContent = "No run loaded";
document.getElementById("loadState").textContent = "Waiting for bundle";
renderRecommendations(null);
renderTimeline([]);
renderEnrichmentFlow(null, null, [], []);
renderCanonicalEvidence(null);
renderScoringView(null);
renderScreeningEligibility(null);
renderModelEvaluation(null);
renderReviewClosure([], null, []);
renderPaperDiagnostics([], [], null, null, null);
renderProjectEvolution();
renderProjectSelector();
renderCandidateHistory();
renderReviewQueue([]);
renderCandidateTracer(null, null);
