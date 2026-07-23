import type { AtomReasonXWorkspaceState } from "../contracts/types";

export type WorkbenchReadSurface = "workspace";

export interface WorkbenchReadAdapter {
  loadWorkspace(): Promise<AtomReasonXWorkspaceState>;
}

export interface WorkbenchReadTransport {
  request(surface: WorkbenchReadSurface): Promise<unknown>;
}

export const cloneWorkspaceState = (
  workspace: AtomReasonXWorkspaceState,
): AtomReasonXWorkspaceState => JSON.parse(JSON.stringify(workspace)) as AtomReasonXWorkspaceState;

export const createFixtureWorkbenchReadAdapter = (
  workspace: AtomReasonXWorkspaceState,
): WorkbenchReadAdapter => ({
  async loadWorkspace() {
    return cloneWorkspaceState(workspace);
  },
});

export const createNoopLocalWorkbenchTransport = (
  workspace: AtomReasonXWorkspaceState,
): WorkbenchReadTransport => ({
  async request(surface) {
    if (surface !== "workspace") {
      throw new Error(`unsupported workbench read surface: ${surface}`);
    }
    return cloneWorkspaceState(workspace);
  },
});

export const createTransportWorkbenchReadAdapter = (
  transport: WorkbenchReadTransport,
): WorkbenchReadAdapter => ({
  async loadWorkspace() {
    return cloneWorkspaceState(await transport.request("workspace") as AtomReasonXWorkspaceState);
  },
});
