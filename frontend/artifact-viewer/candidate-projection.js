(function exposeCandidateProjection(global) {
  "use strict";

  const GROUPS = Object.freeze(["continue", "review", "reject", "insufficient-data"]);
  const STATUS_TO_GROUP = Object.freeze({pass: "continue", defer: "review", reject: "reject"});
  const COMPONENT_NAMES = Object.freeze([
    "homo_alignment", "lumo_alignment", "band_gap", "solubility",
    "stability", "cost", "synthesis_complexity",
  ]);
  const SCREENING_CODES = Object.freeze([
    "HOMO_NOT_YET_RESOLVED",
    "HOMO_REFERENCE_SCALE_MISSING",
    "HOMO_MISMATCH",
    "LUMO_NOT_YET_RESOLVED",
    "LUMO_REFERENCE_SCALE_MISSING",
    "LUMO_MISMATCH",
    "BAND_GAP_NOT_YET_RESOLVED",
    "BAND_GAP_TOO_LOW",
  ]);
  const SCREENING_PROFILE_VERSION = "v12.htl_screening.v1";
  const SCREENING_SCHEMA_VERSION = "v19.screening_input_view.v1";
  const SCREENING_WEIGHTS = Object.freeze({
    homo_alignment: 0.3,
    lumo_alignment: 0.2,
    band_gap: 0.1,
    solubility: 0.1,
    stability: 0.15,
    cost: 0.1,
    synthesis_complexity: 0.05,
  });
  const SCREENING_PAYLOAD_FIELDS = Object.freeze(["schema_version", "profile_version", "candidates"]);
  const SCREENING_ROW_FIELDS = Object.freeze([
    "candidate_id", "status", "codes", "components", "blocking_review_ids",
    "profile_version", "weights", "weighted_utility", "coverage",
  ]);
  const SCREENING_COMPONENT_FIELDS = Object.freeze([
    "name", "utility", "quality", "observed", "evidence_ids",
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
    "candidate_identity_projection",
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

  function identifier(value) {
    return typeof value === "string" && value.length ? value : "";
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

  function uniqueIdentifiers(values) {
    return [...new Set(values.map(identifier).filter(Boolean))].sort(compareText);
  }

  function uniqueRawStrings(values) {
    return [...new Set(values.filter((value) => typeof value === "string"))].sort(compareText);
  }

  function hasExactFields(value, fields) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return false;
    const actual = Object.keys(value).sort(compareText);
    const expected = [...fields].sort(compareText);
    return actual.length === expected.length && expected.every((field, index) => actual[index] === field);
  }

  function buildIdentity(record) {
    const candidateId = identifier(record?.candidate_id);
    const materialId = identifier(record?.material?.material_id);
    const useMaterialId = identifier(record?.use_instance?.material_id);
    const useInstanceId = identifier(record?.use_instance?.use_instance_id);
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
      const id = identifier(item?.energy_evidence_id);
      if (!id) continue;
      const matches = index.get(id) || [];
      matches.push(item);
      index.set(id, matches);
    }
    return index;
  }

  function declaredEvidenceIds(row) {
    const values = [];
    for (const component of Array.isArray(row?.components) ? row.components : []) {
      if (Array.isArray(component?.evidence_ids)) values.push(...component.evidence_ids);
    }
    return uniqueIdentifiers(values);
  }

  function finiteUnitInterval(value) {
    return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1;
  }

  function uniqueNonEmptyStrings(values) {
    return Array.isArray(values) && values.every((value) => text(value)) &&
      new Set(values).size === values.length;
  }

  function screeningRowIsStructurallyValid(row) {
    if (!hasExactFields(row, SCREENING_ROW_FIELDS)) return false;
    if (!identifier(row.candidate_id) || !Array.isArray(row.codes) || !uniqueNonEmptyStrings(row.codes)) return false;
    if (!Object.prototype.hasOwnProperty.call(STATUS_TO_GROUP, row.status)) return false;
    if (!row.codes.every((code) => SCREENING_CODES.includes(code))) return false;
    if (!uniqueNonEmptyStrings(row.blocking_review_ids)) return false;
    if (row.profile_version !== SCREENING_PROFILE_VERSION || !finiteUnitInterval(row.weighted_utility) || !finiteUnitInterval(row.coverage)) return false;
    if (!row.weights || typeof row.weights !== "object" || Array.isArray(row.weights)) return false;
    const weightNames = Object.keys(row.weights).sort(compareText);
    if (weightNames.length !== COMPONENT_NAMES.length || !COMPONENT_NAMES.every((name) => weightNames.includes(name))) return false;
    if (!COMPONENT_NAMES.every((name) => row.weights[name] === SCREENING_WEIGHTS[name])) return false;
    if (!Array.isArray(row.components) || row.components.length !== COMPONENT_NAMES.length) return false;
    const names = row.components.map((component) => identifier(component?.name));
    if (new Set(names).size !== COMPONENT_NAMES.length || !COMPONENT_NAMES.every((name) => names.includes(name))) return false;
    return row.components.every((component) =>
      hasExactFields(component, SCREENING_COMPONENT_FIELDS) &&
      finiteUnitInterval(component?.utility) &&
      finiteUnitInterval(component?.quality) &&
      typeof component?.observed === "boolean" &&
      uniqueNonEmptyStrings(component?.evidence_ids)
    );
  }

  function reviewIndex(snapshot, record, candidateId, relatedReviewIds) {
    const index = new Map();
    for (const item of Array.isArray(record?.review_items) ? record.review_items : []) {
      const id = identifier(item?.review_item_id);
      if (!id) continue;
      const matches = index.get(id) || {canonical: [], queue: []};
      matches.canonical.push(item);
      index.set(id, matches);
    }
    const queue = payload(snapshot, "review_queue");
    for (const item of Array.isArray(queue) ? queue : []) {
      const id = identifier(item?.review_item_id);
      if (!id) continue;
      const queueCandidateId = identifier(item?.candidate_id);
      const relatedId = index.has(id) || relatedReviewIds.includes(id);
      const relatedCandidate = queueCandidateId === candidateId ||
        text(queueCandidateId) === text(candidateId);
      if (!relatedId && !relatedCandidate) continue;
      const matches = index.get(id) || {canonical: [], queue: []};
      matches.queue.push(item);
      index.set(id, matches);
    }
    return index;
  }

  function reviewTargetMatches(review, identity, evidenceById) {
    const anchors = {
      candidate: identity.candidateId,
      material: identity.materialId,
      use_instance: identity.useInstanceId,
    };
    const targetType = identifier(review?.target_type);
    const targetId = identifier(review?.target_id);
    if (targetType === "energy_evidence") {
      const matches = evidenceById.get(targetId) || [];
      if (matches.length !== 1) return false;
      return identifier(matches[0]?.material_id) === identity.materialId &&
        identifier(matches[0]?.use_instance_id) === identity.useInstanceId;
    }
    return Boolean(Object.prototype.hasOwnProperty.call(anchors, targetType) &&
      targetId && targetId === anchors[targetType]);
  }

  function reviewResolution(matches, candidateId, identity, evidenceById) {
    const canonical = matches?.canonical || [];
    const queue = matches?.queue || [];
    if (!canonical.length && !queue.length) return {status: "missing", review: null};
    if (canonical.length > 1 || queue.length > 1) return {status: "ambiguous", review: null};
    if (queue.length === 1 && identifier(queue[0]?.candidate_id) !== candidateId) {
      return {status: "conflict", review: null};
    }
    const canonicalReview = canonical[0] || null;
    const queueReview = queue[0] || null;
    if (canonicalReview && queueReview) {
      const canonicalAnchor = `${identifier(canonicalReview.target_type)}\0${identifier(canonicalReview.target_id)}`;
      const queueAnchor = `${identifier(queueReview.target_type)}\0${identifier(queueReview.target_id)}`;
      if (canonicalAnchor !== queueAnchor) return {status: "conflict", review: null};
    }
    const represented = [canonicalReview, queueReview].filter(Boolean);
    if (represented.some((review) => !reviewTargetMatches(review, identity, evidenceById))) {
      return {status: "conflict", review: null};
    }
    return {
      status: "valid",
      review: canonicalReview && queueReview
        ? {...queueReview, ...canonicalReview, artifactKinds: ["canonical_evidence", "review_queue"]}
        : (canonicalReview
          ? {...canonicalReview, artifactKinds: ["canonical_evidence"]}
          : {...queueReview, artifactKinds: ["review_queue"]}),
    };
  }

  function recommendationsFor(snapshot, candidateId) {
    const requests = payload(snapshot, "recommendations")?.requests;
    if (!Array.isArray(requests)) return [];
    return requests
      .filter((request) => identifier(request?.candidate_id) === candidateId)
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
      .filter((event) => identifier(event?.candidate_id) === candidateId)
      .map((event) => ({
        eventId: text(event?.event_id) || null,
        eventType: text(event?.event_type) || null,
        provider: text(event?.provider) || null,
        outcome: text(event?.outcome) || null,
      }));
  }

  function screeningComponentsFor(row) {
    return (Array.isArray(row?.components) ? row.components : [])
      .map((component) => ({
        artifactKind: "screening_input_view",
        name: identifier(component?.name) || null,
        utility: component?.utility ?? null,
        quality: component?.quality ?? null,
        observed: typeof component?.observed === "boolean" ? component.observed : null,
        evidenceIds: uniqueIdentifiers(Array.isArray(component?.evidence_ids) ? component.evidence_ids : []),
      }))
      .sort((left, right) => {
        const leftIndex = COMPONENT_NAMES.indexOf(left.name);
        const rightIndex = COMPONENT_NAMES.indexOf(right.name);
        return (leftIndex === -1 ? Number.POSITIVE_INFINITY : leftIndex) -
          (rightIndex === -1 ? Number.POSITIVE_INFINITY : rightIndex) ||
          compareText(left.name, right.name);
      });
  }

  function scoringEvidenceFor(snapshot, identity, evidenceIds) {
    const diagnostics = [];
    const unavailable = new Set();
    const facts = payload(snapshot, "scoring_view")?.energy_facts;
    if (!Array.isArray(facts)) {
      if (evidenceIds.length) {
        diagnostics.push(diagnostic(
          "scoring_view_unavailable_or_invalid",
          "declared screening evidence cannot be described as eligible because scoring_view is unavailable or invalid",
          {source: "scoring_view"}
        ));
      }
      evidenceIds.forEach((id) => unavailable.add(id));
      return {
        eligibleScoringEvidence: [],
        unavailableEvidenceIds: [...unavailable].sort(compareText),
        diagnostics,
      };
    }
    const requested = new Set(evidenceIds);
    const byId = new Map();
    facts.forEach((fact) => {
      const id = identifier(fact?.evidence_id);
      if (!id || !requested.has(id)) return;
      const matches = byId.get(id) || [];
      matches.push(fact);
      byId.set(id, matches);
    });
    const eligible = [];
    for (const evidenceId of evidenceIds) {
      const matches = byId.get(evidenceId) || [];
      if (!matches.length) {
        unavailable.add(evidenceId);
        continue;
      }
      if (matches.length > 1) {
        unavailable.add(evidenceId);
        diagnostics.push(diagnostic(
          "ambiguous_scoring_evidence",
          "declared screening evidence_id resolves to multiple scoring_view facts",
          {source: "scoring_view", evidenceId}
        ));
        continue;
      }
      const fact = matches[0];
      if (identifier(fact?.material_id) !== identity.materialId ||
          identifier(fact?.use_instance_id) !== identity.useInstanceId) {
        unavailable.add(evidenceId);
        diagnostics.push(diagnostic(
          "contradictory_scoring_evidence",
          "scoring_view fact does not match the selected candidate material/use-instance identity",
          {source: "scoring_view", evidenceId}
        ));
        continue;
      }
      if (fact?.quality?.eligible_for_scoring !== true) {
        unavailable.add(evidenceId);
        diagnostics.push(diagnostic(
          "scoring_evidence_not_policy_admitted",
          "scoring_view fact is present but not marked eligible_for_scoring",
          {source: "scoring_view", evidenceId}
        ));
        continue;
      }
      eligible.push({
        artifactKind: "scoring_view",
        evidenceId,
        materialId: identifier(fact.material_id) || null,
        useInstanceId: identifier(fact.use_instance_id) || null,
        propertyName: text(fact.property_name) || null,
        valueEv: fact.value_ev ?? null,
        unit: text(fact.unit) || null,
        method: text(fact.method) || null,
        referenceScale: text(fact.reference_scale) || null,
        computed: typeof fact.computed === "boolean" ? fact.computed : null,
        quality: cloneJson(fact.quality || {}),
      });
    }
    return {
      eligibleScoringEvidence: eligible.sort((left, right) => compareText(left.evidenceId, right.evidenceId)),
      unavailableEvidenceIds: [...unavailable].sort(compareText),
      diagnostics,
    };
  }

  function acquisitionFor(snapshot, candidateId) {
    const acquisition = payload(snapshot, "acquisition_breakdown");
    const candidates = Array.isArray(acquisition?.candidates) ? acquisition.candidates : [];
    const matches = candidates.filter((item) => identifier(item?.candidate_id) === candidateId);
    if (matches.length !== 1) return null;
    const item = matches[0];
    return {
      artifactKind: "acquisition_breakdown",
      requestId: text(acquisition?.request_id) || null,
      modelVersion: text(acquisition?.model_version) || null,
      strategy: text(acquisition?.strategy) || null,
      modelScore: item.model_score ?? null,
      heuristicScore: item.heuristic_score ?? null,
      observedUtility: item.observed_utility ?? null,
      modelSelected: typeof item.model_selected === "boolean" ? item.model_selected : null,
      heuristicSelected: typeof item.heuristic_selected === "boolean" ? item.heuristic_selected : null,
    };
  }

  function reviewKey(value) {
    return [
      identifier(value?.review_item_id),
      identifier(value?.target_type),
      identifier(value?.target_id),
    ].join("\0");
  }

  function projectReview(review) {
    return {
      artifactKind: Array.isArray(review?.artifactKinds) ? review.artifactKinds.join(", ") : "canonical_evidence, review_queue",
      reviewItemId: identifier(review?.review_item_id) || null,
      targetType: identifier(review?.target_type) || null,
      targetId: identifier(review?.target_id) || null,
      candidateId: identifier(review?.candidate_id) || null,
      reason: text(review?.reason) || text(review?.reason_code) || null,
      reasonCode: text(review?.reason_code) || null,
      resolutionStatus: text(review?.resolution_status) || null,
      severity: text(review?.severity) || null,
      assignedQueue: text(review?.assigned_queue) || null,
      blockingSurface: text(review?.blocking_surface) || null,
    };
  }

  function projectReviewEvent(event, status) {
    return {
      artifactKind: "review_events",
      eventId: identifier(event?.event_id) || null,
      reviewItemId: identifier(event?.review_item_id) || null,
      targetType: identifier(event?.target_type) || null,
      targetId: identifier(event?.target_id) || null,
      decision: text(event?.decision) || null,
      resolutionStatus: text(event?.resolution_status) || null,
      reason: text(event?.reason) || null,
      status,
      recomputeMarkerIds: uniqueIdentifiers(Array.isArray(event?.recompute_marker_ids) ? event.recompute_marker_ids : []),
    };
  }

  function reviewEventsFor(snapshot, joinedReviews, reviewIds) {
    const diagnostics = [];
    const events = payload(snapshot, "review_events");
    if (!Array.isArray(events)) return {appliedReviewEvents: [], auditReviewEvents: [], diagnostics};
    const knownReviewIds = new Set(uniqueIdentifiers([
      ...reviewIds,
      ...joinedReviews.map((review) => review.review_item_id),
    ]));
    const exactTargets = new Set(joinedReviews.map(reviewKey));
    const appliedReviewEvents = [];
    const auditReviewEvents = [];
    events.forEach((event) => {
      const reviewItemId = identifier(event?.review_item_id);
      if (!reviewItemId || !knownReviewIds.has(reviewItemId)) return;
      if (exactTargets.has(reviewKey(event))) {
        appliedReviewEvents.push(projectReviewEvent(event, "applied"));
        return;
      }
      auditReviewEvents.push(projectReviewEvent(event, "wrong-target"));
      diagnostics.push(diagnostic(
        "wrong_target_review_event",
        "review_event shares review_item_id but does not match target_type and target_id for the selected candidate",
        {source: "review_events", reviewItemId}
      ));
    });
    appliedReviewEvents.sort((left, right) => compareText(left.eventId, right.eventId));
    auditReviewEvents.sort((left, right) => compareText(left.eventId, right.eventId));
    return {appliedReviewEvents, auditReviewEvents, diagnostics};
  }

  function recomputeMarkersFor(snapshot, candidateId, identity, evidenceById, appliedReviewEvents, reviewIds) {
    const markers = payload(snapshot, "recompute_markers");
    if (!Array.isArray(markers)) return [];
    const appliedEventIds = new Set(appliedReviewEvents.map((event) => event.eventId).filter(Boolean));
    const knownReviewIds = new Set(reviewIds);
    return markers
      .filter((marker) =>
        identifier(marker?.candidate_id) === candidateId &&
        (appliedEventIds.has(identifier(marker?.review_event_id)) || knownReviewIds.has(identifier(marker?.review_item_id))) &&
        reviewTargetMatches(marker, identity, evidenceById)
      )
      .map((marker) => ({
        artifactKind: "recompute_markers",
        markerId: identifier(marker?.marker_id) || null,
        reviewEventId: identifier(marker?.review_event_id) || null,
        reviewItemId: identifier(marker?.review_item_id) || null,
        targetType: identifier(marker?.target_type) || null,
        targetId: identifier(marker?.target_id) || null,
        status: text(marker?.status) || null,
        reason: text(marker?.reason) || null,
        affectedArtifacts: uniqueRawStrings(Array.isArray(marker?.affected_artifacts) ? marker.affected_artifacts : []),
      }))
      .sort((left, right) => compareText(left.markerId, right.markerId));
  }

  function reviewSummaryFor(snapshot) {
    const summary = payload(snapshot, "review_summary");
    if (!summary || typeof summary !== "object" || Array.isArray(summary)) return null;
    return {
      artifactKind: "review_summary",
      reviewCount: summary.review_count ?? null,
      eventCount: summary.event_count ?? null,
      appliedEventCount: summary.applied_event_count ?? null,
      openBlockingCount: summary.open_blocking_count ?? null,
      resolvedCount: summary.resolved_count ?? null,
      rejectedCount: summary.rejected_count ?? null,
      reviewItemIds: uniqueIdentifiers(Array.isArray(summary.review_item_ids) ? summary.review_item_ids : []),
      reviewEventIds: uniqueIdentifiers(Array.isArray(summary.review_event_ids) ? summary.review_event_ids : []),
      recomputeMarkerIds: uniqueIdentifiers(Array.isArray(summary.recompute_marker_ids) ? summary.recompute_marker_ids : []),
    };
  }

  function artifactStatusesFor(capabilities, kinds) {
    return kinds.map((kind) => ({
      kind,
      status: capabilities[kind]?.status || "not-declared",
      declared: Boolean(capabilities[kind]?.declared),
      path: capabilities[kind]?.path || null,
    }));
  }

  function paperEvidenceFor(snapshot, capabilities, candidateId) {
    const identityProjection = payload(snapshot, "candidate_identity_projection");
    const identityCandidates = Array.isArray(identityProjection?.candidates)
      ? identityProjection.candidates
      : [];
    const identityCandidate = identityCandidates.find((item) => identifier(item?.candidate_id) === candidateId);
    const identityDiagnostics = [];
    if (identityCandidate?.identity_diagnostics) {
      const state = text(identityCandidate.identity_diagnostics.reviewer_state);
      for (const code of uniqueRawStrings(identityCandidate.identity_diagnostics.reason_codes || [])) {
        identityDiagnostics.push(diagnostic(
          code,
          `candidate identity reviewer state is ${state || "unknown"}; paper association remains diagnostic-only`,
          {
            source: "candidate_identity_projection",
            candidateId,
            reviewerState: state || "unknown",
            reviewItemIds: uniqueIdentifiers(identityCandidate.identity_diagnostics.blocking_review_ids || []),
          }
        ));
      }
    }
    const linkDiagnostics = Array.isArray(identityProjection?.link_diagnostics)
      ? identityProjection.link_diagnostics
          .filter((item) => identifier(item?.candidate_id) === candidateId)
          .map((item) => diagnostic(
            text(item?.reason_code) || "identity_link_diagnostic",
            text(item?.message) || "identity link is diagnostic-only and is not displayed as a candidate-paper association",
            {
              source: "candidate_identity_projection",
              candidateId,
              linkId: identifier(item?.link_id) || null,
              evidenceId: identifier(item?.evidence_id) || null,
              reviewerState: text(item?.reviewer_state) || null,
            }
          ))
      : [];
    const acceptedLinks = Array.isArray(identityCandidate?.accepted_links)
      ? identityCandidate.accepted_links
      : [];
    const acceptedRecords = acceptedLinks
      .filter((link) => text(link?.reviewer_state) === "accepted")
      .map((link) => ({
        artifactKind: "candidate_identity_projection",
        linkId: identifier(link?.link_id) || null,
        candidateId,
        stableIdentityId: identifier(link?.stable_identity_id) || null,
        evidenceId: identifier(link?.evidence_id) || null,
        evidenceKind: text(link?.evidence_kind) || null,
        doi: text(link?.paper?.doi) || null,
        sourceId: text(link?.paper?.source_id) || null,
        title: text(link?.paper?.title) || null,
        reviewerState: text(link?.reviewer_state) || null,
        confidenceCategory: text(link?.confidence_category) || null,
        linkBasis: cloneJson(Array.isArray(link?.link_basis) ? link.link_basis : []),
        lineage: cloneJson(link?.lineage || {}),
      }))
      .sort((left, right) => compareText(left.evidenceId, right.evidenceId) || compareText(left.linkId, right.linkId));
    if (identityCandidate || identityProjection) {
      const diagnostics = [...identityDiagnostics, ...linkDiagnostics].sort((left, right) =>
        compareText(left.code, right.code) || compareText(left.evidenceId, right.evidenceId)
      );
      return {
        status: acceptedRecords.length ? "available" : "unavailable",
        message: acceptedRecords.length
          ? "Accepted explicit V21 candidate identity links are available."
          : "No accepted explicit V21 identity links; proposed, blocked, or conflicting links are diagnostics only.",
        records: acceptedRecords,
        diagnostics,
        runArtifacts: artifactStatusesFor(capabilities, [
          "candidate_identity_projection",
          "literature_claims",
          "source_assets",
          "literature_search_results",
        ]),
      };
    }

    const explicit = payload(snapshot, "candidate_paper_evidence");
    const records = Array.isArray(explicit?.records)
      ? explicit.records
      : (Array.isArray(explicit) ? explicit : []);
    const candidateRecords = records
      .filter((record) => identifier(record?.candidate_id) === candidateId)
      .map((record) => ({artifactKind: "candidate_paper_evidence", ...cloneJson(record)}));
    if (candidateRecords.length) {
      return {
        status: "available",
        message: "Explicit backend candidate-to-paper join is available.",
        records: candidateRecords,
        diagnostics: [],
        runArtifacts: artifactStatusesFor(capabilities, ["literature_claims", "source_assets", "literature_search_results"]),
      };
    }
    return {
      status: "unavailable",
      message: "No explicit backend candidate-to-paper join; literature is available only at run/DOI scope.",
      records: [],
      diagnostics: [],
      runArtifacts: artifactStatusesFor(capabilities, ["literature_claims", "source_assets", "literature_search_results"]),
    };
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
      const candidateId = identifier(record?.candidate_id);
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
    const screeningContractSupported = screeningAvailable &&
      hasExactFields(screening, SCREENING_PAYLOAD_FIELDS) &&
      screening?.schema_version === SCREENING_SCHEMA_VERSION &&
      screening?.profile_version === SCREENING_PROFILE_VERSION;
    if (!screeningAvailable || !Array.isArray(screening?.candidates)) {
      diagnostics.push(diagnostic(
        "screening_unavailable_or_invalid",
        "screening_input_view candidates are unavailable or invalid",
        {source: "screening_input_view", status: capabilities.screening_input_view.status}
      ));
    } else if (!screeningContractSupported) {
      diagnostics.push(diagnostic(
        "screening_contract_unsupported",
        "Browser-local structural check does not support the screening schema/profile markers",
        {source: "screening_input_view"}
      ));
    }
    const screeningById = new Map();
    screeningRows.forEach((row, index) => {
      const candidateId = identifier(row?.candidate_id);
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

      const backendStatus = row ? identifier(row.status) : "";
      if (row && !screeningContractSupported) {
        pushCandidateDiagnostic(candidateDiagnostics, candidateId, "screening_contract_unsupported", "Browser-local structural check does not support the screening schema/profile markers", "screening_input_view");
      }
      if (row && !screeningRowIsStructurallyValid(row)) {
        pushCandidateDiagnostic(candidateDiagnostics, candidateId, "screening_row_invalid", "Browser-local structural check rejected the screening row fields", "screening_input_view");
      }
      if (row && !Object.prototype.hasOwnProperty.call(STATUS_TO_GROUP, backendStatus)) {
        pushCandidateDiagnostic(candidateDiagnostics, candidateId, "screening_status_unknown", `unsupported screening status: ${backendStatus || "missing"}`, "screening_input_view");
      }

      const evidenceIds = row ? declaredEvidenceIds(row) : [];
      const evidenceById = canonicalEvidenceIndex(record);
      const ownedDuplicateEvidenceIds = [...evidenceById.entries()]
        .filter(([, matches]) => matches.length > 1)
        .map(([id]) => id)
        .sort(compareText);
      if (ownedDuplicateEvidenceIds.length) {
        pushCandidateDiagnostic(
          candidateDiagnostics,
          candidateId,
          "duplicate_owned_evidence_id",
          "canonical candidate contains duplicate energy_evidence_id records",
          "canonical_evidence"
        );
      }
      const missingEvidenceIds = evidenceIds.filter((id) => !evidenceById.has(id));
      const ambiguousEvidenceIds = evidenceIds.filter((id) => (evidenceById.get(id) || []).length > 1);
      const conflictingEvidenceIds = evidenceIds.filter((id) => {
        const matches = evidenceById.get(id) || [];
        if (matches.length !== 1) return false;
        const evidence = matches[0];
        return identifier(evidence.material_id) !== identity.materialId ||
          identifier(evidence.use_instance_id) !== identity.useInstanceId;
      });
      if (ambiguousEvidenceIds.length) {
        pushCandidateDiagnostic(
          candidateDiagnostics,
          candidateId,
          "ambiguous_evidence_reference",
          "declared screening evidence_id resolves to multiple canonical records",
          "canonical_evidence"
        );
      }
      if (missingEvidenceIds.length || conflictingEvidenceIds.length) {
        pushCandidateDiagnostic(
          candidateDiagnostics,
          candidateId,
          "unjoinable_evidence_reference",
          "declared screening evidence does not join to the canonical material/use-instance mapping",
          "screening_input_view"
        );
      }

      const reviewIds = row ? uniqueIdentifiers(Array.isArray(row.blocking_review_ids) ? row.blocking_review_ids : []) : [];
      const canonicalReviewIds = uniqueIdentifiers(
        (Array.isArray(record?.review_items) ? record.review_items : [])
          .map((item) => item?.review_item_id)
      );
      const reviewValidationIds = uniqueIdentifiers([...reviewIds, ...canonicalReviewIds]);
      const reviewsById = reviewIndex(snapshot, record, candidateId, reviewValidationIds);
      const canonicalDuplicateReviewIds = [...reviewsById.entries()]
        .filter(([, matches]) => matches.canonical.length > 1)
        .map(([id]) => id)
        .sort(compareText);
      const queueDuplicateReviewIds = [...reviewsById.entries()]
        .filter(([, matches]) =>
          matches.queue.filter((item) => identifier(item?.candidate_id) === candidateId).length > 1
        )
        .map(([id]) => id)
        .sort(compareText);
      if (canonicalDuplicateReviewIds.length) {
        pushCandidateDiagnostic(
          candidateDiagnostics,
          candidateId,
          "duplicate_owned_review_id",
          "canonical candidate contains duplicate review_item_id records",
          "canonical_evidence"
        );
      }
      if (queueDuplicateReviewIds.length) {
        pushCandidateDiagnostic(
          candidateDiagnostics,
          candidateId,
          "duplicate_owned_review_id",
          "review_queue contains duplicate review_item_id records for the exact candidate_id",
          "review_queue"
        );
      }
      const sameSourceDuplicateReviewIds = uniqueIdentifiers([
        ...canonicalDuplicateReviewIds,
        ...queueDuplicateReviewIds,
      ]);
      const reviewResolutionIds = reviewValidationIds.filter((id) =>
        !sameSourceDuplicateReviewIds.includes(id)
      );
      const reviewResolutions = new Map(reviewResolutionIds.map((id) => [
        id,
        reviewResolution(reviewsById.get(id), candidateId, identity, evidenceById),
      ]));
      const missingReviewIds = reviewResolutionIds.filter((id) => reviewResolutions.get(id).status === "missing");
      const ambiguousReviewIds = reviewResolutionIds.filter((id) => reviewResolutions.get(id).status === "ambiguous");
      const conflictingReviewIds = reviewResolutionIds.filter((id) => reviewResolutions.get(id).status === "conflict");
      if (ambiguousReviewIds.length) {
        pushCandidateDiagnostic(
          candidateDiagnostics,
          candidateId,
          "ambiguous_review_reference",
          "review_item_id resolves to multiple records",
          "canonical_evidence, review_queue"
        );
      }
      const unjoinableReviewIds = uniqueIdentifiers([...missingReviewIds, ...ambiguousReviewIds, ...conflictingReviewIds]);
      const declaredUnjoinableReviewIds = reviewIds.filter((id) => unjoinableReviewIds.includes(id));
      const ownedUnjoinableReviewIds = canonicalReviewIds.filter((id) =>
        unjoinableReviewIds.includes(id) && !reviewIds.includes(id)
      );
      if (declaredUnjoinableReviewIds.length) {
        pushCandidateDiagnostic(
          candidateDiagnostics,
          candidateId,
          "unjoinable_review_reference",
          "declared blocking review does not join by review_item_id and candidate_id",
          "screening_input_view, canonical_evidence, review_queue"
        );
      }
      if (ownedUnjoinableReviewIds.length) {
        pushCandidateDiagnostic(
          candidateDiagnostics,
          candidateId,
          "unjoinable_review_reference",
          "canonical review representation conflicts with review_queue candidate or typed target",
          "canonical_evidence, review_queue"
        );
      }

      diagnostics.push(...candidateDiagnostics);
      const group = candidateDiagnostics.length
        ? "insufficient-data"
        : STATUS_TO_GROUP[backendStatus];
      const requests = recommendationsFor(snapshot, candidateId);
      const joinedReviews = reviewIds
        .filter((id) => reviewResolutions.get(id)?.status === "valid")
        .map((id) => cloneJson(reviewResolutions.get(id).review));
      const components = screeningComponentsFor(row);
      const scoringDetail = scoringEvidenceFor(snapshot, identity, evidenceIds);
      const acquisition = acquisitionFor(snapshot, candidateId);
      const reviewEvents = reviewEventsFor(snapshot, joinedReviews, reviewIds);
      const recomputeMarkers = recomputeMarkersFor(
        snapshot,
        candidateId,
        identity,
        evidenceById,
        reviewEvents.appliedReviewEvents,
        reviewIds
      );
      const detailDiagnostics = [
        ...scoringDetail.diagnostics,
        ...reviewEvents.diagnostics,
      ];
      const candidate = {
        candidateId,
        group,
        backendStatus: group === "insufficient-data" ? (backendStatus || null) : backendStatus,
        identity,
        blockers: {
          codes: uniqueRawStrings(Array.isArray(row?.codes) ? row.codes : []),
          reviewIds,
          joinedReviews,
          missingReviewIds: uniqueIdentifiers([
            ...declaredUnjoinableReviewIds,
            ...reviewIds.filter((id) => sameSourceDuplicateReviewIds.includes(id)),
          ]),
        },
        evidenceCoverage: {
          declared: evidenceIds.length,
          joined: evidenceIds.length - uniqueIdentifiers([...missingEvidenceIds, ...ambiguousEvidenceIds, ...conflictingEvidenceIds]).length,
          ratio: evidenceIds.length
            ? (evidenceIds.length - uniqueIdentifiers([...missingEvidenceIds, ...ambiguousEvidenceIds, ...conflictingEvidenceIds]).length) / evidenceIds.length
            : null,
          evidenceIds,
          missingEvidenceIds: uniqueIdentifiers([...missingEvidenceIds, ...ambiguousEvidenceIds, ...conflictingEvidenceIds]),
        },
        screening: row ? cloneJson({
          coverage: row.coverage ?? null,
          weightedUtility: row.weighted_utility ?? null,
          profileVersion: row.profile_version ?? null,
          weights: row.weights ?? null,
          components,
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
        detail: {
          overview: {
            artifactKind: row ? "screening_input_view" : null,
            availability: artifactStatusesFor(capabilities, [
              "screening_input_view",
              "canonical_evidence",
              "scoring_view",
              "review_queue",
              "review_events",
              "recompute_markers",
              "acquisition_breakdown",
            ]),
          },
          explanation: {
            components,
            weights: row ? cloneJson(row.weights || {}) : {},
            weightedUtility: row?.weighted_utility ?? null,
            coverage: row?.coverage ?? null,
            profileVersion: row?.profile_version ?? null,
            eligibleScoringEvidence: scoringDetail.eligibleScoringEvidence,
            unavailableEvidenceIds: scoringDetail.unavailableEvidenceIds,
            diagnostics: scoringDetail.diagnostics,
            acquisition,
          },
          diagnostics: {
            blockingReviews: joinedReviews.map(projectReview),
            appliedReviewEvents: reviewEvents.appliedReviewEvents,
            auditReviewEvents: reviewEvents.auditReviewEvents,
            recomputeMarkers,
            reviewSummary: reviewSummaryFor(snapshot),
            lineageEvents: lineageFor(snapshot, candidateId),
            artifactStatuses: artifactStatusesFor(capabilities, [
              "canonical_evidence",
              "scoring_view",
              "screening_input_view",
              "review_queue",
              "review_events",
              "review_summary",
              "recompute_markers",
              "agent_trace",
              "provider_capabilities",
              "conflict_report",
            ]),
            contradictions: [...candidateDiagnostics, ...detailDiagnostics].map(cloneJson),
          },
          paperEvidence: paperEvidenceFor(snapshot, capabilities, candidateId),
        },
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
