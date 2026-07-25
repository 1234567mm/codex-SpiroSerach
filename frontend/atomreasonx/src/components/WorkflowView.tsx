import React from "react";
import type { WorkbenchCommandDispatcher } from "../adapters/command-adapter";
import {
  canExecuteWorkflowTask,
  type WorkflowTaskExecutor,
} from "../adapters/workflow-task-execution-adapter";
import type {
  HtlOperatorTaskSummary,
  HtlWorkbenchCommandAction,
  HtlWorkflowPreview,
  OperatorTaskExecutionReport,
} from "../contracts/types";

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
  workflowTaskExecutor?: WorkflowTaskExecutor;
  workflowProjectionKey?: string;
  onWorkflowTaskExecuted?: (report: OperatorTaskExecutionReport, projectionKey?: string) => void;
}> = ({
  workflow,
  commandActions,
  operatorTasks = [],
  commandDispatcher,
  workflowTaskExecutor,
  workflowProjectionKey,
  onWorkflowTaskExecuted,
}) => {
  const [executingTaskIds, setExecutingTaskIds] = React.useState<Set<string>>(() => new Set());
  const executeTask = React.useCallback(async (task: HtlOperatorTaskSummary) => {
    if (!workflowTaskExecutor || !canExecuteWorkflowTask(task) || executingTaskIds.has(task.task_id)) {
      return;
    }
    setExecutingTaskIds(previous => new Set(previous).add(task.task_id));
    const startedProjectionKey = workflowProjectionKey;
    try {
      const report = await workflowTaskExecutor.execute(task);
      onWorkflowTaskExecuted?.(report, startedProjectionKey);
    } finally {
      setExecutingTaskIds(previous => {
        const next = new Set(previous);
        next.delete(task.task_id);
        return next;
      });
    }
  }, [executingTaskIds, onWorkflowTaskExecuted, workflowProjectionKey, workflowTaskExecutor]);

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
          {operatorTasks.map(task => {
            const report = task.execution_report;
            return (
              <div key={task.task_id} className="operator-task-row">
                <strong>{task.action_type}</strong>
                <span>{report?.execution_status ?? task.status}</span>
                <span>{task.provider ?? "workspace"}</span>
                <button
                  type="button"
                  disabled={
                    !workflowTaskExecutor
                    || !canExecuteWorkflowTask(task)
                    || executingTaskIds.has(task.task_id)
                  }
                  title={task.task_id}
                  onClick={() => {
                    void executeTask(task);
                  }}
                >
                  Execute
                </button>
                {report && (
                  <div className="operator-task-report">
                    <span>{report.normalized_record_count} records</span>
                    <span>{report.archive_status}</span>
                    <span>{report.review_required ? report.review_reasons.join(", ") : "review clear"}</span>
                    <code style={{ overflowWrap: "anywhere" }}>{report.source_manifest_path}</code>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
};
