(function exposeCandidateProjection(global) {
  "use strict";

  const GROUPS = Object.freeze(["continue", "review", "reject", "insufficient-data"]);
  const STATUS_TO_GROUP = Object.freeze({pass: "continue", defer: "review", reject: "reject"});
  const COMPONENT_NAMES = Object.freeze([
    "homo_alignment", "lumo_alignment", "band_gap", "solubility",
    "stability", "cost", "synthesis_complexity",
  ]);
  const CONTEXT_KINDS = Object.freeze([
    "screening_input_view",
    "canonical_evidence",
    "scoring_view",
    "review_queue",
    "review_events",
    "review_summary",
    "recompute_markers",
    "recommendations",
    "acquisition_breakdown",
    "agent_trace",
    "literature_search_results",
    "literature_claims",
    "source_assets",
    "extraction_evaluation",
    "conflict_report",
    "provider_capabilities",
    "training_snapshot",
    "model_evaluation",
  ]);

  function deepFreeze(value) {
    if (!value || typeof value !== "object" || Object.isFrozen(value)) return value;
    Object.values(value).forEach(deepFreeze);
    return Object.freeze(value);
  }

  function cloneJson(value) {
    if (value === undefined) return undefined;
    return JSON.parse(JSON.stringify(value));
  }

  function text(value) {
    return typeof value === "string" ? value.trim() : "";
  }

  function compareText(left, right) {
    const a = String(left || "").toLocaleLowerCase("en");
    const b = String(right || "").toLocaleLowerCase("en");
    if (a < b) return -1;
    if (a > b) return 1;
    const rawA = String(left || "");
    const rawB = String(right || "");
    return rawA < rawB ? -1 : rawA > rawB ? 1 : 0;
  }

  function payload(snapshot, kind) {
    return snapshot?.artifacts?.[kind]?.payload ?? null;
  }

  function capability(snapshot, kind) {
    const declared = (snapshot?.manifest?.artifacts || []).some((item) => item?.kind === kind);
    const available = snapshot?.availability?.[kind]?.status ||
      (snapshot?.artifacts?.[kind] ? "available" : declared ? "unavailable" : "not-declared");
    return {
      kind,
      status: available,
      declared,
      path: snapshot?.availability?.[kind]?.path || snapshot?.artifacts?.[kind]?.path || null,
    };
  }

  function diagnostic(code, message, details = {}) {
    return {code, message, ...details};
  }

  function pushCandidateDiagnostic(collection, candidateId, code, message, source) {
    collection.push(diagnostic(code, message, {candidateId, source}));
  }

  function uniqueIds(values) {
    return [...new Set(values.map(text).filter(Boolean))].sort(compareText);
  }

  function buildIdentity(record) {
    const candidateId = text(record?.candidate_id);
    const materialId = text(record?.material?.material_id);
    const useMaterialId = text(record?.use_instance?.material_id);
    const useInstanceId = text(record?.use_instance?.use_instance_id);
    return {
      candidateId,
      materialId: materialId || null,
      useMaterialId: useMaterialId || null,
      useInstanceId: useInstanceId || null,
      materialKind: text(record?.material?.material_kind) || null,
      role: text(record?.use_instance?.role) || null,
      profile: text(record?.use_instance?.profile) || null,
      supplierStatus: text(record?.material?.supplier_status) || null,
    };
  }

  function identityConflict(identity) {
    if (!identity.materialId || !identity.useMaterialId || !identity.useInstanceId) {
      return "canonical material/use-instance mapping is incomplete";
    }
    if (identity.materialId !== identity.useMaterialId) {
      return `material ${identity.materialId} conflicts with use-instance material ${identity.useMaterialId}`;
    }
    return null;
  }

  function canonicalEvidenceIndex(record) {
    const index = new Map();
    for (const item of Array.isArray(record?.energy_evidence) ? record.energy_evidence : []) {
      const id = text(item?.energy_evidence_id);
      if (id) index.set(id, item);
    }
    return index;
  }

  function declaredEvidenceIds(row) {
    const values = [];
    for (const component of Array.isArray(row?.components) ? row.components : []) {
      if (Array.isArray(component?.evidence_ids)) values.push(...component.evidence_ids);
    }
    return uniqueIds(values);
  }

  function finiteUnitInterval(value) {
    return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1;
  }

  function uniqueNonEmptyStrings(values) {
    return Array.isArray(values) && values.every((value) => text(value)) &&
      new Set(values).size === values.length;
  }

  function screeningRowIsStructurallyValid(row) {
    if (!row || typeof row !== "object" || Array.isArray(row)) return false;
    if (!text(row.candidate_id) || !Array.isArray(row.codes) || !uniqueNonEmptyStrings(row.codes)) return false;
    if (!uniqueNonEmptyStrings(row.blocking_review_ids)) return false;
    if (!text(row.profile_version) || !finiteUnitInterval(row.weighted_utility) || !finiteUnitInterval(row.coverage)) return false;
    if (!row.weights || typeof row.weights !== "object" || Array.isArray(row.weights)) return false;
    if (!COMPONENT_NAMES.every((name) => typeof row.weights[name] === "number" && Number.isFinite(row.weights[name]))) return false;
    if (!Array.isArray(row.components) || row.components.length !== COMPONENT_NAMES.length) return false;
    const names = row.components.map((component) => text(component?.name));
    if (new Set(names).size !== COMPONENT_NAMES.length || !COMPONENT_NAMES.every((name) => names.includes(name))) return false;
    return row.components.every((component) =>
      finiteUnitInterval(component?.utility) &&
      finiteUnitInterval(component?.quality) &&
      typeof component?.observed === "boolean" &&
      uniqueNonEmptyStrings(component?.evidence_ids)
    );
  }

  function reviewIndex(snapshot, record, candidateId) {
    const index = new Map();
    for (const item of Array.isArray(record?.review_items) ? record.review_items : []) {
      const id = text(item?.review_item_id);
      if (id) index.set(id, item);
    }
    const queue = payload(snapshot, "review_queue");
    for (const item of Array.isArray(queue) ? queue : []) {
      const id = text(item?.review_item_id);
      if (id && text(item?.candidate_id) === candidateId) index.set(id, item);
    }
    return index;
  }

  function recommendationsFor(snapshot, candidateId) {
    const requests = payload(snapshot, "recommendations")?.requests;
    if (!Array.isArray(requests)) return [];
    return requests
      .filter((request) => text(request?.candidate_id) === candidateId)
      .map(cloneJson)
      .sort((left, right) => {
        const leftRank = Number.isFinite(left.rank) ? left.rank : Number.POSITIVE_INFINITY;
        const rightRank = Number.isFinite(right.rank) ? right.rank : Number.POSITIVE_INFINITY;
        return leftRank - rightRank || compareText(left.request_id, right.request_id);
      });
  }

  function lineageFor(snapshot, candidateId) {
    const trace = payload(snapshot, "agent_trace");
    if (!Array.isArray(trace)) return [];
    return trace
      .filter((event) => text(event?.candidate_id) === candidateId)
      .map((event) => ({
        eventId: text(event?.event_id) || null,
        eventType: text(event?.event_type) || null,
        provider: text(event?.provider) || null,
        outcome: text(event?.outcome) || null,
      }));
  }

  function project(snapshot) {
    const diagnostics = [];
    const capabilities = Object.fromEntries(
      CONTEXT_KINDS.map((kind) => [kind, capability(snapshot, kind)])
    );
    const canonical = payload(snapshot, "canonical_evidence");
    const records = Array.isArray(canonical?.records) ? canonical.records : [];
    if (!Array.isArray(canonical?.records)) {
      diagnostics.push(diagnostic(
        "canonical_unavailable_or_invalid",
        "canonical candidate universe is unavailable or invalid",
        {source: "canonical_evidence"}
      ));
    }

    const canonicalById = new Map();
    records.forEach((record, index) => {
      const candidateId = text(record?.candidate_id);
      if (!candidateId) {
        diagnostics.push(diagnostic(
          "canonical_candidate_id_missing",
          "canonical record has no explicit candidate_id",
          {source: "canonical_evidence", recordIndex: index}
        ));
        return;
      }
      const existing = canonicalById.get(candidateId) || [];
      existing.push(record);
      canonicalById.set(candidateId, existing);
    });

    const screening = payload(snapshot, "screening_input_view");
    const screeningAvailable = capabilities.screening_input_view.status === "available";
    const screeningRows = screeningAvailable && Array.isArray(screening?.candidates)
      ? screening.candidates
      : [];
    if (!screeningAvailable || !Array.isArray(screening?.candidates)) {
      diagnostics.push(diagnostic(
        "screening_unavailable_or_invalid",
        "screening_input_view candidates are unavailable or invalid",
        {source: "screening_input_view", status: capabilities.screening_input_view.status}
      ));
    }
    const screeningById = new Map();
    screeningRows.forEach((row, index) => {
      const candidateId = text(row?.candidate_id);
      if (!candidateId) {
        diagnostics.push(diagnostic(
          "screening_candidate_id_missing",
          "screening row has no explicit candidate_id",
          {source: "screening_input_view", recordIndex: index}
        ));
        return;
      }
      const existing = screeningById.get(candidateId) || [];
      existing.push(row);
      screeningById.set(candidateId, existing);
    });

    for (const candidateId of screeningById.keys()) {
      if (!canonicalById.has(candidateId)) {
        pushCandidateDiagnostic(
          diagnostics,
          candidateId,
          "screening_only_identity_contradiction",
          "screening candidate is outside the canonical universe and is not actionable",
          "screening_input_view"
        );
      }
    }

    const groups = Object.fromEntries(GROUPS.map((group) => [group, []]));
    for (const candidateId of [...canonicalById.keys()].sort(compareText)) {
      const candidateDiagnostics = [];
      const canonicalRecords = canonicalById.get(candidateId);
      const record = canonicalRecords[0];
      const identity = buildIdentity(record);
      const rows = screeningById.get(candidateId) || [];
      let row = rows.length === 1 ? rows[0] : null;

      if (canonicalRecords.length > 1) {
        pushCandidateDiagnostic(candidateDiagnostics, candidateId, "duplicate_canonical_candidate_id", "canonical candidate_id is duplicated", "canonical_evidence");
      }
      if (rows.length > 1) {
        pushCandidateDiagnostic(candidateDiagnostics, candidateId, "duplicate_screening_candidate_id", "screening candidate_id is duplicated or contradictory", "screening_input_view");
        row = null;
      } else if (!rows.length) {
        pushCandidateDiagnostic(candidateDiagnostics, candidateId, "screening_row_missing", "canonical candidate has no usable screening row", "screening_input_view");
      }

      const mappingProblem = identityConflict(identity);
      if (mappingProblem) {
        pushCandidateDiagnostic(candidateDiagnostics, candidateId, "canonical_mapping_conflict", mappingProblem, "canonical_evidence");
      }

      const backendStatus = row ? text(row.status) : "";
      if (row && !screeningRowIsStructurallyValid(row)) {
        pushCandidateDiagnostic(candidateDiagnostics, candidateId, "screening_row_invalid", "screening row does not satisfy the required projection fields", "screening_input_view");
      }
      if (row && !Object.prototype.hasOwnProperty.call(STATUS_TO_GROUP, backendStatus)) {
        pushCandidateDiagnostic(candidateDiagnostics, candidateId, "screening_status_unknown", `unsupported screening status: ${backendStatus || "missing"}`, "screening_input_view");
      }

      const evidenceIds = row ? declaredEvidenceIds(row) : [];
      const evidenceById = canonicalEvidenceIndex(record);
      const missingEvidenceIds = evidenceIds.filter((id) => !evidenceById.has(id));
      const conflictingEvidenceIds = evidenceIds.filter((id) => {
        const evidence = evidenceById.get(id);
        if (!evidence) return false;
        return text(evidence.material_id) !== identity.materialId ||
          text(evidence.use_instance_id) !== identity.useInstanceId;
      });
      if (missingEvidenceIds.length || conflictingEvidenceIds.length) {
        pushCandidateDiagnostic(
          candidateDiagnostics,
          candidateId,
          "unjoinable_evidence_reference",
          "declared screening evidence does not join to the canonical material/use-instance mapping",
          "screening_input_view"
        );
      }

      const reviewIds = row ? uniqueIds(Array.isArray(row.blocking_review_ids) ? row.blocking_review_ids : []) : [];
      const reviewsById = reviewIndex(snapshot, record, candidateId);
      const allowedReviewTargets = new Set([
        candidateId,
        identity.materialId,
        identity.useInstanceId,
        ...evidenceById.keys(),
      ].filter(Boolean));
      const missingReviewIds = reviewIds.filter((id) => !reviewsById.has(id));
      const conflictingReviewIds = reviewIds.filter((id) => {
        const review = reviewsById.get(id);
        return review && !allowedReviewTargets.has(text(review.target_id));
      });
      const unjoinableReviewIds = uniqueIds([...missingReviewIds, ...conflictingReviewIds]);
      if (unjoinableReviewIds.length) {
        pushCandidateDiagnostic(
          candidateDiagnostics,
          candidateId,
          "unjoinable_review_reference",
          "declared blocking review does not join by review_item_id and candidate_id",
          "screening_input_view"
        );
      }

      diagnostics.push(...candidateDiagnostics);
      const group = candidateDiagnostics.length
        ? "insufficient-data"
        : STATUS_TO_GROUP[backendStatus];
      const requests = recommendationsFor(snapshot, candidateId);
      const candidate = {
        candidateId,
        group,
        backendStatus: group === "insufficient-data" ? (backendStatus || null) : backendStatus,
        identity,
        blockers: {
          codes: uniqueIds(Array.isArray(row?.codes) ? row.codes : []),
          reviewIds,
          joinedReviews: reviewIds.filter((id) => reviewsById.has(id) && !conflictingReviewIds.includes(id)).map((id) => cloneJson(reviewsById.get(id))),
          missingReviewIds: unjoinableReviewIds,
        },
        evidenceCoverage: {
          declared: evidenceIds.length,
          joined: evidenceIds.length - missingEvidenceIds.length - conflictingEvidenceIds.length,
          ratio: evidenceIds.length
            ? (evidenceIds.length - missingEvidenceIds.length - conflictingEvidenceIds.length) / evidenceIds.length
            : null,
          evidenceIds,
          missingEvidenceIds: uniqueIds([...missingEvidenceIds, ...conflictingEvidenceIds]),
        },
        screening: row ? cloneJson({
          coverage: row.coverage ?? null,
          weightedUtility: row.weighted_utility ?? null,
          profileVersion: row.profile_version ?? null,
        }) : null,
        recommendation: {
          capability: capabilities.recommendations.status,
          requests,
        },
        lineage: {
          capability: capabilities.agent_trace.status,
          events: lineageFor(snapshot, candidateId),
        },
        diagnostic: candidateDiagnostics.length ? {
          source: candidateDiagnostics.map((item) => item.source).filter(Boolean).join(", "),
          reason: candidateDiagnostics.map((item) => item.message).join("; "),
          codes: candidateDiagnostics.map((item) => item.code),
        } : null,
      };
      groups[group].push(candidate);
    }

    return deepFreeze({
      run: cloneJson(snapshot?.manifestMetadata || {
        runId: snapshot?.manifest?.run_id || null,
        schemaVersion: snapshot?.manifest?.schema_version || null,
      }),
      capabilities,
      groups,
      diagnostics,
    });
  }

  function query(projection, controls = {}) {
    const search = text(controls.search).toLocaleLowerCase("en");
    const requestedStatuses = Array.isArray(controls.statuses)
      ? controls.statuses.filter((status) => GROUPS.includes(status))
      : [];
    const statuses = requestedStatuses.length ? requestedStatuses : GROUPS;
    const candidates = statuses.flatMap((status) => projection?.groups?.[status] || []);
    const filtered = search ? candidates.filter((candidate) => [
      candidate.candidateId,
      candidate.identity?.materialId,
      candidate.identity?.useInstanceId,
      candidate.identity?.role,
      candidate.backendStatus,
      candidate.group,
    ].some((value) => String(value || "").toLocaleLowerCase("en").includes(search))) : [...candidates];
    const sort = controls.sort || "candidate-asc";
    filtered.sort((left, right) => {
      if (sort === "candidate-desc") return compareText(right.candidateId, left.candidateId);
      if (sort === "coverage-desc") {
        const coverageOrder = (right.evidenceCoverage?.ratio ?? -1) - (left.evidenceCoverage?.ratio ?? -1);
        return coverageOrder || compareText(left.candidateId, right.candidateId);
      }
      if (sort === "group") {
        const groupOrder = GROUPS.indexOf(left.group) - GROUPS.indexOf(right.group);
        return groupOrder || compareText(left.candidateId, right.candidateId);
      }
      return compareText(left.candidateId, right.candidateId);
    });
    return deepFreeze(filtered.map(cloneJson));
  }

  global.SpiroCandidateProjection = Object.freeze({GROUPS, project, query});
})(typeof globalThis === "undefined" ? this : globalThis);
