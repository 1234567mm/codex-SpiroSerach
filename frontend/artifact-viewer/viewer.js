const state = {
  manifest: null,
  artifacts: new Map(),
};

document.getElementById("manifestFile").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  state.manifest = JSON.parse(await file.text());
  renderManifest(state.manifest);
  renderKnownArtifacts();
});

document.getElementById("artifactFiles").addEventListener("change", async (event) => {
  state.artifacts.clear();
  for (const file of event.target.files) {
    const text = await file.text();
    state.artifacts.set(file.name, parseArtifact(file.name, text));
  }
  renderKnownArtifacts();
});

function parseArtifact(name, text) {
  if (name.endsWith(".jsonl")) {
    return parseJsonl(text);
  }
  return JSON.parse(text);
}

function parseJsonl(text) {
  return text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}

function renderManifest(manifest) {
  document.getElementById("artifactCount").textContent = String((manifest.artifacts || []).length);
  document.getElementById("modelVersion").textContent = manifest.model_version || "-";
  document.getElementById("budgetValue").textContent = manifest.budget ?? "-";
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
  const recommendations = state.artifacts.get("recommendations.json");
  const trace = state.artifacts.get("agent-trace.jsonl") || [];
  if (state.manifest) {
    renderManifest(state.manifest);
  }
  renderRecommendations(recommendations);
  renderTimeline(trace);
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
        candidates ${safeCount(event.candidate_count)} / recommended ${safeCount(event.recommended_count)} / observations ${safeCount(event.observation_count)}
      </div>
    </div>`)
    .join("");
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

renderRecommendations(null);
renderTimeline([]);
