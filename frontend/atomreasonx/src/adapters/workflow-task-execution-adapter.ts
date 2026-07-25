import type {
  AtomReasonXWorkspaceState,
  HtlOperatorTaskSummary,
  OperatorTaskExecutionReport,
} from "../contracts/types";
import type { TauriCommandInvoke } from "./tauri-command-adapter";

export const OPERATOR_TASK_EXECUTION_SCHEMA_VERSION = "v35.operator_task_execution.v1" as const;
export const OPERATOR_TASK_EXECUTION_REQUEST_SCHEMA_VERSION = "v35.operator_task_execution_request.v1" as const;
export const DEFAULT_OPERATOR_TASK_LEDGER_PATH = "data/lib/operator_tasks/operator-task-ledger.jsonl" as const;

const NOMAD_EXECUTION_TARGET_PREFIX = "data/lib/nomad_perla_psc/snapshots/run-" as const;
const EXECUTABLE_NOMAD_ACTION = "start_nomad_sync" as const;
const EXECUTABLE_NOMAD_PROVIDER = "nomad_perla_psc" as const;
const EXECUTION_ARCHIVE_STATUSES = new Set([
  "available",
  "empty",
  "unavailable",
  "rate_limited",
  "schema_unrecognized",
  "not_requested",
]);
const EXECUTION_REPORT_FIELDS = new Set([
  "schema_version",
  "task_id",
  "action_type",
  "provider",
  "admission_hash",
  "execution_status",
  "write_authorization_scope",
  "live_calls_authorized",
  "provider_cache_written",
  "local_backend_written",
  "scoring_written",
  "experiment_written",
  "started_at",
  "target_data_library_path",
  "source_manifest_path",
  "normalized_record_count",
  "provider_response_hash",
  "raw_search_hash",
  "raw_archive_hash",
  "archive_status",
  "review_required",
  "review_reasons",
]);

export interface WorkflowTaskExecutionRequest {
  schema_version: typeof OPERATOR_TASK_EXECUTION_REQUEST_SCHEMA_VERSION;
  task_id: string;
  ledger_path: typeof DEFAULT_OPERATOR_TASK_LEDGER_PATH;
  target_data_library_path: string;
  authorize_live_provider_calls: true;
  execution_contract: typeof OPERATOR_TASK_EXECUTION_SCHEMA_VERSION;
}

export interface WorkflowTaskExecutor {
  execute(task: HtlOperatorTaskSummary): Promise<OperatorTaskExecutionReport>;
}

export interface TauriWorkflowTaskExecutorOptions {
  invoke?: TauriCommandInvoke;
}

export const canExecuteWorkflowTask = (task: HtlOperatorTaskSummary): boolean => (
  task.schema_version === "v35.operator_task.v1"
  && task.action_type === EXECUTABLE_NOMAD_ACTION
  && task.provider === EXECUTABLE_NOMAD_PROVIDER
  && task.provider_scope === "source"
  && task.status === "queued"
  && task.queue_scope === "operator_local"
  && task.writes_authorized === false
  && task.execution_started === false
  && task.admission_status === "admitted"
  && task.admission_source === "operator_task_ledger"
  && task.ledger_path === DEFAULT_OPERATOR_TASK_LEDGER_PATH
  && task.execution_report === undefined
  && isSHA256(String(task.admission_hash ?? ""))
  && safeNomadTaskId(task.task_id)
  && equalStringArray(task.declared_effects, ["provider_sync_jobs"])
);

export const buildWorkflowTaskExecutionRequest = (
  task: HtlOperatorTaskSummary,
): WorkflowTaskExecutionRequest => {
  if (!canExecuteWorkflowTask(task)) {
    throw new Error("workflow task is not executable");
  }
  return {
    schema_version: OPERATOR_TASK_EXECUTION_REQUEST_SCHEMA_VERSION,
    task_id: task.task_id,
    ledger_path: DEFAULT_OPERATOR_TASK_LEDGER_PATH,
    target_data_library_path: `${NOMAD_EXECUTION_TARGET_PREFIX}${task.task_id}`,
    authorize_live_provider_calls: true,
    execution_contract: OPERATOR_TASK_EXECUTION_SCHEMA_VERSION,
  };
};

export const createTauriWorkflowTaskExecutor = ({
  invoke = defaultTauriInvoke,
}: TauriWorkflowTaskExecutorOptions = {}): WorkflowTaskExecutor => ({
  async execute(task) {
    const request = buildWorkflowTaskExecutionRequest(task);
    const report = await invoke<unknown>("execute_workflow_task", { request });
    return validateOperatorTaskExecutionReport(report, request);
  },
});

