# Database Schema Plan

## Purpose

This document defines a practical PostgreSQL plus pgvector data model for an industrial Spiro-OMeTAD replacement mining system. PostgreSQL is the system of record for candidate hole transport layer materials, literature evidence, calculations, experiments, failure modes, and active-learning rounds. Neo4j is treated as a synchronized evidence graph, described in `docs/mcp-resources.md`.

## Design Principles

- Keep every scored candidate tied to an inspectable evidence chain.
- Store raw observations separately from normalized candidate summaries.
- Make calculations, experiments, and literature claims first-class evidence producers.
- Preserve model versions, extraction prompts, protocols, and quality flags for reproducibility.
- Use pgvector for semantic search over document chunks, claims, protocols, and failure notes.
- Avoid direct deletion of scientific evidence; prefer superseding records and audit events.

## PostgreSQL Extensions

Required extensions:

- `pgcrypto` for UUID generation.
- `vector` for embedding columns and ANN indexes.
- `pg_trgm` for fuzzy material, author, and supplier lookup.
- `btree_gin` for mixed scalar and JSONB filter indexes where needed.

Recommended schemas:

- `core`: projects, users, candidates, identifiers, controlled vocabularies.
- `literature`: sources, document chunks, extracted claims.
- `calc`: calculation runs and calculation results.
- `lab`: protocols, batches, samples, measurements, stability observations.
- `evidence`: evidence items, evidence links, candidate scorecards.
- `ml`: active-learning rounds, features, predictions, selections.
- `audit`: ingestion jobs, change events, graph sync outbox.

## Core Tables

### `core.projects`

Tracks mining campaigns, for example "Spiro-OMeTAD replacement v1".

Essential fields:

- `id uuid primary key`
- `slug text unique not null`
- `name text not null`
- `objective text not null`
- `target_device_stack text`
- `success_criteria jsonb not null`
- `status text not null check (status in ('draft','active','paused','archived'))`
- `created_at timestamptz not null`
- `updated_at timestamptz not null`

Indexes:

- Unique btree on `slug`.
- GIN on `success_criteria`.

### `core.candidates`

One record per HTL candidate or candidate family under consideration.

Essential fields:

- `id uuid primary key`
- `project_id uuid not null references core.projects(id)`
- `canonical_name text not null`
- `candidate_kind text not null check (candidate_kind in ('small_molecule','polymer','salt','dopant','blend','family'))`
- `target_role text not null default 'HTL'`
- `smiles text`
- `inchi_key text`
- `cas_number text`
- `material_class text`
- `replacement_hypothesis text`
- `synthesis_route_status text check (synthesis_route_status in ('unknown','commercial','literature','internal_route','not_feasible'))`
- `supplier_status text check (supplier_status in ('unknown','available','custom_order','synthesized_internal','restricted'))`
- `cost_usd_per_g numeric`
- `ip_status text`
- `toxicity_flag text check (toxicity_flag in ('unknown','low','medium','high','restricted'))`
- `readiness_level int check (readiness_level between 0 and 9)`
- `screening_status text not null check (screening_status in ('new','triaged','in_silico','selected_for_experiment','tested','rejected','promoted'))`
- `metadata jsonb not null default '{}'::jsonb`
- `created_at timestamptz not null`
- `updated_at timestamptz not null`

Indexes:

- Unique partial btree on `(project_id, inchi_key)` where `inchi_key is not null`.
- Btree on `(project_id, screening_status)`.
- Trigram GIN on `canonical_name`.
- GIN on `metadata`.

### `core.candidate_identifiers`

Stores synonyms and external database identifiers.

Essential fields:

- `id uuid primary key`
- `candidate_id uuid not null references core.candidates(id)`
- `identifier_type text not null`
- `identifier_value text not null`
- `source text`
- `is_primary boolean not null default false`

Indexes:

- Unique btree on `(identifier_type, identifier_value)`.
- Btree on `candidate_id`.
- Trigram GIN on `identifier_value`.

### `core.property_targets`

Controlled target windows used by triage and active learning.

Essential fields:

