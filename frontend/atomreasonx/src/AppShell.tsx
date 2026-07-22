import React from "react";
import { LeftSidebar } from "./components/LeftSidebar";
import { BottomTelemetryBar } from "./components/BottomTelemetryBar";
import { SettingsModal } from "./components/SettingsModal";
import type { AtomReasonXWorkspaceState } from "./contracts/types";

const SIDEBAR_ENTRIES = [
  "New Chat", "Database", "Projects", "Plugins", "Recent", "Automation",
];

const RIGHT_INSPECTOR_TABS = ["Overview", "Files"];

const SETTINGS_CATEGORIES = [
  "General", "Models", "Agents", "MCP And Tools", "Remote SSH", "Skills",
  "Subagents", "Plugins", "Memory", "Hooks", "Diagnostics", "Shortcuts",
  "Permissions", "Sandbox", "Network", "Retrieval", "File Parsing",
  "Knowledge Library", "Citation", "Cost Guardrails", "Telemetry source policy",
];

export const AppShell: React.FC<{
  workspace: AtomReasonXWorkspaceState;
  onOpenSettings?: () => void;
  showSettings?: boolean;
  onCloseSettings?: () => void;
}> = ({ workspace, onOpenSettings, showSettings, onCloseSettings }) => {
  return (
    <div className="app-shell" style={{ display: "flex", flexDirection: "row", height: "100vh" }}>
      <LeftSidebar
        brand={workspace.brand}
        entries={SIDEBAR_ENTRIES}
        onOpenSettings={onOpenSettings}
      />
      <div className="main-column" style={{ display: "flex", flexDirection: "column", flex: 1 }}>
        <main className="main-chat-workspace" style={{ flex: 1, display: "flex", flexDirection: "column" }}>
          <header className="session-header">
            <span className="app-title">{workspace.app}</span>
          </header>
          <div className="message-timeline" style={{ flex: 1, overflowY: "auto" }}>
            <div className="empty-state">
              <p>Start a new materials discovery session.</p>
            </div>
          </div>
          <div className="composer" style={{ padding: "8px" }}>
            <input type="text" placeholder="Ask AtomX..." style={{ width: "100%" }} />
          </div>
        </main>
        <BottomTelemetryBar telemetry={workspace.telemetry} />
      </div>
      <aside className="right-inspector" style={{ width: "280px" }}>
        {RIGHT_INSPECTOR_TABS.map(tab => (
          <div key={tab} className="inspector-tab">{tab}</div>
        ))}
      </aside>
      {showSettings && (
        <SettingsModal categories={SETTINGS_CATEGORIES} onClose={onCloseSettings} />
      )}
    </div>
  );
};