export const projectWorkflowTaskExecutionReport = (
  workspace: AtomReasonXWorkspaceState,
  report: OperatorTaskExecutionReport,
): AtomReasonXWorkspaceState => {
  if (!isProjectableExecutionReport(report)) {
    return workspace;
  }
  const taskIndex = workspace.operator_tasks.findIndex(task => (
    task.task_id === report.task_id
    && task.action_type === EXECUTABLE_NOMAD_ACTION
    && task.provider === EXECUTABLE_NOMAD_PROVIDER
    && task.admission_status === "admitted"
    && task.admission_source === "operator_task_ledger"
    && task.admission_hash === report.admission_hash
  ));
  if (taskIndex < 0 || workspace.operator_tasks[taskIndex].execution_report) {
    return workspace;
  }
  const nextTasks = workspace.operator_tasks.map((task, index) => {
    if (index !== taskIndex) {
      return { ...task, config: { ...task.config } };
    }
    return {
      ...task,
      config: { ...task.config },
      execution_report: cloneExecutionReport(report),
    };
  });
  return {
    ...workspace,
    operator_tasks: nextTasks,
  };
};

export const validateOperatorTaskExecutionReport = (
  value: unknown,
  request?: WorkflowTaskExecutionRequest,
): OperatorTaskExecutionReport => {
  if (!isRecord(value)) {
    throw new Error("workflow task execution report must be an object");
  }
  const report = value as Record<string, unknown>;
  for (const key of Object.keys(report)) {
    if (!EXECUTION_REPORT_FIELDS.has(key)) {
      throw new Error(`workflow task execution report has unsupported field ${key}`);
    }
  }
  for (const field of EXECUTION_REPORT_FIELDS) {
    if (!(field in report)) {
      throw new Error(`workflow task execution report ${field} is required`);
    }
  }
  if (report.schema_version !== OPERATOR_TASK_EXECUTION_SCHEMA_VERSION) {
    throw new Error("workflow task execution report schema_version is not supported");
  }
  if (report.action_type !== EXECUTABLE_NOMAD_ACTION || report.provider !== EXECUTABLE_NOMAD_PROVIDER) {
    throw new Error("workflow task execution report action/provider mismatch");
  }
  if (report.execution_status !== "source_snapshot_written" || report.write_authorization_scope !== "source_snapshot_only") {
    throw new Error("workflow task execution report status is not a source snapshot");
  }
  for (const field of [
    "live_calls_authorized",
  ]) {
    if (report[field] !== true) {
      throw new Error(`workflow task execution report ${field} must be true`);
    }
  }
  for (const field of [
    "provider_cache_written",
    "local_backend_written",
    "scoring_written",
    "experiment_written",
  ]) {
    if (report[field] !== false) {
      throw new Error(`workflow task execution report ${field} must be false`);
    }
  }
  for (const field of [
    "task_id",
    "admission_hash",
    "started_at",
    "target_data_library_path",
    "source_manifest_path",
    "provider_response_hash",
    "raw_search_hash",
    "raw_archive_hash",
    "archive_status",
  ]) {
    if (typeof report[field] !== "string" || report[field].trim() === "") {
      throw new Error(`workflow task execution report ${field} is required`);
    }
  }
  if (!safeNomadTaskId(String(report.task_id))) {
    throw new Error("workflow task execution report task_id is unsafe");
  }
  if (
    typeof report.normalized_record_count !== "number"
    || !Number.isInteger(report.normalized_record_count)
    || report.normalized_record_count < 0
  ) {
    throw new Error("workflow task execution report normalized_record_count must be a nonnegative integer");
  }
  if (
    typeof report.archive_status !== "string"
    || !EXECUTION_ARCHIVE_STATUSES.has(report.archive_status)
  ) {
    throw new Error("workflow task execution report archive_status is not supported");
  }
  if (
    typeof report.review_required !== "boolean"
    || !Array.isArray(report.review_reasons)
    || !report.review_reasons.every(item => typeof item === "string" && item.trim() !== "")
  ) {
    throw new Error("workflow task execution report review fields are invalid");
  }
  for (const field of ["admission_hash", "provider_response_hash", "raw_search_hash", "raw_archive_hash"]) {
    if (!isSHA256(String(report[field]))) {
      throw new Error(`workflow task execution report ${field} must be a sha256 hash`);
    }
  }
  const targetPath = String(report.target_data_library_path);
  const manifestPath = String(report.source_manifest_path);
  if (!safeNomadTargetPath(targetPath) || manifestPath !== `${targetPath}/source-manifest.json`) {
    throw new Error("workflow task execution report path is unsafe");
  }
  if (request) {
    if (report.task_id !== request.task_id || targetPath !== request.target_data_library_path) {
      throw new Error("workflow task execution report does not match request");
    }
  }
  const blob = JSON.stringify(report);
  for (const forbidden of ["api_key", ["readonly", "token"].join("_"), "Bearer ", "mp-secret", "SPIROCTL_PATH", "spiroctl.exe"]) {
    if (blob.includes(forbidden)) {
      throw new Error("workflow task execution report contains credential-shaped output");
    }
  }
  return {
    schema_version: OPERATOR_TASK_EXECUTION_SCHEMA_VERSION,
    task_id: String(report.task_id),
    action_type: EXECUTABLE_NOMAD_ACTION,
    provider: EXECUTABLE_NOMAD_PROVIDER,
    admission_hash: String(report.admission_hash),
    execution_status: "source_snapshot_written",
    write_authorization_scope: "source_snapshot_only",
    live_calls_authorized: true,
    provider_cache_written: false,
    local_backend_written: false,
    scoring_written: false,
    experiment_written: false,
    started_at: String(report.started_at),
    target_data_library_path: targetPath,
    source_manifest_path: manifestPath,
    normalized_record_count: report.normalized_record_count,
    provider_response_hash: String(report.provider_response_hash),
    raw_search_hash: String(report.raw_search_hash),
    raw_archive_hash: String(report.raw_archive_hash),
    archive_status: report.archive_status,
    review_required: report.review_required,
    review_reasons: [...report.review_reasons],
  } as OperatorTaskExecutionReport;
};