- `id uuid primary key`
- `project_id uuid not null references core.projects(id)`
- `property_name text not null`
- `preferred_direction text check (preferred_direction in ('minimize','maximize','target_range'))`
- `minimum_value numeric`
- `maximum_value numeric`
- `unit text not null`
- `weight numeric not null default 1.0`
- `rationale text not null`

Indexes:

- Unique btree on `(project_id, property_name)`.

Typical properties:

- `homo_ev`, `lumo_ev`, `band_gap_ev`, `hole_mobility_cm2_v_s`, `conductivity_s_cm`, `glass_transition_c`, `thermal_decomposition_c`, `solubility_mg_ml`, `water_contact_angle_deg`, `film_roughness_nm`, `pce_percent`, `voc_v`, `jsc_ma_cm2`, `fill_factor`, `t80_hours`, `dopant_free_score`, `cost_score`, `toxicity_score`.

## Literature Tables

### `literature.sources`

Bibliographic and provenance metadata for papers, patents, preprints, datasets, and web records.

Essential fields:

- `id uuid primary key`
- `source_kind text not null check (source_kind in ('paper','patent','preprint','dataset','web','internal_report','vendor_datasheet'))`
- `doi text`
- `patent_number text`
- `title text not null`
- `authors text[]`
- `venue text`
- `publication_year int`
- `url text`
- `pdf_uri text`
- `license text`
- `publisher text`
- `ingestion_status text not null`
- `credibility_score numeric check (credibility_score between 0 and 1)`
- `raw_metadata jsonb not null default '{}'::jsonb`
- `created_at timestamptz not null`

Indexes:

- Unique partial btree on `lower(doi)` where `doi is not null`.
- Unique partial btree on `patent_number` where `patent_number is not null`.
- GIN full-text index on `to_tsvector('english', title || ' ' || coalesce(venue,''))`.
- GIN on `authors`.

### `literature.document_chunks`

Chunked text used for search and claim grounding.

Essential fields:

- `id uuid primary key`
- `source_id uuid not null references literature.sources(id)`
- `section_label text`
- `page_start int`
- `page_end int`
- `chunk_index int not null`
- `chunk_text text not null`
- `chunk_hash text not null`
- `token_count int`
- `embedding_model text not null`
- `embedding vector(1536)`
- `created_at timestamptz not null`

Indexes:

- Unique btree on `(source_id, chunk_hash)`.
- Btree on `(source_id, chunk_index)`.
- HNSW vector index on `embedding vector_cosine_ops`.
- GIN full-text index on `to_tsvector('english', chunk_text)`.

If the embedding model changes dimensionality, create a new column such as `embedding_v2 vector(3072)` and backfill before removing the old column.

### `literature.claims`

Normalized scientific claims extracted from document chunks.

Essential fields:

- `id uuid primary key`
- `source_id uuid not null references literature.sources(id)`
- `chunk_id uuid references literature.document_chunks(id)`
- `candidate_id uuid references core.candidates(id)`
- `claim_type text not null check (claim_type in ('property','performance','stability','synthesis','failure','comparison','mechanism','safety','cost'))`
- `property_name text`
- `normalized_claim text not null`
- `raw_span text`
- `value_numeric numeric`
- `value_text text`
- `unit text`
- `conditions jsonb not null default '{}'::jsonb`
- `polarity text check (polarity in ('supports','refutes','neutral','mixed'))`
- `confidence numeric check (confidence between 0 and 1)`
- `extraction_model text not null`
- `extraction_prompt_hash text`
- `curation_status text not null check (curation_status in ('machine','reviewed','rejected','superseded'))`
- `created_at timestamptz not null`

Indexes:

- Btree on `(candidate_id, claim_type)`.
- Btree on `(property_name, value_numeric)`.
- GIN on `conditions`.
- HNSW vector index on optional `claim_embedding vector(1536)` if claim-level retrieval is enabled.

## Calculation Tables

### `calc.runs`

One calculation execution, including failed or partial runs.

Essential fields:

