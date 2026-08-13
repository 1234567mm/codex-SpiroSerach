/**
 * AtomReasonX frontend contract types.
 * These mirror the V33A sanitized contract shapes.
 * Fixture-first: fixtures must conform to these types until V33A contracts land.
 */

export type TelemetrySource =
  | "provider_reported"
  | "runtime_computed"
  | "estimated"
  | "unavailable"
  | "stale";

export interface TelemetryField {
  name: string;
  value: unknown;
  source: TelemetrySource;
}

export interface AtomReasonXTelemetryState {
  schema_version: string;
  fields: TelemetryField[];
}

export type ModelProviderKind = "private_relay" | "model_provider";
export type ModelProviderApiFormat = "openai_compatible";

export interface ProviderRegistryStatusEntry {
  provider: string;
  brand: string | null;
  priority: number;
  provider_kind: ModelProviderKind;
  api_format: ModelProviderApiFormat;
  requires_api_key: boolean;
  api_key_env: string | null;
  base_url: string | null;
  base_url_config_key: string | null;
  base_url_template: string | null;
  default_model: string | null;
  default_models: string[];
  default_model_config_key: string | null;
  supports: string[];
  docs_url: string | null;
  requires_workspace_id: boolean;
  supports_cache: boolean;
  context_window_tokens: number | null;
  usage_field_mapping: Record<string, string>;
  price_input_per_1m_tokens: number | null;
  price_output_per_1m_tokens: number | null;
  price_cache_read_per_1m_tokens: number | null;
}

export interface ProviderConfigStatusEntry {
  provider: string;
  brand: string | null;
  priority: number;
  provider_kind: ModelProviderKind;
  requires_api_key: boolean;
  has_api_key: boolean;
  key_fingerprint: string | null;
  validation_state: "missing" | "configured" | "validation_failed" | "validated";
  enabled: boolean;
  base_url: string | null;
  default_model: string | null;
  workspace_id: string | null;
}

export type ConfigProviderScope = "model" | "source";
export type SourceProviderKind =
  | "provider_api"
  | "local_dataset"
  | "schema_module"
  | "archive_import"
  | "local_vault"
  | "deferred_extractor";
export type SourceOperationalStatus = "active" | "experimental" | "quarantined" | "disabled";
export type SourceKeyRequirement = "none" | "optional" | "required";

export interface SourceConfigStatusEntry {
  provider_id: string;
  provider_scope: "source";
  provider_kind: SourceProviderKind;
  status: SourceOperationalStatus;
  v35_slice: string;
  acquisition_mode: string;
  distribution_policy: string;
  requires_api_key: boolean;
  key_requirement: SourceKeyRequirement;
  api_key_env: string | null;
  has_api_key: boolean;
  key_fingerprint: string | null;
  validation_state: "missing" | "configured" | "validation_failed" | "validated";
  data_library_path: string | null;
  execution_modes: string[];
  capabilities: string[];
}

export interface AtomReasonXSourceProfile {
  schema_version: "v35.atomreasonx_source_profile.v1";
  provider_id: string;
  display_name: string;
  provider_kind: SourceProviderKind;
  source_family: string;
  operational_status: SourceOperationalStatus;
  v35_slice: string;
  acquisition_mode: string;
  distribution_policy: string;
  license_hint: string;
  license_scope: string;
  trust_level: string;
  default_curation_status: string;
  base_url: string | null;
  source_url: string | null;
  data_library_path: string | null;
  dataset_doi: string | null;
  dataset_version: string | null;
  required_citation: string;
  last_verified_at: string | null;
  quarantine_state: "none" | "fixture_only" | "provider_quarantined" | "manual_import_required" | "deferred";
  go_migration_state: string;
  python_bridge_required: boolean;
  typescript_surface: string;
  requires_api_key: boolean;
  api_key_env: string | null;
}

export interface AtomReasonXProviderStatus {
  schema_version: string;
  producer_version: string;
  providers: ProviderRegistryStatusEntry[];
}

