# MCP And Knowledge Graph Resource Plan

## Purpose

This document defines the Neo4j evidence graph projection and MCP resource plan for the Spiro-OMeTAD replacement mining system. PostgreSQL remains the source of truth. Neo4j is a query-optimized projection for evidence-chain traversal, and MCP exposes safe resources and tools for assistants, analysts, and active-learning workflows.

## System Boundaries

- PostgreSQL stores canonical records, audit history, embeddings, and write transactions.
- pgvector supports semantic retrieval over literature chunks, claims, protocols, and failure notes.
- Neo4j stores derived nodes and relationships for explainable candidate reasoning.
- MCP servers should read from both PostgreSQL and Neo4j, but write only through constrained PostgreSQL procedures unless explicitly operating a graph sync worker.
- Neo4j writes should be driven from `audit.graph_sync_outbox`, not ad hoc assistant mutations.

## Neo4j Graph Model

### Node Labels

#### `Project`

Properties:

- `id`
- `slug`
- `name`
- `objective`
- `status`

Constraints and indexes:

- Unique constraint on `Project.id`.
- Index on `Project.slug`.

#### `Candidate`

Properties:

- `id`
- `project_id`
- `canonical_name`
- `candidate_kind`
- `material_class`
- `inchi_key`
- `screening_status`
- `readiness_level`
- `toxicity_flag`
- `cost_usd_per_g`

Constraints and indexes:

- Unique constraint on `Candidate.id`.
- Index on `Candidate.project_id`.
- Index on `Candidate.inchi_key`.
- Full-text index on `Candidate.canonical_name`.

#### `Identifier`

Properties:

- `id`
- `identifier_type`
- `identifier_value`
- `source`

Constraints and indexes:

- Unique constraint on `Identifier.id`.
- Index on `(identifier_type, identifier_value)`.

#### `LiteratureSource`

Properties:

- `id`
- `source_kind`
- `doi`
- `patent_number`
- `title`
- `venue`
- `publication_year`
- `url`
- `credibility_score`

Constraints and indexes:

- Unique constraint on `LiteratureSource.id`.
- Index on `LiteratureSource.doi`.
- Full-text index on `LiteratureSource.title`.

#### `DocumentChunk`

Properties:

- `id`
- `source_id`
- `section_label`
- `page_start`
- `page_end`
- `chunk_index`
- `chunk_hash`
- `text_preview`

Constraints and indexes:

- Unique constraint on `DocumentChunk.id`.
- Index on `DocumentChunk.source_id`.

Full chunk text and embeddings remain in PostgreSQL to avoid duplicating large vector payloads in Neo4j.

#### `Claim`

Properties:

- `id`
- `claim_type`
- `property_name`
- `normalized_claim`
- `value_numeric`
- `value_text`
- `unit`
- `polarity`
- `confidence`
- `curation_status`

Constraints and indexes:

- Unique constraint on `Claim.id`.
- Index on `Claim.claim_type`.
- Index on `Claim.property_name`.

#### `CalculationRun`

Properties:

- `id`
- `candidate_id`
- `method`
- `software_name`
- `software_version`
- `workflow_name`
- `workflow_version`
- `status`
- `reproducibility_hash`

Constraints and indexes:

- Unique constraint on `CalculationRun.id`.
- Index on `CalculationRun.reproducibility_hash`.
- Index on `CalculationRun.status`.

#### `CalculationResult`

Properties:

- `id`
- `property_name`
- `value_numeric`
- `value_text`
- `unit`
- `quality_flag`

Constraints and indexes:

- Unique constraint on `CalculationResult.id`.
- Index on `CalculationResult.property_name`.

#### `ExperimentBatch`

Properties:

- `id`
- `project_id`
- `batch_code`
- `protocol_name`
- `protocol_version`
- `qc_status`
- `started_at`
- `completed_at`

Constraints and indexes:

- Unique constraint on `ExperimentBatch.id`.
- Index on `ExperimentBatch.batch_code`.

#### `Sample`

Properties:

- `id`
- `sample_code`
- `sample_kind`
- `candidate_id`
- `deposition_method`
- `encapsulation`
- `replicate_group`

Constraints and indexes:

- Unique constraint on `Sample.id`.
- Index on `Sample.candidate_id`.

#### `Measurement`

Properties:

- `id`
- `measurement_type`
- `property_name`
- `value_numeric`
- `value_text`
- `unit`
- `qc_status`
- `measured_at`

Constraints and indexes:

- Unique constraint on `Measurement.id`.
- Index on `Measurement.property_name`.
- Index on `Measurement.qc_status`.

#### `StabilityObservation`

Properties:

- `id`
- `stress_protocol`
- `elapsed_hours`
- `pce_retention_percent`
- `failure_observed`

