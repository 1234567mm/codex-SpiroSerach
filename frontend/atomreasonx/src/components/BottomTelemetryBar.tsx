import React from "react";
import type { AtomReasonXTelemetryState } from "../contracts/types";

export const BottomTelemetryBar: React.FC<{
  telemetry: AtomReasonXTelemetryState;
}> = ({ telemetry }) => {
  return (
    <div className="telemetry-bar" style={{
      height: "24px",
      alignItems: "center",
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
