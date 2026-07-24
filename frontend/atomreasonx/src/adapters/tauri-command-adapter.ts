import type {
  AtomReasonXCommandResult,
} from "../contracts/types";
import type {
  WorkbenchCommandAdapter,
  WorkbenchCommandRequest,
} from "./command-adapter";

export type TauriCommandInvoke = <T>(command: string, args?: Record<string, unknown>) => Promise<T>;

export interface TauriConfigCommandAdapterOptions {
  invoke?: TauriCommandInvoke;
}

const CONFIG_COMMAND_ACTION_TYPES = new Set([
  "config_write",
  "key_rotate",
  "key_remove",
  "test_connection",
  "model_list_refresh",
]);

export const createTauriConfigCommandAdapter = ({
  invoke = defaultTauriInvoke,
}: TauriConfigCommandAdapterOptions = {}): WorkbenchCommandAdapter => ({
  async submit(request) {
    if (!CONFIG_COMMAND_ACTION_TYPES.has(request.action_type)) {
      return buildQueuedCommandResult(request);
    }
    const result = await invoke<unknown>("submit_config_command", { request });
    return validateCommandResult(result);
  },
});

export const createRuntimeWorkbenchCommandAdapter = (
  options: TauriConfigCommandAdapterOptions = {},
): WorkbenchCommandAdapter => createTauriConfigCommandAdapter(options);

export const buildQueuedCommandResult = (
  request: WorkbenchCommandRequest,
): AtomReasonXCommandResult => ({
  schema_version: "v23.action_result.v1",
  request_id: "queued-local",
  action_type: request.action_type,
  status: "queued",
  idempotency_key: request.idempotency_key,
  actor_id: request.actor.actor_id,
  reason_code: "transport_pending",
  message: "Command transport is pending for this action type.",
  output_artifacts: [],
  audit: {
    idempotency_key: request.idempotency_key,
    expected_source_version: request.preconditions.expected_target_version,
    declared_effects: Object.keys(request.payload),
    changed_fields: [],
    validation_state: "queued",
    config_version: 0,
    output_artifacts: [],
  },
});

export const validateCommandResult = (value: unknown): AtomReasonXCommandResult => {
  if (!isRecord(value)) {
    throw new Error("command result must be an object");
  }
  for (const field of [
    "schema_version",
    "request_id",
    "action_type",
    "status",
    "idempotency_key",
    "actor_id",
    "reason_code",
    "message",
  ]) {
    if (typeof value[field] !== "string" || value[field].trim() === "") {
      throw new Error(`command result ${field} is required`);
    }
  }
  if (!Array.isArray(value.output_artifacts)) {
    throw new Error("command result output_artifacts must be an array");
  }
  if (!isRecord(value.audit) || !Array.isArray(value.audit.output_artifacts)) {
    throw new Error("command result audit output_artifacts must be an array");
  }
  const blob = JSON.stringify(value);
  for (const forbidden of ["mp-secret", "sk-", "Bearer ", "api_key="]) {
    if (blob.includes(forbidden)) {
      throw new Error("command result contains credential-shaped output");
    }
  }
  return value as unknown as AtomReasonXCommandResult;
};

const defaultTauriInvoke: TauriCommandInvoke = async (command, args) => {
  const invoke = (globalThis as {
    __TAURI__?: { core?: { invoke?: TauriCommandInvoke } };
  }).__TAURI__?.core?.invoke;
  if (typeof invoke !== "function") {
    if (command === "submit_config_command") {
      throw new Error("Tauri command transport is unavailable");
    }
    throw new Error("Tauri invoke is unavailable");
  }
  return invoke(command, args);
};

const isRecord = (value: unknown): value is Record<string, unknown> => (
  typeof value === "object" && value !== null && !Array.isArray(value)
);
