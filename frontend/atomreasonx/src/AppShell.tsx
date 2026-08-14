import React from "react";
import { LeftSidebar, type SidebarNavGroup } from "./components/LeftSidebar";
import { BottomTelemetryBar } from "./components/BottomTelemetryBar";
import { ContextWindowRing } from "./components/ContextWindowRing";
import { SessionView } from "./components/SessionView";
import { SearchView } from "./components/SearchView";
import { EvidenceGraphView } from "./components/EvidenceGraphView";
import { SettingsModal } from "./components/SettingsModal";
import { DatabaseView } from "./components/DatabaseView";
import { KnowledgeLibraryView } from "./components/KnowledgeLibraryView";
import { SourceCategoriesView } from "./components/SourceCategoriesView";
import { ScreeningView } from "./components/ScreeningView";
import { WorkflowView } from "./components/WorkflowView";
import { InspectorPanel } from "./components/InspectorPanel";
import type { WorkbenchCommandDispatcher } from "./adapters/command-adapter";
import type { WorkflowTaskExecutor } from "./adapters/workflow-task-execution-adapter";
import type {
  ReadonlyRunOperatorConfig,
  ReadonlyRunRecentOutputDir,
} from "./adapters/readonly-run-operator-config";
import type { AtomReasonXWorkspaceState, OperatorTaskExecutionReport } from "./contracts/types";
import type { WorkbenchViewId } from "./lib/views";
import { toTelemetryView } from "./lib/telemetry";

export const workspaceModeBadge = (
  workspace: AtomReasonXWorkspaceState,
): { label: string; tone: "fixture" | "readonly" | "repo" } => {
  if (workspace.active_workspace.startsWith("readonly_run:")) {
    return { label: `readonly run`, tone: "readonly" };
  }
  if (workspace._provisional) {
    return { label: "demo data", tone: "fixture" };
  }
  return { label: "workspace", tone: "repo" };
};

const RIGHT_INSPECTOR_TABS = ["Overview", "Files"];

const SETTINGS_CATEGORIES = [
  "General", "Models", "Agents", "MCP And Tools", "Remote SSH", "Skills",
  "Subagents", "Plugins", "Memory", "Hooks", "Diagnostics", "Shortcuts",
  "Permissions", "Sandbox", "Network", "Retrieval", "File Parsing",
  "Knowledge Library", "Data Sources", "Citation", "Cost Guardrails", "Telemetry source policy",
];

const VIEW_BY_LABEL: Record<string, WorkbenchViewId> = {
  "Session": "session",
  "Database": "database",
  "Knowledge Library": "knowledge",
  "Screening": "screening",
  "Workflow": "workflow",
  "Projects": "projects",
  "Search": "search",
};

const VIEW_LABELS: Record<WorkbenchViewId, string> = {
  session: "Session",
  search: "Search",
  database: "Database",
  knowledge: "Knowledge Library",
  screening: "Screening",
  workflow: "Workflow",
  projects: "Projects",
};

