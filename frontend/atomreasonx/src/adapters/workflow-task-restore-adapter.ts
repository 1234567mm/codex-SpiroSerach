import type {
  AtomReasonXWorkspaceState,
  HtlOperatorTaskSummary,
  OperatorTaskExecutionReport,
} from "../contracts/types";
import type { TauriCommandInvoke } from "./tauri-command-adapter";
import {
  DEFAULT_OPERATOR_TASK_LEDGER_PATH,
  OPERATOR_TASK_EXECUTION_SCHEMA_VERSION,
  validateOperatorTaskExecutionReport,
} from "./workflow-task-execution-adapter";

export const OPERATOR_TASK_RESTORE_SCHEMA_VERSION = "v35.operator_task_restore.v1" as const;
const OPERATOR_TASK_RESTORE_READ_SCOPE = "operator_task_snapshots_readonly" as const;
const RESTORE_FIELDS = new Set([
  "schema_version",
  "read_authorization_scope",
  "provider_cache_written",
  "local_backend_written",
  "scoring_written",
  "experiment_written",
  "restored_tasks",
]);
const RESTORED_TASK_FIELDS = new Set([
  "schema_version",
  "task_id",
  "action_type",
  "provider",
  "provider_scope",
  "status",
  "queue_scope",
  "declared_effects",
  "writes_authorized",
  "execution_started",
  "created_at",
  "config",
  "admission_status",
  "admission_hash",
  "ledger_path",
  "admission_source",
  "handoff_source",
  "execution_report",
]);
const OPTIONAL_RESTORED_TASK_FIELDS = new Set(["handoff_source"]);
const RESTORED_TASK_CONFIG_FIELDS = new Set([
  "transport",
  "runtime_writes",
  "config_source",
]);

export interface OperatorTaskRestoreReport {
  schema_version: typeof OPERATOR_TASK_RESTORE_SCHEMA_VERSION;
  read_authorization_scope: typeof OPERATOR_TASK_RESTORE_READ_SCOPE;
  provider_cache_written: false;
  local_backend_written: false;
  scoring_written: false;
  experiment_written: false;
  restored_tasks: HtlOperatorTaskSummary[];
}

export interface WorkflowTaskRestoreReader {
  restore(): Promise<OperatorTaskRestoreReport>;
}

export interface TauriWorkflowTaskRestoreReaderOptions {
  invoke?: TauriCommandInvoke;
}

export const createTauriWorkflowTaskRestoreReader = ({
  invoke = defaultTauriInvoke,
}: TauriWorkflowTaskRestoreReaderOptions = {}): WorkflowTaskRestoreReader => ({
  async restore() {
    const report = await invoke<unknown>("restore_workflow_tasks");
    return validateOperatorTaskRestoreReport(report);
  },
});

export const projectWorkflowTaskRestoreReport = (
  workspace: AtomReasonXWorkspaceState,
  report: OperatorTaskRestoreReport,
): AtomReasonXWorkspaceState => {
  let restored: OperatorTaskRestoreReport;
  try {
    restored = validateOperatorTaskRestoreReport(report);
  } catch {
    return workspace;
  }
  if (restored.restored_tasks.length === 0) {
    return workspace;
  }
  const restoredIDs = new Set(restored.restored_tasks.map(task => task.task_id));
  return {
    ...workspace,
    operator_tasks: [
      ...restored.restored_tasks.map(cloneTask),
      ...workspace.operator_tasks
        .filter(task => !restoredIDs.has(task.task_id))
        .map(cloneTask),
    ],
  };
};

export const validateOperatorTaskRestoreReport = (value: unknown): OperatorTaskRestoreReport => {
  if (!isRecord(value)) {
    throw new Error("workflow task restore report must be an object");
  }
  for (const key of Object.keys(value)) {
    if (!RESTORE_FIELDS.has(key)) {
      throw new Error(`workflow task restore report has unsupported field ${key}`);
    }
  }
  for (const field of RESTORE_FIELDS) {
    if (!(field in value)) {
      throw new Error(`workflow task restore report ${field} is required`);
    }
  }
  if (
    value.schema_version !== OPERATOR_TASK_RESTORE_SCHEMA_VERSION
    || value.read_authorization_scope !== OPERATOR_TASK_RESTORE_READ_SCOPE
    || value.provider_cache_written !== false
    || value.local_backend_written !== false
    || value.scoring_written !== false
    || value.experiment_written !== false
    || !Array.isArray(value.restored_tasks)
  ) {
    throw new Error("workflow task restore report metadata is invalid");
  }
  const restoredTasks = value.restored_tasks.map(validateRestoredTask);
  const blob = JSON.stringify(value);
  for (const forbidden of ["api_key", ["readonly", "token"].join("_"), "Bearer ", "mp-secret", "spiroctl.exe"]) {
    if (blob.includes(forbidden)) {
      throw new Error("workflow task restore report contains credential-shaped output");
    }
  }
  return {
    schema_version: OPERATOR_TASK_RESTORE_SCHEMA_VERSION,
    read_authorization_scope: OPERATOR_TASK_RESTORE_READ_SCOPE,
    provider_cache_written: false,
    local_backend_written: false,
    scoring_written: false,
    experiment_written: false,
    restored_tasks: restoredTasks,
  };
};

