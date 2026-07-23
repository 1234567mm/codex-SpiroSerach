export type WorkbenchActorRole = "curator" | "reviewer" | "operator" | "admin";

export interface WorkbenchCommandRequest {
  schema_version: "v23.action_request.v1";
  action_type: string;
  actor: {
    actor_id: string;
    role: WorkbenchActorRole;
  };
  reason: string;
  idempotency_key: string;
  expected_source: {
    run_id: string;
    input_hash: string;
  };
  preconditions: {
    expected_target_version: string;
  };
  payload: Record<string, unknown>;
}

export interface WorkbenchCommandRequestOptions {
  actorId?: string;
  role?: WorkbenchActorRole;
  reason?: string;
  expectedRunId?: string;
  expectedInputHash?: string;
  expectedTargetVersion?: string;
  idempotencyKey?: string;
}

export interface WorkbenchCommandAdapter {
  submit(request: WorkbenchCommandRequest): Promise<unknown>;
}

export interface WorkbenchCommandDispatcher {
  submitAction(actionType: string, payload: Record<string, unknown>): Promise<unknown>;
}

export type WorkbenchCommandRequestOptionsFactory = () => WorkbenchCommandRequestOptions;

export const buildWorkbenchCommandRequest = (
  actionType: string,
  payload: Record<string, unknown>,
  options: WorkbenchCommandRequestOptions = {},
): WorkbenchCommandRequest => ({
  schema_version: "v23.action_request.v1",
  action_type: actionType,
  actor: {
    actor_id: options.actorId ?? "atomreasonx-operator",
    role: options.role ?? "operator",
  },
  reason: options.reason ?? "AtomReasonX settings action",
  idempotency_key: options.idempotencyKey ?? `atomx-${actionType}-${Date.now().toString(36)}`,
  expected_source: {
    run_id: options.expectedRunId ?? "config",
    input_hash: options.expectedInputHash ?? "config",
  },
  preconditions: {
    expected_target_version: options.expectedTargetVersion ?? "0",
  },
  payload,
});

export const createLocalCommandAdapter = (
  submitLocal: (request: WorkbenchCommandRequest) => Promise<unknown>,
): WorkbenchCommandAdapter => ({
  submit(request) {
    return submitLocal(request);
  },
});

export const createWorkbenchCommandDispatcher = (
  adapter: WorkbenchCommandAdapter,
  options: WorkbenchCommandRequestOptions | WorkbenchCommandRequestOptionsFactory = {},
): WorkbenchCommandDispatcher => ({
  submitAction(actionType, payload) {
    const resolvedOptions = typeof options === "function" ? options() : options;
    return adapter.submit(buildWorkbenchCommandRequest(actionType, payload, resolvedOptions));
  },
});