Constraints and indexes:

- Unique constraint on `StabilityObservation.id`.
- Index on `StabilityObservation.stress_protocol`.

#### `FailureMode`

Properties:

- `id`
- `code`
- `label`
- `category`
- `description`

Constraints and indexes:

- Unique constraint on `FailureMode.id`.
- Unique constraint on `FailureMode.code`.
- Index on `FailureMode.category`.

#### `EvidenceItem`

Properties:

- `id`
- `project_id`
- `source_type`
- `source_table`
- `source_id`
- `property_name`
- `assertion`
- `value_numeric`
- `value_text`
- `unit`
- `confidence`
- `quality_score`
- `curation_status`

Constraints and indexes:

- Unique constraint on `EvidenceItem.id`.
- Index on `EvidenceItem.project_id`.
- Index on `EvidenceItem.source_type`.
- Index on `EvidenceItem.property_name`.

#### `ActiveLearningRound`

Properties:

- `id`
- `project_id`
- `round_number`
- `objective`
- `model_name`
- `model_version`
- `acquisition_strategy`
- `status`

Constraints and indexes:

- Unique constraint on `ActiveLearningRound.id`.
- Index on `(project_id, round_number)`.

#### `Prediction`

Properties:

- `id`
- `round_id`
- `candidate_id`
- `predicted_objective`
- `uncertainty`
- `expected_improvement`
- `constraint_pass_probability`
- `recommended_action`

Constraints and indexes:

- Unique constraint on `Prediction.id`.
- Index on `Prediction.round_id`.
- Index on `Prediction.expected_improvement`.

### Relationship Types

Core relationships:

- `(Project)-[:CONTAINS]->(Candidate)`
- `(Candidate)-[:HAS_IDENTIFIER]->(Identifier)`
- `(Candidate)-[:MENTIONED_IN]->(LiteratureSource)`
- `(LiteratureSource)-[:HAS_CHUNK]->(DocumentChunk)`
- `(DocumentChunk)-[:GROUNDS]->(Claim)`
- `(Claim)-[:ABOUT]->(Candidate)`
- `(Claim)-[:PRODUCES_EVIDENCE]->(EvidenceItem)`
- `(CalculationRun)-[:RUN_FOR]->(Candidate)`
- `(CalculationRun)-[:OUTPUTS]->(CalculationResult)`
- `(CalculationResult)-[:PRODUCES_EVIDENCE]->(EvidenceItem)`
- `(ExperimentBatch)-[:HAS_SAMPLE]->(Sample)`
- `(Sample)-[:USES_HTL]->(Candidate)`
- `(Sample)-[:HAS_MEASUREMENT]->(Measurement)`
- `(Measurement)-[:PRODUCES_EVIDENCE]->(EvidenceItem)`
- `(Sample)-[:HAS_STABILITY_OBSERVATION]->(StabilityObservation)`
- `(StabilityObservation)-[:PRODUCES_EVIDENCE]->(EvidenceItem)`
- `(EvidenceItem)-[:SUPPORTS]->(EvidenceItem)`
- `(EvidenceItem)-[:REFUTES]->(EvidenceItem)`
- `(EvidenceItem)-[:DERIVED_FROM]->(EvidenceItem)`
- `(EvidenceItem)-[:CONTRADICTS]->(EvidenceItem)`
- `(EvidenceItem)-[:INDICATES_FAILURE]->(FailureMode)`
- `(Candidate)-[:HAS_FAILURE_RISK]->(FailureMode)`
- `(ActiveLearningRound)-[:PREDICTED]->(Prediction)`
- `(Prediction)-[:RANKS]->(Candidate)`
- `(Prediction)-[:SELECTED_FOR]->(ExperimentBatch)`

Important relationship properties:

- `confidence`
- `rationale`
- `created_at`
- `source_evidence_id`
- `sync_event_id`

## Graph Query Patterns

Candidate explanation:

- Start from `Candidate`.
- Traverse to `EvidenceItem` through claims, calculation results, measurements, and failure observations.
- Return top supporting, refuting, and contradictory evidence by `quality_score` and `confidence`.

Failure mode investigation:

- Start from `FailureMode`.
- Traverse incoming `INDICATES_FAILURE` and `HAS_FAILURE_RISK`.
- Group by candidate class, protocol, stress condition, and evidence source type.

Active-learning rationale:

- Start from `ActiveLearningRound`.
- Traverse `PREDICTED` to `Prediction` to `Candidate`.
- Expand candidate evidence and failure risks to explain selection or rejection.

Literature trace:

- Start from `Claim` or `EvidenceItem`.
- Traverse back to `DocumentChunk` and `LiteratureSource`.
- Fetch full chunk text from PostgreSQL only when needed.

