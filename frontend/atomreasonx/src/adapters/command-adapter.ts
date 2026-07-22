export interface WorkbenchCommandRequest {
  action_type: string;
  idempotency_key: string;
  actor_id: string;
  payload: Record<string, unknown>;
}

export interface WorkbenchCommandAdapter {
  submit(request: WorkbenchCommandRequest): Promise<unknown>;
}

export const createLocalCommandAdapter = (
  submitLocal: (request: WorkbenchCommandRequest) => Promise<unknown>,
): WorkbenchCommandAdapter => ({
  submit(request) {
    return submitLocal(request);
  },
});
