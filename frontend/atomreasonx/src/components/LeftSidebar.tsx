import React from "react";

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
      <ul className="nav-entries" style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {entries.map(entry => (
          <li key={entry} className="nav-entry" style={{ padding: "6px 12px", fontSize: "14px" }}>
            {entry}
          </li>
        ))}
      </ul>
      <div className="lower-left" style={{ marginTop: "auto", padding: "12px" }}>
        <button onClick={onOpenSettings} className="settings-btn">Settings</button>
      </div>
    </nav>
  );
};