- `id uuid primary key`
- `candidate_id uuid not null references core.candidates(id)`
- `project_id uuid not null references core.projects(id)`
- `method text not null`
- `software_name text not null`
- `software_version text`
- `workflow_name text`
- `workflow_version text`
- `input_uri text not null`
- `output_uri text`
- `parameters jsonb not null`
- `environment_hash text`
- `reproducibility_hash text not null`
- `status text not null check (status in ('queued','running','succeeded','failed','invalidated'))`
- `failure_reason text`
- `started_at timestamptz`
- `completed_at timestamptz`
- `created_at timestamptz not null`

Indexes:

- Btree on `(project_id, status)`.
- Btree on `(candidate_id, method)`.
- Unique btree on `reproducibility_hash`.
- GIN on `parameters`.

### `calc.results`

Normalized outputs from calculation runs.

Essential fields:

- `id uuid primary key`
- `run_id uuid not null references calc.runs(id)`
- `candidate_id uuid not null references core.candidates(id)`
- `property_name text not null`
- `value_numeric numeric`
- `value_text text`
- `unit text`
- `uncertainty numeric`
- `conditions jsonb not null default '{}'::jsonb`
- `quality_flag text not null check (quality_flag in ('raw','accepted','suspect','rejected','superseded'))`
- `evidence_item_id uuid`
- `created_at timestamptz not null`

Indexes:

- Btree on `(candidate_id, property_name)`.
- Btree on `(property_name, value_numeric)`.
- GIN on `conditions`.

## Experiment Tables

### `lab.protocols`

Reusable experimental protocols and device-stack definitions.

Essential fields:

- `id uuid primary key`
- `project_id uuid not null references core.projects(id)`
- `protocol_name text not null`
- `protocol_version text not null`
- `device_architecture text not null`
- `substrate_stack text not null`
- `htl_process_window jsonb not null`
- `measurement_plan jsonb not null`
- `acceptance_criteria jsonb not null`
- `created_by text`
- `created_at timestamptz not null`

Indexes:

- Unique btree on `(project_id, protocol_name, protocol_version)`.
- GIN on `htl_process_window`.

### `lab.experiment_batches`

Groups devices, samples, or coupons made under the same execution context.

Essential fields:

- `id uuid primary key`
- `project_id uuid not null references core.projects(id)`
- `protocol_id uuid references lab.protocols(id)`
- `batch_code text not null`
- `operator text`
- `lab_location text`
- `started_at timestamptz`
- `completed_at timestamptz`
- `environment_conditions jsonb not null default '{}'::jsonb`
- `batch_notes text`
- `qc_status text not null check (qc_status in ('planned','in_progress','accepted','partial','rejected'))`

Indexes:

- Unique btree on `(project_id, batch_code)`.
- Btree on `(project_id, qc_status)`.

### `lab.samples`

Physical samples or devices using a candidate HTL.

Essential fields:

- `id uuid primary key`
- `batch_id uuid not null references lab.experiment_batches(id)`
- `candidate_id uuid not null references core.candidates(id)`
- `sample_code text not null`
- `sample_kind text not null check (sample_kind in ('film','device','coupon','solution'))`
- `formulation jsonb not null`
- `dopant_system jsonb not null default '{}'::jsonb`
- `deposition_method text`
- `annealing_profile jsonb`
- `encapsulation text`
- `device_area_cm2 numeric`
- `replicate_group text`
- `created_at timestamptz not null`

Indexes:

- Unique btree on `(batch_id, sample_code)`.
- Btree on `(candidate_id, sample_kind)`.
- GIN on `formulation`.

### `lab.measurements`

Atomic measured observations.

Essential fields:

- `id uuid primary key`
- `sample_id uuid not null references lab.samples(id)`
- `candidate_id uuid not null references core.candidates(id)`
- `measurement_type text not null`
- `property_name text not null`
- `value_numeric numeric`
- `value_text text`
- `unit text`
- `conditions jsonb not null default '{}'::jsonb`
- `instrument_id text`
- `raw_data_uri text`
- `analysis_method text`
- `operator text`
- `qc_status text not null check (qc_status in ('raw','accepted','suspect','rejected','superseded'))`
- `measured_at timestamptz not null`
- `created_at timestamptz not null`

Indexes:

- Btree on `(candidate_id, property_name, measured_at desc)`.
- Btree on `(sample_id, measurement_type)`.
- Btree on `(property_name, value_numeric)`.
- GIN on `conditions`.

