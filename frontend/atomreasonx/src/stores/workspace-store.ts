import React from "react";
import type { WorkbenchReadAdapter } from "../adapters/workbench-read-adapter";
import type { AtomReasonXWorkspaceState } from "../contracts/types";

export type WorkbenchWorkspaceStoreState =
  | { status: "loading" }
  | { status: "ready"; workspace: AtomReasonXWorkspaceState }
  | { status: "error"; message: string };

export const createLoadingWorkbenchWorkspaceState = (): WorkbenchWorkspaceStoreState => ({
  status: "loading",
});

export const loadWorkbenchWorkspace = async (
  adapter: WorkbenchReadAdapter,
): Promise<WorkbenchWorkspaceStoreState> => {
  try {
    return {
      status: "ready",
      workspace: await adapter.loadWorkspace(),
    };
  } catch (error) {
    return {
      status: "error",
      message: error instanceof Error ? error.message : String(error),
    };
  }
};

export const useWorkbenchWorkspaceStore = (
  adapter: WorkbenchReadAdapter,
): WorkbenchWorkspaceStoreState => {
  const [state, setState] = React.useState<WorkbenchWorkspaceStoreState>(
    createLoadingWorkbenchWorkspaceState,
  );

  React.useEffect(() => {
    let active = true;
    setState(createLoadingWorkbenchWorkspaceState());
    void loadWorkbenchWorkspace(adapter).then((nextState) => {
      if (active) {
        setState(nextState);
      }
    });
    return () => {
      active = false;
      void adapter.dispose?.();
    };
  }, [adapter]);

  return state;
};