## MCP Resource Names

Resource URIs should be stable, versioned where needed, and read-optimized. Suggested resource namespace: `spiro-search`.

### PostgreSQL Resources

`resource://spiro-search/postgres/schema`

- Returns table, view, and stored procedure metadata exposed to MCP.
- Must not include credentials.

`resource://spiro-search/project/{project_id}/summary`

- Returns project goals, target property windows, counts by candidate status, evidence coverage, and active round status.

`resource://spiro-search/candidate/{candidate_id}/profile`

- Returns canonical candidate identity, identifiers, latest property values, scorecard, failure risks, and readiness status.

`resource://spiro-search/candidate/{candidate_id}/evidence-chain`

- Returns evidence items, evidence links, source summaries, quality flags, and curation status.
- Should support query parameters: `source_type`, `property_name`, `min_quality`, `include_rejected`.

`resource://spiro-search/candidate/{candidate_id}/properties`

- Returns normalized latest properties plus provenance.

`resource://spiro-search/literature/source/{source_id}`

- Returns bibliographic metadata and chunk inventory.

`resource://spiro-search/literature/chunk/{chunk_id}`

- Returns chunk text, location metadata, linked claims, and source citation.

`resource://spiro-search/calculation/run/{run_id}`

- Returns calculation metadata, parameters, result rows, quality flags, and linked evidence.

`resource://spiro-search/experiment/batch/{batch_id}`

- Returns protocol, samples, measurements, stability observations, QC status, and linked evidence.

`resource://spiro-search/failure-mode/{code}`

- Returns taxonomy entry, affected candidates, supporting observations, and mitigation patterns.

`resource://spiro-search/active-learning/round/{round_id}`

- Returns model metadata, selected feature set, ranked predictions, selections, and downstream calculations or experiments.

### Neo4j Resources

`resource://spiro-search/graph/candidate/{candidate_id}/neighborhood`

- Returns a bounded graph neighborhood.
- Query parameters: `depth`, `relationship_types`, `min_confidence`, `limit`.

`resource://spiro-search/graph/candidate/{candidate_id}/explanation`

- Returns a graph-shaped explanation with supporting, refuting, derived, and contradictory evidence paths.

`resource://spiro-search/graph/failure-mode/{code}/candidates`

- Returns candidates connected to a failure mode with path summaries.

`resource://spiro-search/graph/claim/{claim_id}/lineage`

- Returns source chunk, literature source, evidence item, downstream scorecard, and conflicts.

`resource://spiro-search/graph/active-learning/round/{round_id}/rationale`

- Returns selected candidates, prediction nodes, expected improvement, and supporting evidence paths.

## MCP Tools

MCP tools should be explicit, idempotent, and narrow. Read tools may query PostgreSQL, pgvector, and Neo4j. Write tools should call PostgreSQL stored procedures that create audit events and graph sync outbox records.

### Read Tools

`search_literature_chunks`

- Inputs: `query`, `project_id`, `candidate_id`, `source_kind`, `year_min`, `year_max`, `top_k`.
- Uses pgvector plus full-text ranking.
- Returns chunks with source citation, similarity score, and linked claims.

`search_candidates`

- Inputs: `project_id`, `text_query`, `property_filters`, `status`, `top_k`.
- Uses candidate identifiers, latest properties, scorecards, and optional vector-backed claim matching.

`get_candidate_evidence_chain`

- Inputs: `candidate_id`, `property_name`, `include_graph_paths`, `min_quality`.
- Returns evidence items and optional Neo4j path summaries.

`compare_candidates`

- Inputs: `candidate_ids`, `property_names`, `include_failure_modes`.
- Returns side-by-side properties, scorecards, and evidence confidence.

`explain_failure_mode`

- Inputs: `failure_mode_code`, `project_id`, `candidate_id`.
- Returns graph paths and supporting evidence.

`get_active_learning_shortlist`

- Inputs: `round_id`, `limit`, `recommended_action`.
- Returns predictions, uncertainty, expected improvement, and selection status.

### Write Tools

`upsert_candidate`

- Inputs: project, canonical identity, structure identifiers, material class, metadata, idempotency key.
- Requirements: perform candidate identity resolution and write audit event.

`attach_literature_claim`

- Inputs: source, chunk, normalized claim, optional candidate link, confidence, extraction metadata, idempotency key.
- Requirements: create or update claim, create evidence item when claim is accepted or machine-readable, enqueue graph sync.

`record_calculation_run`

- Inputs: candidate, method, software, parameters, input/output URIs, status, result list, idempotency key.
- Requirements: compute or accept reproducibility hash, create result evidence items for accepted outputs.

