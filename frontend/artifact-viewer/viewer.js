const state = {
  manifest: null,
  artifacts: new Map(),
};

document.getElementById("manifestFile").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    clearError();
    state.manifest = JSON.parse(await file.text());
    renderManifest(state.manifest);
    renderKnownArtifacts();
  } catch (error) {
    showError(`manifest ${error.message}`);
  }
});

document.getElementById("artifactFiles").addEventListener("change", async (event) => {
  try {
    clearError();
    state.artifacts.clear();
    for (const file of event.target.files) {
      const text = await file.text();
      const artifactName = file.webkitRelativePath || file.name;
      const parsed = parseArtifact(artifactName, text);
      state.artifacts.set(artifactName, parsed);
      if (artifactName !== file.name && !state.artifacts.has(file.name)) {
        state.artifacts.set(file.name, parsed);
      }
    }
    renderKnownArtifacts();
  } catch (error) {
    showError(error.message);
  }
});

function parseArtifact(name, text) {
  if (name.endsWith(".jsonl")) {
    return parseJsonl(text, name);
  }
  try {
    return JSON.parse(text);
  } catch (error) {
    throw new Error(`${name} JSON parse failed: ${error.message}`);
  }
}

function parseJsonl(text, name = "jsonl") {
  const records = [];
  const lines = text.split(/\r?\n/);
  lines.forEach((line, index) => {
    const trimmed = line.trim();
    if (!trimmed) return;
    try {
      records.push(JSON.parse(trimmed));
    } catch (error) {
      throw new Error(`${name} line ${index + 1}: ${error.message}`);
    }
  });
  return records;
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
    return `<tr>
      <td>${escapeHtml(artifact.kind || "-")}</td>
      <td>${escapeHtml(artifact.path || "-")}</td>
      <td>${escapeHtml(String(artifact.bytes ?? "-"))}</td>
      <td>${escapeHtml(hash)}</td>
    </tr>`;
  });
  document.getElementById("artifactTable").innerHTML = rows.join("") || `<tr><td colspan="4">No artifacts</td></tr>`;
  document.getElementById("loadState").textContent = state.artifacts.size
    ? `${state.artifacts.size} files loaded`
    : "Manifest loaded";
}

function renderKnownArtifacts() {
  const recommendations = getArtifact("recommendations.json", "recommendations");
  const trace = getArtifact("agent-trace.jsonl", "agent_trace") || [];
  const enrichment = getArtifact("enrichment-results.json", "enrichment_results");
  const canonicalEvidence = getArtifact("canonical-evidence.json", "canonical_evidence");
  const cacheIndex = getArtifact("provider-cache-index.json", "provider_cache_index");
  const reviewQueue = getArtifact("review-queue.jsonl", "review_queue") || [];
  if (state.manifest) {
    renderManifest(state.manifest);
  }
  renderRecommendations(recommendations);
  renderTimeline(trace);
  renderEnrichmentFlow(enrichment, cacheIndex, reviewQueue, trace);
  renderCanonicalEvidence(canonicalEvidence);
  renderReviewQueue(reviewQueue);
}

function getArtifact(fileName, kind) {
  const artifact = (state.manifest?.artifacts || []).find((item) => item.kind === kind);
  if (artifact?.path) {
    const pathName = artifact.path.split(/[\\/]/).pop();
    if (state.artifacts.has(artifact.path)) {
      return state.artifacts.get(artifact.path);
    }
    if (artifact.path === pathName) {
      return state.artifacts.get(pathName) || null;
    }
    return null;
  }
  return state.artifacts.get(fileName) || null;
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

renderRecommendations(null);
renderTimeline([]);
renderEnrichmentFlow(null, null, [], []);
renderCanonicalEvidence(null);
renderReviewQueue([]);
