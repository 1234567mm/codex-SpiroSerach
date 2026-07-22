import React from "react";
import type { HtlWorkbenchCommandAction, HtlWorkflowPreview } from "../contracts/types";

export const WorkflowView: React.FC<{
  workflow: HtlWorkflowPreview;
  commandActions: HtlWorkbenchCommandAction[];
}> = ({ workflow, commandActions }) => {
  return (
    <section className="workflow-view">
      <div className="section-header">
        <h2>Workflow</h2>
        <span>{workflow.gates.join(" / ")}</span>
      </div>
      <ol className="workflow-list">
        {workflow.steps.map(step => (
          <li key={step.index}>
            <span>{step.index}</span>
            <strong>{step.label}</strong>
          </li>
        ))}
      </ol>
      <div className="command-bar">
        {commandActions.map(action => (
          <button key={action.action_type} disabled={!action.enabled} title={action.declared_effects.join(", ")}>
            {action.label}
          </button>
        ))}
      </div>
    </section>
  );
};
