import React from "react";

export const SettingsModal: React.FC<{
  categories: string[];
  onClose?: () => void;
}> = ({ categories, onClose }) => {
  return (
    <div className="settings-overlay" style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)",
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <div className="settings-modal" style={{
        width: "72%", height: "86%", background: "#1a1a2e",
        display: "flex", flexDirection: "row", borderRadius: "8px", overflow: "hidden",
      }}>
        <nav className="settings-nav" style={{ width: "200px", padding: "8px 0" }}>
          {categories.map((cat, i) => (
            <div key={cat} className={`settings-nav-item ${i === 0 ? "selected" : ""}`}
              style={{
                padding: "6px 12px", fontSize: "13px",
                background: i === 0 ? "rgba(100,200,200,0.15)" : "transparent",
                borderLeft: i === 0 ? "3px solid teal" : "3px solid transparent",
              }}>
              {cat}
            </div>
          ))}
        </nav>
        <div className="settings-content" style={{ flex: 1, padding: "16px", overflowY: "auto" }}>
          <h3>{categories[0]}</h3>
          <p>Settings content for {categories[0]}.</p>
          <button onClick={onClose} className="close-btn">Close</button>
        </div>
      </div>
    </div>
  );
};
