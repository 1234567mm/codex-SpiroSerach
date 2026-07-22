import React from "react";
import type { HtlSourceCoverageMatrix, HtlWorkflowPreview } from "../contracts/types";

export const InspectorPanel: React.FC<{
  tabs: string[];
  sourceCoverage: HtlSourceCoverageMatrix;
  workflow: HtlWorkflowPreview;
}> = ({ tabs, sourceCoverage, workflow }) => {
  const critical = sourceCoverage.sources.filter(source => source.phase_status === "critical");
  return (
    <aside className="right-inspector">
      <div className="inspector-tabs">
        {tabs.map(tab => (
          <span key={tab}>{tab}</span>
        ))}
      </div>
      <div className="inspector-section">
        <h3>Coverage</h3>
        {critical.map(source => (
          <div className="inspector-row" key={source.provider_id}>
            <span>{source.provider_id}</span>
            <strong>{source.key_requirement}</strong>
          </div>
        ))}
      </div>
      <div className="inspector-section">
        <h3>Fields</h3>
        <p>{workflow.target_fields.slice(0, 8).join(", ")}</p>
      </div>
    </aside>
  );
};
