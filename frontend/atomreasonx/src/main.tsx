import React from "react";
import ReactDOM from "react-dom/client";
import { AppShell } from "./AppShell";
import { createLocalCommandAdapter, createWorkbenchCommandDispatcher } from "./adapters/command-adapter";
import fixture from "./fixtures/atomreasonx-ui-fixture.json";
import type { AtomReasonXWorkspaceState } from "./contracts/types";

const workspace = fixture as unknown as AtomReasonXWorkspaceState;
const commandAdapter = createLocalCommandAdapter(async () => ({
  status: "queued",
}));
const commandDispatcher = createWorkbenchCommandDispatcher(commandAdapter, () => ({
  expectedTargetVersion: String(workspace.source_settings.config_version),
}));

const AtomReasonXRoot: React.FC = () => {
  const [showSettings, setShowSettings] = React.useState(false);

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