For high-throughput labs, partition by `measured_at` month or by `project_id` once row counts exceed operational thresholds.

### `lab.stability_observations`

Time-series stability observations linked to a sample.

Essential fields:

- `id uuid primary key`
- `sample_id uuid not null references lab.samples(id)`
- `candidate_id uuid not null references core.candidates(id)`
- `stress_protocol text not null`
- `elapsed_hours numeric not null`
- `pce_retention_percent numeric`
- `voc_retention_percent numeric`
- `jsc_retention_percent numeric`
- `fill_factor_retention_percent numeric`
- `failure_observed boolean not null default false`
- `conditions jsonb not null default '{}'::jsonb`
- `measurement_id uuid references lab.measurements(id)`
- `created_at timestamptz not null`

Indexes:

- Btree on `(candidate_id, stress_protocol, elapsed_hours)`.
- Btree on `(sample_id, elapsed_hours)`.

## Failure Mode Tables

### `evidence.failure_modes`

Controlled taxonomy of failure mechanisms.

Essential fields:

- `id uuid primary key`
- `code text unique not null`
- `label text not null`
- `category text not null check (category in ('chemical','thermal','morphological','interfacial','processing','device','supply_chain','safety'))`
- `description text not null`
- `detection_methods text[]`
- `mitigation_patterns text[]`

Recommended initial codes:

- `HTL_OXIDATION`
- `DOPANT_MIGRATION`
- `PINHOLE_FORMATION`
- `POOR_ENERGY_ALIGNMENT`
- `LOW_HOLE_MOBILITY`
- `THERMAL_GLASS_TRANSITION`
- `MOISTURE_SENSITIVITY`
- `PEROVSKITE_INTERFACE_REACTION`
- `SYNTHESIS_SCALEUP_RISK`
- `TOXICITY_OR_RESTRICTION`

### `evidence.failure_observations`

Links a candidate, sample, claim, calculation, or measurement to a failure mode.

Essential fields:

- `id uuid primary key`
- `candidate_id uuid references core.candidates(id)`
- `sample_id uuid references lab.samples(id)`
- `failure_mode_id uuid not null references evidence.failure_modes(id)`
- `severity text not null check (severity in ('low','medium','high','critical'))`
- `diagnosis_confidence numeric check (diagnosis_confidence between 0 and 1)`
- `observation_summary text not null`
- `supporting_evidence_item_id uuid`
- `mitigation_status text check (mitigation_status in ('none','proposed','in_progress','validated','failed'))`
- `created_at timestamptz not null`

Indexes:

- Btree on `(candidate_id, failure_mode_id)`.
- Btree on `(failure_mode_id, severity)`.

## Evidence Chain Tables

### `evidence.items`

Canonical evidence units from literature, calculations, experiments, curation, or external databases.

Essential fields:

- `id uuid primary key`
- `project_id uuid not null references core.projects(id)`
- `candidate_id uuid references core.candidates(id)`
- `source_type text not null check (source_type in ('literature_claim','calculation_result','lab_measurement','stability_observation','failure_observation','curation','external_database','active_learning'))`
- `source_table text not null`
- `source_id uuid not null`
- `property_name text`
- `assertion text not null`
- `value_numeric numeric`
- `value_text text`
- `unit text`
- `conditions jsonb not null default '{}'::jsonb`
- `confidence numeric check (confidence between 0 and 1)`
- `quality_score numeric check (quality_score between 0 and 1)`
- `curation_status text not null check (curation_status in ('machine','reviewed','rejected','superseded'))`
- `created_at timestamptz not null`

Indexes:

- Btree on `(project_id, candidate_id)`.
- Btree on `(source_type, source_id)`.
- Btree on `(property_name, value_numeric)`.
- GIN on `conditions`.

### `evidence.links`

Directed edges between evidence items.

Essential fields:

- `id uuid primary key`
- `from_evidence_id uuid not null references evidence.items(id)`
- `to_evidence_id uuid not null references evidence.items(id)`
- `link_type text not null check (link_type in ('supports','refutes','derived_from','same_as','supersedes','explains','contradicts'))`
- `rationale text`
- `confidence numeric check (confidence between 0 and 1)`
- `created_by text`
- `created_at timestamptz not null`