const validateRestoredTask = (value: unknown): HtlOperatorTaskSummary => {
  if (!isRecord(value)) {
    throw new Error("restored workflow task must be an object");
  }
  for (const key of Object.keys(value)) {
    if (!RESTORED_TASK_FIELDS.has(key)) {
      throw new Error(`restored workflow task has unsupported field ${key}`);
    }
  }
  for (const field of RESTORED_TASK_FIELDS) {
    if (OPTIONAL_RESTORED_TASK_FIELDS.has(field)) {
      continue;
    }
    if (!(field in value)) {
      throw new Error(`restored workflow task ${field} is required`);
    }
  }
  const config = value.config;
  if (!isRecord(config)) {
    throw new Error("restored workflow task metadata is invalid");
  }
  for (const key of Object.keys(config)) {
    if (!RESTORED_TASK_CONFIG_FIELDS.has(key)) {
      throw new Error(`restored workflow task config has unsupported field ${key}`);
    }
  }

  if (
    value.schema_version !== "v35.operator_task.v1"
    || !safeNomadTaskId(String(value.task_id))
    || value.action_type !== "start_nomad_sync"
    || value.provider !== "nomad_perla_psc"
    || value.provider_scope !== "source"
    || value.status !== "queued"
    || value.queue_scope !== "operator_local"
    || !equalStringArray(value.declared_effects, ["provider_sync_jobs"])
    || value.writes_authorized !== false
    || value.execution_started !== false
    || value.created_at !== null
    || config.transport !== "operator_task_queue"
    || config.runtime_writes !== false
    || config.config_source !== "workflow_command_allowlist"
    || value.admission_status !== "admitted"
    || !isSHA256(String(value.admission_hash))
    || value.ledger_path !== DEFAULT_OPERATOR_TASK_LEDGER_PATH
    || value.admission_source !== "operator_task_ledger"
    || (
      "handoff_source" in value
      && value.handoff_source !== "restored_snapshot"
    )
  ) {
    throw new Error("restored workflow task metadata is invalid");
  }
  const executionReport = validateOperatorTaskExecutionReport(value.execution_report);
  if (
    executionReport.schema_version !== OPERATOR_TASK_EXECUTION_SCHEMA_VERSION
    || executionReport.task_id !== value.task_id
    || executionReport.admission_hash !== value.admission_hash
  ) {
    throw new Error("restored workflow task execution report does not match admission");
  }
  return {
    schema_version: "v35.operator_task.v1",
    task_id: String(value.task_id),
    action_type: "start_nomad_sync",
    provider: "nomad_perla_psc",
    provider_scope: "source",
    status: "queued",
    queue_scope: "operator_local",
    declared_effects: ["provider_sync_jobs"],
    writes_authorized: false,
    execution_started: false,
    created_at: null,
    config: {
      transport: "operator_task_queue",
      runtime_writes: false,
      config_source: "workflow_command_allowlist",
    },
    admission_status: "admitted",
    admission_hash: String(value.admission_hash),
    ledger_path: DEFAULT_OPERATOR_TASK_LEDGER_PATH,
    admission_source: "operator_task_ledger",
    handoff_source: "restored_snapshot",
    execution_report: cloneExecutionReport(executionReport),
  };
};

const cloneTask = (task: HtlOperatorTaskSummary): HtlOperatorTaskSummary => ({
  ...task,
  declared_effects: [...task.declared_effects],
  config: { ...task.config },
  execution_report: task.execution_report ? cloneExecutionReport(task.execution_report) : undefined,
});

const cloneExecutionReport = (report: OperatorTaskExecutionReport): OperatorTaskExecutionReport => ({
  ...report,
  review_reasons: [...report.review_reasons],
});

const defaultTauriInvoke: TauriCommandInvoke = async (command, args) => {
  const invoke = (globalThis as {
    __TAURI__?: { core?: { invoke?: TauriCommandInvoke } };
  }).__TAURI__?.core?.invoke;
  if (typeof invoke !== "function") {
    throw new Error("Tauri workflow task restore bridge is unavailable");
  }
  return invoke(command, args);
};

const safeNomadTaskId = (value: string): boolean => {
  const prefix = "task-start_nomad_sync-";
  if (!value.startsWith(prefix)) {
    return false;
  }
  const suffix = value.slice(prefix.length);
  return /^[a-z0-9]{1,16}$/.test(suffix) && suffix !== "api_key";
};

const isSHA256 = (value: string): boolean => /^[a-f0-9]{64}$/.test(value);

const equalStringArray = (value: unknown, expected: string[]): boolean => (
  Array.isArray(value)
  && value.length === expected.length
  && value.every((item, index) => item === expected[index])
);

const isRecord = (value: unknown): value is Record<string, unknown> => (
  typeof value === "object" && value !== null && !Array.isArray(value)
);