`record_experiment_batch`

- Inputs: protocol, batch metadata, sample list, measurement list, stability observations, idempotency key.
- Requirements: create batch, samples, measurements, evidence items, and audit rows in one transaction.

`record_failure_observation`

- Inputs: candidate or sample, failure mode code, severity, confidence, supporting evidence, mitigation status, idempotency key.
- Requirements: link to existing taxonomy or reject unknown failure code unless caller has curation permission.

`submit_active_learning_round`

- Inputs: project, objective, feature set, model metadata, candidate pool hash, prediction list, idempotency key.
- Requirements: persist predictions and evidence items summarizing model recommendations.

`select_active_learning_candidates`

- Inputs: round, candidate decisions, ranks, reasons, linked calculation or experiment target, idempotency key.
- Requirements: preserve human decision context and update candidate screening status.

`curate_evidence`

- Inputs: evidence item, new curation status, quality score, reason, optional superseding evidence.
- Requirements: never hard-delete; create audit event and graph sync event.

## Integration Requirements

### Connection And Permissions

- MCP servers must use separate database users for read-only and write-capable operations.
- Write tools must use stored procedures or service-layer commands, not arbitrary SQL from the assistant.
- Neo4j credentials should be read-only for normal MCP resources.
- The graph sync worker may have Neo4j write access, but it should not expose general graph write operations to assistants.
- All secrets must come from environment or secret manager references, never from resource payloads.

### Transactionality

- Evidence-producing writes must create the source row, `evidence.items` row, `audit.change_events` row, and `audit.graph_sync_outbox` event in the same PostgreSQL transaction.
- MCP write tools must accept an `idempotency_key` and return the existing record on retry.
- Partial ingestion should report failed records in `audit.ingestion_jobs` rather than leaving untracked side effects.

### Retrieval Quality

- Vector searches must return embedding model name, distance score, source citation, and chunk location.
- Candidate ranking responses must include missing evidence and contradictory evidence, not only positive evidence.
- MCP resources should expose confidence and quality scores separately.
- Assistant-facing summaries must include stable IDs for follow-up inspection.

### Graph Sync

- PostgreSQL emits outbox events for node and edge projections.
- A sync worker translates outbox payloads into Cypher `MERGE` operations.
- Sync should be idempotent by node `id` and relationship `(from_id, to_id, type, source_evidence_id)`.
- Failed sync events stay in `audit.graph_sync_outbox` with `attempt_count` and `last_error`.
- Neo4j nodes should include `postgres_table`, `postgres_id`, and `updated_at` projection metadata where useful.

### Observability

- Record MCP tool name, actor, request ID, idempotency key, affected table, affected record ID, and latency.
- Track vector query latency and top-k result quality feedback.
- Track graph sync lag from outbox `created_at` to `processed_at`.
- Emit alerts for failed graph sync events, repeated idempotency conflicts, and write attempts outside stored procedures.

### Safety And Governance

- Preserve raw literature chunks and extracted claims even when claims are rejected; mark curation status instead.
- Keep copyrighted source text access bounded to retrieved chunks and citations.
- Require curation permission before promoting a machine-extracted claim to reviewed status.
- Require lab or calculation provenance before a candidate can be marked `promoted`.
- Separate industrial confidential notes from public literature metadata through project-level access control.

## Recommended MCP Response Shapes

Candidate profile responses should include:

- `candidate`
- `latest_properties`
- `scorecard`
- `top_supporting_evidence`
- `top_refuting_evidence`
- `failure_risks`
- `active_learning_status`
- `resource_links`

Evidence chain responses should include:

- `evidence_items`
- `evidence_links`
- `graph_paths`
- `source_citations`
- `conflicts`
- `missing_evidence`

Active-learning round responses should include:

- `round`
- `feature_set`
- `prediction_summary`
- `ranked_candidates`
- `selected_candidates`
- `downstream_work`
- `model_limitations`

## Minimum Viable Resource Set

For the first operational release, expose these resources and tools only:

- `resource://spiro-search/project/{project_id}/summary`
- `resource://spiro-search/candidate/{candidate_id}/profile`
- `resource://spiro-search/candidate/{candidate_id}/evidence-chain`
- `resource://spiro-search/literature/chunk/{chunk_id}`
- `resource://spiro-search/active-learning/round/{round_id}`
- `search_literature_chunks`
- `search_candidates`
- `get_candidate_evidence_chain`
- `upsert_candidate`
- `attach_literature_claim`
- `record_calculation_run`
- `record_experiment_batch`
- `submit_active_learning_round`

Defer broad graph exploration, curation writes, and failure-mode management until authentication, audit review, and graph sync monitoring are in place.