Indexes:

- Unique btree on `(from_evidence_id, to_evidence_id, link_type)`.
- Btree on `(to_evidence_id, link_type)`.

### `evidence.candidate_scorecards`

Materialized candidate summaries for ranking and review.

Essential fields:

- `id uuid primary key`
- `project_id uuid not null references core.projects(id)`
- `candidate_id uuid not null references core.candidates(id)`
- `scorecard_version text not null`
- `overall_score numeric not null`
- `performance_score numeric`
- `stability_score numeric`
- `processability_score numeric`
- `cost_score numeric`
- `risk_score numeric`
- `evidence_balance jsonb not null`
- `top_positive_evidence_ids uuid[] not null default '{}'::uuid[]`
- `top_negative_evidence_ids uuid[] not null default '{}'::uuid[]`
- `recommendation text not null check (recommendation in ('reject','watch','calculate','experiment','promote'))`
- `created_at timestamptz not null`

Indexes:

- Unique btree on `(project_id, candidate_id, scorecard_version)`.
- Btree on `(project_id, recommendation, overall_score desc)`.
- GIN on `evidence_balance`.

## Active-Learning Tables

### `ml.feature_sets`

Feature definitions used for model training or selection.

Essential fields:

- `id uuid primary key`
- `project_id uuid not null references core.projects(id)`
- `name text not null`
- `version text not null`
- `feature_schema jsonb not null`
- `source_query_hash text not null`
- `created_at timestamptz not null`

Indexes:

- Unique btree on `(project_id, name, version)`.

### `ml.rounds`

One active-learning iteration.

Essential fields:

- `id uuid primary key`
- `project_id uuid not null references core.projects(id)`
- `round_number int not null`
- `objective text not null`
- `feature_set_id uuid references ml.feature_sets(id)`
- `model_name text not null`
- `model_version text not null`
- `acquisition_strategy text not null`
- `training_set_hash text not null`
- `candidate_pool_query_hash text not null`
- `status text not null check (status in ('planned','running','completed','cancelled'))`
- `started_at timestamptz`
- `completed_at timestamptz`
- `created_at timestamptz not null`

Indexes:

- Unique btree on `(project_id, round_number)`.
- Btree on `(project_id, status)`.

### `ml.predictions`

Per-candidate model outputs for a round.

Essential fields:

- `id uuid primary key`
- `round_id uuid not null references ml.rounds(id)`
- `candidate_id uuid not null references core.candidates(id)`
- `predicted_objective numeric`
- `prediction_interval_low numeric`
- `prediction_interval_high numeric`
- `uncertainty numeric`
- `expected_improvement numeric`
- `constraint_pass_probability numeric`
- `recommended_action text check (recommended_action in ('ignore','calculate','synthesize','experiment','promote'))`
- `model_explanation jsonb not null default '{}'::jsonb`
- `created_at timestamptz not null`

Indexes:

- Unique btree on `(round_id, candidate_id)`.
- Btree on `(round_id, expected_improvement desc)`.
- Btree on `(candidate_id, created_at desc)`.
- GIN on `model_explanation`.

### `ml.selections`

Human or automated decisions made from active-learning predictions.

Essential fields:

- `id uuid primary key`
- `round_id uuid not null references ml.rounds(id)`
- `candidate_id uuid not null references core.candidates(id)`
- `rank int not null`
- `selection_reason text not null`
- `decision text not null check (decision in ('selected','deferred','rejected','already_known'))`
- `linked_calculation_run_id uuid references calc.runs(id)`
- `linked_experiment_batch_id uuid references lab.experiment_batches(id)`
- `decision_by text`
- `created_at timestamptz not null`

Indexes:

- Unique btree on `(round_id, candidate_id)`.
- Btree on `(round_id, rank)`.

## Audit And Sync Tables

### `audit.ingestion_jobs`

Tracks document, calculation, experiment, and external database ingestion.

Essential fields:

- `id uuid primary key`
- `job_type text not null`
- `input_uri text`
- `status text not null check (status in ('queued','running','succeeded','failed','partial'))`
- `idempotency_key text not null`
- `records_created int not null default 0`
- `records_updated int not null default 0`
- `error_summary text`
- `started_at timestamptz`
- `completed_at timestamptz`

