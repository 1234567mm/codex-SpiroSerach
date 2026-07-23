import React from "react";
import type { AtomReasonXSourceSettingsState } from "../contracts/types";

type SettingsCommandHandler = (actionType: string, payload: Record<string, unknown>) => void;

export const SettingsModal: React.FC<{
  categories: string[];
  sourceSettings?: AtomReasonXSourceSettingsState;
  onCommand?: SettingsCommandHandler;
  onClose?: () => void;
}> = ({ categories, sourceSettings, onCommand, onClose }) => {
  const [selected, setSelected] = React.useState(categories[0] ?? "General");
  const [sourceKeys, setSourceKeys] = React.useState<Record<string, string>>({});
  const isDataSources = selected === "Data Sources";

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
          {categories.map((cat) => (
            <button key={cat} className={`settings-nav-item ${cat === selected ? "selected" : ""}`}
              onClick={() => setSelected(cat)}
              style={{
                width: "100%", padding: "6px 12px", fontSize: "13px", textAlign: "left",
                background: cat === selected ? "rgba(100,200,200,0.15)" : "transparent",
                border: 0,
                borderLeft: cat === selected ? "3px solid teal" : "3px solid transparent",
                color: "#eef",
              }}>
              {cat}
            </button>
          ))}
        </nav>
        <div className="settings-content" style={{ flex: 1, padding: "16px", overflowY: "auto" }}>
          <h3>{selected}</h3>
          {isDataSources ? (
            <div style={{ display: "grid", gap: "8px" }}>
              {(sourceSettings?.sources ?? []).map((source) => (
                <div key={source.provider_id} style={{
                  display: "grid",
                  gridTemplateColumns: "minmax(120px, 1fr) 96px 96px minmax(160px, 1.5fr) minmax(220px, 1.5fr)",
                  gap: "8px",
                  alignItems: "center",
                  padding: "8px",
                  border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: "6px",
                  fontSize: "12px",
                }}>
                  <strong>{source.provider_id}</strong>
                  <span>{source.validation_state}</span>
                  <span>{source.key_requirement}</span>
                  <span>{source.data_library_path ?? ""}</span>
                  <span style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                    {source.requires_api_key && (
                      <>
                        <input
                          aria-label={`${source.provider_id} API key`}
                          type="password"
                          value={sourceKeys[source.provider_id] ?? ""}
                          onChange={(event) => setSourceKeys({
                            ...sourceKeys,
                            [source.provider_id]: event.currentTarget.value,
                          })}
                          style={{ minWidth: 0, width: "96px" }}
                        />
                        <button
                          type="button"
                          disabled={!onCommand || !(sourceKeys[source.provider_id] ?? "").trim()}
                          onClick={() => {
                            onCommand?.("key_rotate", {
                              provider: source.provider_id,
                              provider_scope: "source",
                              api_key: sourceKeys[source.provider_id] ?? "",
                            });
                            setSourceKeys({
                              ...sourceKeys,
                              [source.provider_id]: "",
                            });
                          }}
                        >
                          Set
                        </button>
                        <button
                          type="button"
                          disabled={!onCommand || !source.has_api_key}
                          onClick={() => onCommand?.("key_remove", {
                            provider: source.provider_id,
                            provider_scope: "source",
                          })}
                        >
                          Remove
                        </button>
                      </>
                    )}
                    <button
                      type="button"
                      disabled={!onCommand}
                      onClick={() => onCommand?.("test_connection", {
                        provider: source.provider_id,
                        provider_scope: "source",
                      })}
                    >
                      Test
                    </button>
                  </span>
                </div>
              ))}
            </div>
          ) : (
            <div style={{ fontSize: "13px", color: "#cfd3ff" }}>{selected}</div>
          )}
          <button onClick={onClose} className="close-btn">Close</button>
        </div>
      </div>
    </div>
  );
};
