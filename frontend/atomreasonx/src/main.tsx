import React from "react";
import ReactDOM from "react-dom/client";
import { AppShell } from "./AppShell";
import { SettingsModal } from "./components/SettingsModal";
import { createWorkbenchCommandDispatcher } from "./adapters/command-adapter";
import { createRuntimeWorkbenchCommandAdapter } from "./adapters/tauri-command-adapter";
import { createRuntimeWorkbenchReadAdapter } from "./adapters/readonly-run-workbench-adapter";
import {
  buildReadonlyRunRecentOutputDirs,
  buildReadonlyRunOperatorConfig,
  normalizeReadonlyRunOutputDir,
  resolveConfiguredReadonlyOutputDir,
  resolveConfiguredReadonlyRecentOutputDirs,
} from "./adapters/readonly-run-operator-config";
import fixture from "./fixtures/atomreasonx-ui-fixture.json";
import { useWorkbenchWorkspaceStore } from "./stores/workspace-store";
import type { AtomReasonXWorkspaceState } from "./contracts/types";

const baseWorkspace = fixture as unknown as AtomReasonXWorkspaceState;
const commandAdapter = createRuntimeWorkbenchCommandAdapter();

const AtomReasonXRoot: React.FC = () => {
  const [showSettings, setShowSettings] = React.useState(false);
  const [readonlyOutputDir, setReadonlyOutputDir] = React.useState<string | null>(
    () => resolveConfiguredReadonlyOutputDir(),
  );
  const [readonlyRecentOutputDirs, setReadonlyRecentOutputDirs] = React.useState<string[]>(
    () => resolveConfiguredReadonlyRecentOutputDirs(),
  );
  const runtimeReadAdapter = React.useMemo(() => createRuntimeWorkbenchReadAdapter({
    baseWorkspace,
    readonlyOutputDir,
  }), [readonlyOutputDir]);
  const readonlyRunConfig = React.useMemo(
    () => buildReadonlyRunOperatorConfig(readonlyOutputDir),
    [readonlyOutputDir],
  );
  const readonlyRecentOutputDirEntries = React.useMemo(
    () => buildReadonlyRunRecentOutputDirs(readonlyRecentOutputDirs, readonlyOutputDir),
    [readonlyOutputDir, readonlyRecentOutputDirs],
  );
  const applyReadonlyRunOutputDir = React.useCallback((nextOutputDir: string | null) => {
    const normalized = normalizeReadonlyRunOutputDir(nextOutputDir);
    setReadonlyOutputDir(normalized);
    if (normalized) {
      setReadonlyRecentOutputDirs(previous => [normalized, ...previous]);
    }
  }, []);
  const workspaceState = useWorkbenchWorkspaceStore(runtimeReadAdapter.adapter);

  if (workspaceState.status === "loading") {
    return <div className="app-shell app-shell-loading">Loading AtomReasonX workspace</div>;
  }

  if (workspaceState.status === "error") {
    return (
      <div className="app-shell app-shell-error" style={{ padding: "16px" }}>
        <div role="alert">{workspaceState.message}</div>
        <button type="button" onClick={() => setShowSettings(true)}>
          Settings
        </button>
        {showSettings && (
          <SettingsModal
            categories={baseWorkspace.settings_categories}
            sourceSettings={baseWorkspace.source_settings}
            readonlyRunConfig={readonlyRunConfig}
            readonlyRecentOutputDirs={readonlyRecentOutputDirEntries}
            onApplyReadonlyRunOutputDir={applyReadonlyRunOutputDir}
            onClose={() => setShowSettings(false)}
          />
        )}
      </div>
    );
  }

  const workspace = workspaceState.workspace;
  const commandDispatcher = runtimeReadAdapter.readOnly
    ? undefined
    : createWorkbenchCommandDispatcher(commandAdapter, () => ({
      expectedTargetVersion: String(workspace.source_settings.config_version),
    }));

  return (
    <AppShell
      workspace={workspace}
      showSettings={showSettings}
      onOpenSettings={() => setShowSettings(true)}
      onCloseSettings={() => setShowSettings(false)}
      readonlyRunConfig={readonlyRunConfig}
      readonlyRecentOutputDirs={readonlyRecentOutputDirEntries}
      onApplyReadonlyRunOutputDir={applyReadonlyRunOutputDir}
      commandDispatcher={commandDispatcher}
    />
  );
};

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AtomReasonXRoot />
  </React.StrictMode>
);
