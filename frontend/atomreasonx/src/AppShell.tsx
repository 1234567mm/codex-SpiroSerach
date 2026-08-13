import React from "react";
import { LeftSidebar } from "./components/LeftSidebar";
import { BottomTelemetryBar } from "./components/BottomTelemetryBar";
import { SettingsModal } from "./components/SettingsModal";
import { DatabaseView } from "./components/DatabaseView";
import { KnowledgeLibraryView } from "./components/KnowledgeLibraryView";
import { SourceCategoriesView } from "./components/SourceCategoriesView";
import { WorkflowView } from "./components/WorkflowView";
import { InspectorPanel } from "./components/InspectorPanel";
import type { WorkbenchCommandDispatcher } from "./adapters/command-adapter";
import type { WorkflowTaskExecutor } from "./adapters/workflow-task-execution-adapter";
import type {
  ReadonlyRunOperatorConfig,
  ReadonlyRunRecentOutputDir,
} from "./adapters/readonly-run-operator-config";
import type { AtomReasonXWorkspaceState, OperatorTaskExecutionReport } from "./contracts/types";

const RIGHT_INSPECTOR_TABS = ["Overview", "Files"];

const SETTINGS_CATEGORIES = [
  "General", "Models", "Agents", "MCP And Tools", "Remote SSH", "Skills",
  "Subagents", "Plugins", "Memory", "Hooks", "Diagnostics", "Shortcuts",
  "Permissions", "Sandbox", "Network", "Retrieval", "File Parsing",
  "Knowledge Library", "Data Sources", "Citation", "Cost Guardrails", "Telemetry source policy",
];

export const AppShell: React.FC<{
  workspace: AtomReasonXWorkspaceState;
  onOpenSettings?: () => void;
  showSettings?: boolean;
  onCloseSettings?: () => void;
  readonlyRunConfig?: ReadonlyRunOperatorConfig;
  readonlyRecentOutputDirs?: ReadonlyRunRecentOutputDir[];
  onApplyReadonlyRunOutputDir?: (outputDir: string | null) => void;
  commandDispatcher?: WorkbenchCommandDispatcher;
  workflowTaskExecutor?: WorkflowTaskExecutor;
  workflowProjectionKey?: string;
  onWorkflowTaskExecuted?: (report: OperatorTaskExecutionReport, projectionKey?: string) => void;
}> = ({
  workspace,
  onOpenSettings,
  showSettings,
  onCloseSettings,
  readonlyRunConfig,
  readonlyRecentOutputDirs,
  onApplyReadonlyRunOutputDir,
  commandDispatcher,
  workflowTaskExecutor,
  workflowProjectionKey,
  onWorkflowTaskExecuted,
}) => {
  return (
    <div className="app-shell" style={{ display: "flex", flexDirection: "row", height: "100vh" }}>
      <LeftSidebar
        brand={workspace.brand}
        entries={workspace.sidebar_entries}
        onOpenSettings={onOpenSettings}
      />
      <div className="main-column" style={{ display: "flex", flexDirection: "column", flex: 1 }}>
        <main className="main-chat-workspace" style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <header className="session-header">
            <span className="app-title">{workspace.app}</span>
          </header>
          <div className="workbench-grid" style={{ flex: 1, overflowY: "auto" }}>
            <DatabaseView
              sourceCoverage={workspace.source_coverage}
              sourceProfiles={workspace.source_profiles}
              sourceSettings={workspace.source_settings}
              syncJobs={workspace.sync_jobs}
            />
            <KnowledgeLibraryView summary={workspace.knowledge_library} />
            <SourceCategoriesView catalog={workspace.source_catalog} />
            <WorkflowView
              workflow={workspace.workflow}
              commandActions={workspace.command_actions}
              operatorTasks={workspace.operator_tasks}
              commandDispatcher={commandDispatcher}
              workflowTaskExecutor={workflowTaskExecutor}
              workflowProjectionKey={workflowProjectionKey}
              onWorkflowTaskExecuted={onWorkflowTaskExecuted}
            />
          </div>
          <div className="composer" style={{ padding: "8px" }}>
            <input type="text" placeholder="Ask AtomX..." style={{ width: "100%" }} />
          </div>
        </main>
        <BottomTelemetryBar telemetry={workspace.telemetry} />
      </div>
      <InspectorPanel
        tabs={RIGHT_INSPECTOR_TABS}
        sourceCoverage={workspace.source_coverage}
        workflow={workspace.workflow}
      />
      {showSettings && (
        <SettingsModal
          categories={SETTINGS_CATEGORIES}
          sourceSettings={workspace.source_settings}
          modelSettings={workspace.settings}
          readonlyRunConfig={readonlyRunConfig}
          readonlyRecentOutputDirs={readonlyRecentOutputDirs}
          onApplyReadonlyRunOutputDir={onApplyReadonlyRunOutputDir}
          commandDispatcher={commandDispatcher}
          onClose={onCloseSettings}
        />
      )}
    </div>
  );
};
