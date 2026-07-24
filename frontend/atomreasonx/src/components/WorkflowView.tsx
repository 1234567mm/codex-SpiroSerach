import React from "react";
import type { WorkbenchCommandDispatcher } from "../adapters/command-adapter";
import type { HtlOperatorTaskSummary, HtlWorkbenchCommandAction, HtlWorkflowPreview } from "../contracts/types";

export const buildWorkflowCommandPayload = (action: HtlWorkbenchCommandAction): Record<string, unknown> => ({
  provider: action.provider ?? null,
  provider_scope: action.provider_scope ?? "source",
  declared_effects: action.declared_effects,
});

export const canSubmitWorkflowCommandAction = (action: HtlWorkbenchCommandAction): boolean =>
  action.enabled && (action.input_fields ?? []).length === 0;

export const submitWorkflowCommandAction = (
  commandDispatcher: WorkbenchCommandDispatcher,
  action: HtlWorkbenchCommandAction,
): Promise<unknown> => {
  if (!canSubmitWorkflowCommandAction(action)) {
    return Promise.reject(new Error(`workflow command requires input: ${action.action_type}`));
  }
  return commandDispatcher.submitAction(action.action_type, buildWorkflowCommandPayload(action));
};

export const WorkflowView: React.FC<{
  workflow: HtlWorkflowPreview;
  commandActions: HtlWorkbenchCommandAction[];
  operatorTasks?: HtlOperatorTaskSummary[];
  commandDispatcher?: WorkbenchCommandDispatcher;
}> = ({ workflow, commandActions, operatorTasks = [], commandDispatcher }) => {
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
          <button
            key={action.action_type}
            disabled={!commandDispatcher || !canSubmitWorkflowCommandAction(action)}
            title={(action.input_fields ?? action.declared_effects).join(", ")}
            onClick={() => {
              if (commandDispatcher && canSubmitWorkflowCommandAction(action)) {
                void submitWorkflowCommandAction(commandDispatcher, action);
              }
            }}
          >
            {action.label}
          </button>
        ))}
      </div>
      {operatorTasks.length > 0 && (
        <div className="operator-task-list">
          {operatorTasks.map(task => (
            <div key={task.task_id} className="operator-task-row">
              <strong>{task.action_type}</strong>
              <span>{task.status}</span>
              <span>{task.provider ?? "workspace"}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
};