Indexes:

- Unique btree on `idempotency_key`.
- Btree on `(job_type, status)`.

### `audit.change_events`

Immutable audit log for scientific records.

Essential fields:

- `id uuid primary key`
- `actor text not null`
- `action text not null`
- `table_name text not null`
- `record_id uuid not null`
- `before_json jsonb`
- `after_json jsonb`
- `reason text`
- `created_at timestamptz not null`

Indexes:

- Btree on `(table_name, record_id, created_at desc)`.
- Btree on `(actor, created_at desc)`.

### `audit.graph_sync_outbox`

Outbox table for synchronizing PostgreSQL records into Neo4j.

Essential fields:

- `id uuid primary key`
- `event_type text not null check (event_type in ('upsert_node','upsert_edge','delete_edge','tombstone_node'))`
- `entity_type text not null`
- `entity_id uuid not null`
- `payload jsonb not null`
- `status text not null check (status in ('pending','processing','succeeded','failed'))`
- `attempt_count int not null default 0`
- `last_error text`
- `created_at timestamptz not null`
- `processed_at timestamptz`

Indexes:

- Btree on `(status, created_at)`.
- Unique partial btree on `(event_type, entity_type, entity_id)` where `status in ('pending','processing')`.

## Materialized Views

### `evidence.v_candidate_latest_properties`

Latest accepted values by candidate and property across literature, calculations, and lab results. Include columns for `candidate_id`, `property_name`, `best_value_numeric`, `unit`, `source_type`, `evidence_item_id`, `confidence`, `quality_score`, and `updated_at`.

Indexes:

- Unique btree on `(candidate_id, property_name)`.
- Btree on `(property_name, best_value_numeric)`.

### `evidence.v_candidate_evidence_balance`

Aggregates positive, negative, conflicting, and missing evidence counts by candidate.

Indexes:

- Unique btree on `candidate_id`.
- Btree on `net_support_score desc`.

### `ml.v_active_learning_training_matrix`

Feature matrix view joining latest properties, evidence quality, failure counts, and prior experimental labels.

Indexes:

- Unique btree on `(project_id, candidate_id)` if materialized.

## Data Integrity Requirements

- Every `calc.results`, `lab.measurements`, `lab.stability_observations`, `literature.claims`, and `evidence.failure_observations` row should have a matching `evidence.items` row.
- Evidence-producing writes should occur in a transaction with their `evidence.items` row and `audit.graph_sync_outbox` event.
- Scientific updates should supersede records rather than mutate accepted historical values when the interpretation changes.
- `source_table` plus `source_id` in `evidence.items` must point to an allowed evidence-producing table.
- All ingestion and write APIs must accept an `idempotency_key`.
- Candidate identity resolution must prefer `inchi_key`, then curated identifiers, then exact normalized name, then human review.

## Security And Access Requirements

Recommended database roles:

- `mcp_reader`: read-only access to curated tables, materialized views, and vector search functions.
- `mcp_writer`: limited insert/update access through stored procedures for candidates, evidence, and curation notes.
- `lab_writer`: write access to `lab` tables and associated evidence procedures.
- `calc_writer`: write access to `calc` tables and associated evidence procedures.
- `ml_writer`: write access to `ml` tables and associated evidence procedures.
- `graph_sync_worker`: read access to `audit.graph_sync_outbox` and update access to sync statuses.

Operational requirements:

- Enable row-level security by `project_id` if multiple industrial programs share one database.
- Store raw files in object storage and keep only immutable URIs plus hashes in PostgreSQL.
- Keep secrets and connection strings outside the database and MCP resource definitions.
- Log all MCP write operations to `audit.change_events`.

## Initial Implementation Order

1. Create PostgreSQL schemas, extensions, enum/check constraints, and core project/candidate tables.
2. Add literature ingestion tables and pgvector indexes.
3. Add calculation and lab evidence producers.
4. Add evidence item/link abstraction and scorecard materialized views.
5. Add active-learning tables.
6. Add graph sync outbox and Neo4j projection.
7. Expose read resources and constrained write tools through MCP.