export interface AtomReasonXSettingsState {
  schema_version: string;
  producer_version: string;
  config_version: number;
  providers: ProviderConfigStatusEntry[];
}

export interface AtomReasonXSourceSettingsState {
  schema_version: string;
  producer_version: string;
  config_version: number;
  sources: SourceConfigStatusEntry[];
}

export interface SourceProviderConnectionProbeReport {
  schema_version: "v35.source_provider_connection_probe.v1";
  provider: "materials_project";
  status: "blocked" | "missing_api_key" | "provider_error" | "validated" | "validation_failed";
  validation_state: "missing" | "validated" | "validation_failed";
  read_only: true;
  live_enabled: boolean;
  requires_api_key: boolean;
  api_key_env: string;
  api_key_configured: boolean;
  key_source?: "environment" | "operator_secret";
  formula: string;
  source_url?: string;
  response_id?: string;
  resolution_status?: string;
  normalized_field_count: number;
  allowed_output_fields: string[];
  review_triggers: string[];
  error_code?: string;
  error_message?: string;
}

export interface OperatorTaskExecutionReport {
  schema_version: "v35.operator_task_execution.v1";
  task_id: string;
  action_type: "start_nomad_sync";
  provider: "nomad_perla_psc";
  admission_hash: string;
  execution_status: "source_snapshot_written";
  write_authorization_scope: "source_snapshot_only";
  live_calls_authorized: true;
  provider_cache_written: boolean;
  local_backend_written: boolean;
  scoring_written: boolean;
  experiment_written: boolean;
  started_at: string;
  target_data_library_path: string;
  source_manifest_path: string;
  normalized_record_count: number;
  provider_response_hash: string;
  raw_search_hash: string;
  raw_archive_hash: string;
  archive_status: "available" | "empty" | "unavailable" | "rate_limited" | "schema_unrecognized" | "not_requested";
  review_required: boolean;
  review_reasons: string[];
}

export interface AtomReasonXSourceProfilesState {
  schema_version: "v35.atomreasonx_source_profiles.v1";
  producer_version: string;
  profiles: AtomReasonXSourceProfile[];
}

export interface AtomReasonXCommandEffectArtifact {
  kind: "config_command_effect";
  schema_version: string;
  action_type: string;
  provider: string | null;
  provider_scope: "model" | "source";
  changed_fields: string[];
  validation_state: string;
  validation_mode?: "configuration_only" | "live_probe";
  provider_probe?: SourceProviderConnectionProbeReport;
  config_version: number;
}

export interface HtlOperatorTaskSummary {
  schema_version: "v35.operator_task.v1";
  task_id: string;
  action_type: string;
  provider: string | null;
  provider_scope: ConfigProviderScope;
  status: "queued";
  queue_scope: "operator_local";
  declared_effects: string[];
  writes_authorized: false;
  execution_started: false;
  created_at: string | null;
  config: Record<string, unknown>;
  admission_status?: "admitted";
  admission_hash?: string;
  ledger_path?: string;
  admission_source?: "operator_task_ledger";
  handoff_source?: "current_session_execution" | "restored_snapshot";
  execution_report?: OperatorTaskExecutionReport;
}

export interface AtomReasonXWorkflowCommandTaskArtifact extends HtlOperatorTaskSummary {
  kind: "workflow_command_task";
  provider_probe?: never;
}

export type AtomReasonXCommandOutputArtifact =
  | AtomReasonXCommandEffectArtifact
  | AtomReasonXWorkflowCommandTaskArtifact;

export interface AtomReasonXCommandResult {
  schema_version: string;
  request_id: string;
  action_type: string;
  status: string;
  idempotency_key: string;
  actor_id: string;
  reason_code: string;
  message: string;
  output_artifacts: AtomReasonXCommandOutputArtifact[];
  audit: {
    idempotency_key: string;
    expected_source_version: string;
    declared_effects: string[];
    changed_fields: string[];
    validation_state: string;
    config_version: number;
    output_artifacts: AtomReasonXCommandOutputArtifact[];
  };
}

