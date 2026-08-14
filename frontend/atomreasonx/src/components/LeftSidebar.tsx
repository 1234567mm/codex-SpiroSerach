import React from "react";

const NAV_GROUPS: Array<{ label: string; entries: string[] }> = [
  { label: "Workspace", entries: ["Session", "Database", "Knowledge Library", "Screening", "Workflow", "Projects"] },
  { label: "System", entries: ["Settings", "Diagnostics"] },
];

export const LeftSidebar: React.FC<{
  brand: string;
  entries: string[];
  onOpenSettings?: () => void;
}> = ({ brand, entries, onOpenSettings }) => {
  return (
    <nav className="left-sidebar" style={{ width: "220px", display: "flex", flexDirection: "column" }}>
      <div className="brand-slot" style={{ padding: "12px", fontWeight: 600 }}>
        {brand}
      </div>
      <div style={{ flex: 1, overflowY: "auto" }}>
        {NAV_GROUPS.map(group => (
          <div key={group.label}>
            <div className="nav-group-label">{group.label}</div>
            <ul className="nav-entries" style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {group.entries.map(entry => (
                <li key={entry} className={`nav-entry ${entries.includes(entry) ? "" : "nav-entry--inactive"}`}
                  style={{ padding: "6px 12px", fontSize: "14px" }}>
                  {entry}
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
