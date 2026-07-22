import React from "react";
import type { AtomReasonXTelemetryState } from "../contracts/types";

export const BottomTelemetryBar: React.FC<{
  telemetry: AtomReasonXTelemetryState;
}> = ({ telemetry }) => {
  return (
    <div className="bottom-telemetry-bar" style={{
      height: "24px",
      display: "flex",
      alignItems: "center",
      gap: "12px",
      padding: "0 8px",
      fontSize: "11px",
      borderTop: "1px solid #333",
      overflowX: "hidden",
    }}>
      {telemetry.fields.map(field => (
        <span key={field.name} className="telemetry-item" title={`source: ${field.source}`}>
          {field.name}: {String(field.value)} <span className="source-label">({field.source})</span>
        </span>
      ))}
    </div>
  );
};