export interface KnowledgeLibrarySummary {
  file_count: number;
  parsed_papers: number;
  si_attachments: number;
  material_records: number;
  extracted_claims: number;
  candidate_entities: number;
  provider_snapshots: number;
  parse_failures: number;
  index_freshness: string | null;
  blocked_review_items: number;
}

export interface HtlSourceCoverageRow {
  provider_id: string;
  provider_kind: SourceProviderKind;
  status: SourceOperationalStatus;
  phase_status: "critical" | "useful" | "optional" | "optional_for_htl" | "blocked_until_validated" | "out_of_current_slice";
  key_requirement: SourceKeyRequirement;
  htl_capability: string;
  automatic_acquisition: string;
  local_dataset: boolean;
  expected_fields: string[];
  provenance_fields: string[];
  cache_ttl_hours: number | null;
  blocking_review_count: number;
  review_blockers: string[];
}

export interface HtlSourceCoverageMatrix {
  schema_version: string;
  lane: "htl_only";
  sources: HtlSourceCoverageRow[];
}

export interface HtlSyncJobSummary {
  job_id: string;
  provider: string;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  config: Record<string, unknown>;
}

export interface HtlWorkflowStep {
  index: number;
  label: string;
}

export interface HtlWorkflowPreview {
  schema_version: string;
  lane: "htl_only";
  steps: HtlWorkflowStep[];
  target_fields: string[];
  gates: string[];
}

export interface HtlWorkbenchCommandAction {
  action_type: string;
  label: string;
  declared_effects: string[];
  enabled: boolean;
  provider_scope?: ConfigProviderScope;
  provider?: string;
  input_fields?: string[];
}

export interface SourceCatalogEntry {
  provider: string;
  display_name: string;
  source_family: string;
  acquisition_mode: string;
  operational_status: string;
  go_migration_state: string;
  data_library_path: string;
  fixture_status: string;
  local_snapshot_count: number;
}

export interface SourceCatalogFamily {
  family: string;
  entry_count: number;
  acquisition_modes: string[];
  entries: SourceCatalogEntry[];
}

export interface SourceCatalogSummary {
  schema_version: string;
  source_count: number;
  family_count: number;
  families: SourceCatalogFamily[];
}

export interface ScreeningCandidate {
  rank: number;
  record_id: string;
  material_id: string;
  homo_ev: number;
  lumo_ev: number;
  band_gap_ev: number;
  score: number;
  source_id: string;
  record: Record<string, unknown>;
}

export interface ScreeningResultState {
  schema_version: "v37.screening_result.v1";
  module_id: string;
  layer: string;
  source_ids: string[];
  window: {
    homo_min?: number;
    homo_max?: number;
    lumo_min?: number;
    lumo_max?: number;
    band_gap_min?: number;
    band_gap_max?: number;
  };
  stats: Record<string, number>;
  review_required: boolean;
  review_reasons: string[];
  candidates: ScreeningCandidate[];
}

export interface AtomReasonXWorkspaceState {
  brand: string;
  app: string;
  tagline: string;
  active_workspace: string;
  sidebar_entries: string[];
  right_inspector_tabs: string[];
  telemetry_fields: string[];
  settings_categories: string[];
  knowledge_library: KnowledgeLibrarySummary;
  source_catalog?: SourceCatalogSummary;
  screening_result?: ScreeningResultState;
  telemetry: AtomReasonXTelemetryState;
  provider_status: AtomReasonXProviderStatus;
  settings: AtomReasonXSettingsState;
  source_settings: AtomReasonXSourceSettingsState;
  source_profiles: AtomReasonXSourceProfilesState;
  source_coverage: HtlSourceCoverageMatrix;
  sync_jobs: HtlSyncJobSummary[];
  operator_tasks: HtlOperatorTaskSummary[];
  workflow: HtlWorkflowPreview;
  command_actions: HtlWorkbenchCommandAction[];
  _provisional: boolean;
}
