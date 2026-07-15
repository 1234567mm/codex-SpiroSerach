const state = {
  manifest: null,
  artifacts: new Map(),
  snapshot: null,
  selectedCandidateId: null,
};

const runDataStore = globalThis.SpiroRunData
  ? new globalThis.SpiroRunData.RunDataStore()
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

document.getElementById("candidateTable").addEventListener("click", (event) => {
  const row = event.target.closest?.("[data-candidate-id]");
  if (!row) return;
  state.selectedCandidateId = row.dataset.candidateId;
  renderCandidateTracer(
    getKnownArtifact("screening_input_view"),
    getKnownArtifact("canonical_evidence")
  );
});

function applyCommittedSnapshot(snapshot) {
  state.snapshot = snapshot;
  state.manifest = snapshot.manifest;
  state.artifacts = new Map(
    Object.values(snapshot.artifacts).map((artifact) => [artifact.path, artifact.payload])
  );
  state.selectedCandidateId = null;
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
  renderReviewQueue(reviewQueue);
  renderCandidateTracer(screeningInputView, canonicalEvidence);
}

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
renderReviewQueue([]);
renderCandidateTracer(null, null);
