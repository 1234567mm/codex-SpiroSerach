import React from "react";
import ReactDOM from "react-dom/client";
import { AppShell } from "./AppShell";
import { buildWorkbenchCommandRequest, createLocalCommandAdapter } from "./adapters/command-adapter";
import fixture from "./fixtures/atomreasonx-ui-fixture.json";
import type { AtomReasonXWorkspaceState } from "./contracts/types";

const workspace = fixture as unknown as AtomReasonXWorkspaceState;
const commandAdapter = createLocalCommandAdapter(async () => ({
  status: "queued",
}));

const AtomReasonXRoot: React.FC = () => {
  const [showSettings, setShowSettings] = React.useState(false);

  const handleCommand = React.useCallback(
    (actionType: string, payload: Record<string, unknown>) => {
      const request = buildWorkbenchCommandRequest(actionType, payload, {
        expectedTargetVersion: String(workspace.source_settings.config_version),
      });
      void commandAdapter.submit(request);
    },
    [],
  );

  return (
    <AppShell
      workspace={workspace}
      showSettings={showSettings}
      onOpenSettings={() => setShowSettings(true)}
      onCloseSettings={() => setShowSettings(false)}
      onCommand={handleCommand}
    />
  );
};

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AtomReasonXRoot />
  </React.StrictMode>
);
