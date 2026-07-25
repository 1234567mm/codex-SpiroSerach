import type {
  AtomReasonXCommandResult,
  AtomReasonXWorkflowCommandTaskArtifact,
  AtomReasonXWorkspaceState,
  HtlOperatorTaskSummary,
} from "../contracts/types";
import {
  WORKFLOW_OPERATOR_TASK_QUEUE_SCOPE,
  WORKFLOW_OPERATOR_TASK_SCHEMA_VERSION,
  buildWorkflowTaskConfig,
  getWorkflowCommandTaskDefinition,
} from "./workflow-command-task-contract";

export const projectWorkflowCommandTaskResult = (
  workspace: AtomReasonXWorkspaceState,
  result: AtomReasonXCommandResult,
): AtomReasonXWorkspaceState => {
  if (result.status !== "accepted") {
    return workspace;
  }
  const tasks = result.output_artifacts.filter(isWorkflowCommandTaskArtifact);
  if (tasks.length === 0) {
    return workspace;
  }
  const seenTaskIds = new Set(workspace.operator_tasks.map(task => task.task_id));
  const newTasks = tasks
    .filter(task => {
      if (seenTaskIds.has(task.task_id)) {
        return false;
      }
      seenTaskIds.add(task.task_id);
      return true;
    })
    .map(workflowTaskArtifactToSummary);
  if (newTasks.length === 0) {
    return workspace;
  }
  return {
    ...workspace,
    operator_tasks: [
      ...newTasks,
      ...workspace.operator_tasks.map(task => ({ ...task, config: { ...task.config } })),
    ],
  };
};

const isWorkflowCommandTaskArtifact = (
  artifact: unknown,
): artifact is AtomReasonXWorkflowCommandTaskArtifact => (
  isRecord(artifact)
  && artifact.kind === "workflow_command_task"
  && artifact.schema_version === WORKFLOW_OPERATOR_TASK_SCHEMA_VERSION
  && typeof artifact.task_id === "string"
  && typeof artifact.action_type === "string"
  && safeTaskIdForAction(artifact.task_id, artifact.action_type)
  && artifact.status === "queued"
  && artifact.queue_scope === WORKFLOW_OPERATOR_TASK_QUEUE_SCOPE
  && artifact.writes_authorized === false
  && artifact.execution_started === false
  && workflowTaskMatchesDefinition(artifact)
);

const workflowTaskArtifactToSummary = (
  artifact: AtomReasonXWorkflowCommandTaskArtifact,
): HtlOperatorTaskSummary => {
  const definition = getWorkflowCommandTaskDefinition(artifact.action_type);
  if (!definition) {
    throw new Error("workflow command task definition is required");
  }
  return {
    schema_version: WORKFLOW_OPERATOR_TASK_SCHEMA_VERSION,
    task_id: artifact.task_id,
    action_type: definition.action_type,
    provider: definition.provider,
    provider_scope: definition.provider_scope,
    status: "queued",
    queue_scope: WORKFLOW_OPERATOR_TASK_QUEUE_SCOPE,
    declared_effects: [...definition.declared_effects],
    writes_authorized: false,
    execution_started: false,
    created_at: null,
    config: buildWorkflowTaskConfig(),
  };
};

const workflowTaskMatchesDefinition = (artifact: Record<string, unknown>): boolean => {
  const definition = getWorkflowCommandTaskDefinition(String(artifact.action_type));
  return Boolean(
    definition
    && artifact.provider === definition.provider
    && artifact.provider_scope === definition.provider_scope
    && equalStringArray(artifact.declared_effects, definition.declared_effects)
  );
};

const equalStringArray = (value: unknown, expected: string[]): boolean => (
  Array.isArray(value)
  && value.length === expected.length
  && value.every((item, index) => item === expected[index])
);

const safeTaskIdForAction = (taskId: string, actionType: string): boolean => {
  const definition = getWorkflowCommandTaskDefinition(actionType);
  if (!definition) {
    return false;
  }
  const expectedPrefix = `task-${safeTaskToken(definition.action_type)}-`;
  const suffix = taskId.slice(expectedPrefix.length);
  return taskId.startsWith(expectedPrefix) && /^[a-z0-9]{1,16}$/.test(suffix);
};

const safeTaskToken = (value: string): string => (
  value.trim().toLowerCase().replace(/[^a-z0-9_-]+/g, "-").replace(/^-+|-+$/g, "") || "unknown"
);

const isRecord = (value: unknown): value is Record<string, unknown> => (
  typeof value === "object" && value !== null && !Array.isArray(value)
);
