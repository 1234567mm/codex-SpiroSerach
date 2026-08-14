import React from "react";
import type { WorkbenchViewId } from "../lib/views";

export interface SidebarViewEntry {
  id: WorkbenchViewId;
  label: string;
}

export interface SidebarNavGroup {
  label: string;
  views: SidebarViewEntry[];
}

export const LeftSidebar: React.FC<{
  brand: string;
  groups: SidebarNavGroup[];
  activeView: WorkbenchViewId;
  onSelectView: (id: WorkbenchViewId) => void;
  onOpenSettings?: () => void;
}> = ({ brand, groups, activeView, onSelectView, onOpenSettings }) => {
  return (
    <nav className="left-sidebar" style={{ width: "220px", display: "flex", flexDirection: "column" }}>
      <div className="brand-slot" style={{ padding: "12px", fontWeight: 600 }}>
        {brand}
      </div>
      <div style={{ flex: 1, overflowY: "auto" }}>
        {groups.map(group => (
          <div key={group.label}>
            <div className="nav-group-label">{group.label}</div>
            <ul className="nav-entries" style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {group.views.map(view => (
                <li key={view.id}>
                  <button
                    type="button"
                    className={`nav-entry nav-entry--view${activeView === view.id ? " nav-entry--active" : ""}`}
                    onClick={() => onSelectView(view.id)}
                    aria-current={activeView === view.id ? "page" : undefined}
                  >
                    {view.label}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <div className="lower-left" style={{ marginTop: "auto", padding: "12px" }}>
        <button onClick={onOpenSettings} className="settings-btn">Settings</button>
      </div>
    </nav>
  );
};
