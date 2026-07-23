import React from "react";
import ReactDOM from "react-dom/client";
import { AppShell } from "./AppShell";
import { createLocalCommandAdapter, createWorkbenchCommandDispatcher } from "./adapters/command-adapter";
import { createFixtureWorkbenchReadAdapter } from "./adapters/workbench-read-adapter";
import fixture from "./fixtures/atomreasonx-ui-fixture.json";
import { useWorkbenchWorkspaceStore } from "./stores/workspace-store";
import type { AtomReasonXWorkspaceState } from "./contracts/types";

const readAdapter = createFixtureWorkbenchReadAdapter(fixture as unknown as AtomReasonXWorkspaceState);
const commandAdapter = createLocalCommandAdapter(async () => ({
  status: "queued",
}));

const AtomReasonXRoot: React.FC = () => {
  const [showSettings, setShowSettings] = React.useState(false);
  const workspaceState = useWorkbenchWorkspaceStore(readAdapter);

  if (workspaceState.status === "loading") {
    return <div className="app-shell app-shell-loading">Loading AtomReasonX workspace</div>;
  }

  if (workspaceState.status === "error") {
    return <div className="app-shell app-shell-error" role="alert">{workspaceState.message}</div>;
  }

  const workspace = workspaceState.workspace;
  const commandDispatcher = createWorkbenchCommandDispatcher(commandAdapter, () => ({
    expectedTargetVersion: String(workspace.source_settings.config_version),
  }));

  return (
    <AppShell
      workspace={workspace}
      showSettings={showSettings}
      onOpenSettings={() => setShowSettings(true)}
      onCloseSettings={() => setShowSettings(false)}
      commandDispatcher={commandDispatcher}
    />
  );
};

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AtomReasonXRoot />
  </React.StrictMode>
);
