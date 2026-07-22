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

export interface AtomReasonXCommandEffectArtifact {
  kind: "config_command_effect";
  schema_version: string;
  action_type: string;
  provider: string | null;
  changed_fields: string[];
  validation_state: string;
  config_version: number;
}

export interface AtomReasonXCommandResult {
  schema_version: string;
  request_id: string;
  action_type: string;
  status: string;
  idempotency_key: string;
  actor_id: string;
  reason_code: string;
  message: string;
  output_artifacts: AtomReasonXCommandEffectArtifact[];
  audit: {
    idempotency_key: string;
    expected_source_version: string;
    declared_effects: string[];
    changed_fields: string[];
    validation_state: string;
    config_version: number;
    output_artifacts: AtomReasonXCommandEffectArtifact[];
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
  provider_kind: string;
  status: "active" | "experimental" | "quarantined" | "disabled";
  phase_status: "critical" | "useful" | "optional" | "optional_for_htl" | "blocked_until_validated" | "out_of_current_slice";
  key_requirement: "none" | "optional" | "required";
  htl_capability: string;
  automatic_acquisition: string;
  local_dataset: boolean;
  expected_fields: string[];
  provenance_fields: string[];
  cache_ttl_hours: number | null;
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
  telemetry: AtomReasonXTelemetryState;
  provider_status: AtomReasonXProviderStatus;
  settings: AtomReasonXSettingsState;
  source_coverage: HtlSourceCoverageMatrix;
  sync_jobs: HtlSyncJobSummary[];
  workflow: HtlWorkflowPreview;
  command_actions: HtlWorkbenchCommandAction[];
  _provisional: boolean;
}