export const buildNavGroups = (sidebarEntries: string[], hasScreening: boolean): SidebarNavGroup[] => {
  const workspaceViews: { id: WorkbenchViewId; label: string }[] = [];
  const seen = new Set<WorkbenchViewId>();
  for (const entry of sidebarEntries) {
    const id = VIEW_BY_LABEL[entry];
    if (id && !seen.has(id)) {
      seen.add(id);
      workspaceViews.push({ id, label: VIEW_LABELS[id] });
    }
  }
  if (hasScreening && !seen.has("screening")) {
    workspaceViews.splice(1, 0, { id: "screening", label: VIEW_LABELS.screening });
  }
  if (workspaceViews.length === 0) {
    workspaceViews.push({ id: "session", label: VIEW_LABELS.session });
  }
  if (!seen.has("search")) {
    const sessionIndex = workspaceViews.findIndex((view) => view.id === "session");
    workspaceViews.splice(sessionIndex === -1 ? 1 : sessionIndex + 1, 0, {
      id: "search",
      label: VIEW_LABELS.search,
    });
  }
  return [{ label: "Workspace", views: workspaceViews }];
};

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
  const navGroups = React.useMemo(
    () => buildNavGroups(workspace.sidebar_entries, Boolean(workspace.screening_result)),
    [workspace.sidebar_entries, workspace.screening_result],
  );
  const availableViews = React.useMemo(
    () => new Set(navGroups.flatMap((group) => group.views.map((view) => view.id))),
    [navGroups],
  );
  const [activeView, setActiveView] = React.useState<WorkbenchViewId>(() => {
    const first = navGroups[0]?.views[0]?.id;
    return first && availableViews.has(first) ? first : "session";
  });
  const [searchQuery, setSearchQuery] = React.useState("");
  const [sessionDraft, setSessionDraft] = React.useState("");
  const activeViewId = availableViews.has(activeView) ? activeView : "session";
  const telemetryView = React.useMemo(() => toTelemetryView(workspace.telemetry), [workspace.telemetry]);
  const runSearch = React.useCallback((query: string) => {
    setSearchQuery(query);
    setActiveView("search");
  }, []);
  const askInSession = React.useCallback((prompt: string) => {
    setSessionDraft(prompt);
    setActiveView("session");
  }, []);

  return (
    <div className="app-shell" style={{ display: "flex", flexDirection: "row", height: "100vh" }}>
      <LeftSidebar
        brand={workspace.brand}
        groups={navGroups}
        activeView={activeViewId}
        onSelectView={setActiveView}
        onOpenSettings={onOpenSettings}
      />
      <div className="main-column" style={{ display: "flex", flexDirection: "column", flex: 1 }}>
        <main className="main-chat-workspace" style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <header className="session-header">
            <span className="app-title">{workspace.app}</span>
            <span style={{ display: "inline-flex", alignItems: "center", gap: "10px" }}>
              <ContextWindowRing telemetry={telemetryView} />
              <span className={`mode-badge mode-badge--${workspaceModeBadge(workspace).tone}`}>
                {workspaceModeBadge(workspace).label}
              </span>
            </span>
          </header>
          <div className="workbench-view" style={{ flex: 1, minHeight: 0, overflowY: "auto" }}>
            {activeViewId === "session" && (
              <SessionView
                key={sessionDraft}
                initialDraft={sessionDraft}
                telemetry={telemetryView}
                models={workspace.settings.providers}
                commandDispatcher={commandDispatcher}
              />
            )}
            {activeViewId === "search" && (
              <section className="view-card workbench-view-page">
                <SearchView
                  key={searchQuery}
                  initialQuery={searchQuery}
                  screeningResult={workspace.screening_result}
                  sourceCatalog={workspace.source_catalog}
                />
              </section>
            )}
            {activeViewId === "database" && (
              <section className="view-card workbench-view-page">
                <DatabaseView
                  sourceCoverage={workspace.source_coverage}
                  sourceProfiles={workspace.source_profiles}
                  sourceSettings={workspace.source_settings}
                  syncJobs={workspace.sync_jobs}
                />
              </section>
            )}
            {activeViewId === "knowledge" && (
              <section className="view-card workbench-view-page">
                <KnowledgeLibraryView summary={workspace.knowledge_library} />
              </section>
            )}
            {activeViewId === "projects" && (
              <section className="view-card workbench-view-page">
                <SourceCategoriesView catalog={workspace.source_catalog} />
              </section>
            )}
            {activeViewId === "screening" && workspace.screening_result && (
              <section className="view-card workbench-view-page">
                <EvidenceGraphView
                  screeningResult={workspace.screening_result}
                  sourceCatalog={workspace.source_catalog}
                  sourceCoverage={workspace.source_coverage}
                  onSearch={runSearch}
                />
                <ScreeningView
                  result={workspace.screening_result}
                  onAskInSession={askInSession}
                />
              </section>
            )}
            {activeViewId === "workflow" && (
              <section className="view-card workbench-view-page">
                <WorkflowView
                  workflow={workspace.workflow}
                  commandActions={workspace.command_actions}
                  operatorTasks={workspace.operator_tasks}
                  commandDispatcher={commandDispatcher}
                  workflowTaskExecutor={workflowTaskExecutor}
                  workflowProjectionKey={workflowProjectionKey}
                  onWorkflowTaskExecuted={onWorkflowTaskExecuted}
                />
              </section>
            )}
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
          providerRegistry={workspace.provider_status}
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
