import type { ConfigProviderScope, HtlOperatorTaskSummary } from "../contracts/types";

export const WORKFLOW_OPERATOR_TASK_SCHEMA_VERSION = "v35.operator_task.v1" as const;
export const WORKFLOW_OPERATOR_TASK_QUEUE_SCOPE = "operator_local" as const;

export interface WorkflowCommandTaskDefinition {
  action_type: string;
  provider: string | null;
  provider_scope: ConfigProviderScope;
  declared_effects: string[];
}

type WorkflowCommandTaskDefinitionSeed = {
  provider: string | null;
  provider_scope: ConfigProviderScope;
  declared_effects: string[];
};

export const WORKFLOW_COMMAND_TASK_DEFINITIONS: Record<string, WorkflowCommandTaskDefinitionSeed> = {
  start_nomad_sync: {
    provider: "nomad_perla_psc",
    provider_scope: "source",
    declared_effects: ["provider_sync_jobs"],
  },
  pause_nomad_sync: {
    provider: "nomad_perla_psc",
    provider_scope: "source",
    declared_effects: ["provider_sync_jobs"],
  },
  resume_nomad_sync: {
    provider: "nomad_perla_psc",
    provider_scope: "source",
    declared_effects: ["provider_sync_jobs"],
  },
  cancel_nomad_sync: {
    provider: "nomad_perla_psc",
    provider_scope: "source",
    declared_effects: ["provider_sync_jobs"],
  },
  import_doi_list: {
    provider: null,
    provider_scope: "source",
    declared_effects: ["paper_sources", "manual_acquisition_tasks"],
  },
  import_paper_group: {
    provider: null,
    provider_scope: "source",
    declared_effects: ["paper_groups", "paper_assets"],
  },
  import_hopv15_snapshot: {
    provider: "hopv15",
    provider_scope: "source",
    declared_effects: ["source_import_tasks"],
  },
  import_opv_db_snapshot: {
    provider: "opv_db",
    provider_scope: "source",
    declared_effects: ["source_import_tasks"],
  },
  import_pubchemqc_snapshot: {
    provider: "pubchemqc",
    provider_scope: "source",
    declared_effects: ["source_import_tasks"],
  },
  import_materials_cloud_archive_record: {
    provider: "materials_cloud",
    provider_scope: "source",
    declared_effects: ["source_import_tasks"],
  },
  refresh_pubchem_identity_cache: {
    provider: "pubchem",
    provider_scope: "source",
    declared_effects: ["provider_cache"],
  },
  run_parsing_job: {
    provider: null,
    provider_scope: "source",
    declared_effects: ["knowledge_chunks"],
  },
  run_extraction_job: {
    provider: null,
    provider_scope: "source",
    declared_effects: ["extracted_claims", "citation_links"],
  },
  run_htl_screening: {
    provider: null,
    provider_scope: "local",
    declared_effects: ["screening_result"],
  },
};

export const WORKFLOW_COMMAND_ACTION_TYPES = new Set(Object.keys(WORKFLOW_COMMAND_TASK_DEFINITIONS));

export const getWorkflowCommandTaskDefinition = (
  actionType: string,
): WorkflowCommandTaskDefinition | null => {
  const definition = WORKFLOW_COMMAND_TASK_DEFINITIONS[actionType];
  if (!definition) {
    return null;
  }
  return {
    action_type: actionType,
    provider: definition.provider,
    provider_scope: definition.provider_scope,
    declared_effects: [...definition.declared_effects],
  };
};

export const buildWorkflowTaskConfig = (): HtlOperatorTaskSummary["config"] => ({
  transport: "operator_task_queue",
  runtime_writes: false,
  config_source: "workflow_command_allowlist",
});