const cloneExecutionReport = (report: OperatorTaskExecutionReport): OperatorTaskExecutionReport => ({
  ...report,
  review_reasons: [...report.review_reasons],
});

const isProjectableExecutionReport = (report: OperatorTaskExecutionReport): boolean => {
  const blob = JSON.stringify(report);
  return (
    report.schema_version === OPERATOR_TASK_EXECUTION_SCHEMA_VERSION
    && report.action_type === EXECUTABLE_NOMAD_ACTION
    && report.provider === EXECUTABLE_NOMAD_PROVIDER
    && report.execution_status === "source_snapshot_written"
    && report.write_authorization_scope === "source_snapshot_only"
    && report.live_calls_authorized === true
    && report.provider_cache_written === false
    && report.local_backend_written === false
    && report.scoring_written === false
    && report.experiment_written === false
    && typeof report.started_at === "string"
    && report.started_at.trim() !== ""
    && typeof report.review_required === "boolean"
    && isSHA256(report.admission_hash)
    && isSHA256(report.provider_response_hash)
    && isSHA256(report.raw_search_hash)
    && isSHA256(report.raw_archive_hash)
    && safeNomadTaskId(report.task_id)
    && safeNomadTargetPath(report.target_data_library_path)
    && report.source_manifest_path === `${report.target_data_library_path}/source-manifest.json`
    && Number.isInteger(report.normalized_record_count)
    && report.normalized_record_count >= 0
    && EXECUTION_ARCHIVE_STATUSES.has(report.archive_status)
    && Array.isArray(report.review_reasons)
    && report.review_reasons.every(reason => typeof reason === "string" && reason.trim() !== "")
    && !blob.includes("api_key")
    && !blob.includes(["readonly", "token"].join("_"))
    && !blob.includes("Bearer ")
    && !blob.includes("mp-secret")
    && !blob.includes("SPIROCTL_PATH")
    && !blob.includes("spiroctl.exe")
  );
};

const defaultTauriInvoke: TauriCommandInvoke = async (command, args) => {
  const invoke = (globalThis as {
    __TAURI__?: { core?: { invoke?: TauriCommandInvoke } };
  }).__TAURI__?.core?.invoke;
  if (typeof invoke !== "function") {
    throw new Error("Tauri workflow task execution bridge is unavailable");
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

const safeNomadTargetPath = (value: string): boolean => (
  value.startsWith(NOMAD_EXECUTION_TARGET_PREFIX)
  && !value.includes("\\")
  && !value.includes(":")
  && !value.includes("//")
  && !value.includes("/../")
  && !value.endsWith("/..")
);

const equalStringArray = (value: unknown, expected: string[]): boolean => (
  Array.isArray(value)
  && value.length === expected.length
  && value.every((item, index) => item === expected[index])
);

const isRecord = (value: unknown): value is Record<string, unknown> => (
  typeof value === "object" && value !== null && !Array.isArray(value)
);
