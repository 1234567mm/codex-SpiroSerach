// Chat + model-list commands — frontend helpers that submit chat_completion /
// model_list_refresh through the workbench command dispatcher (V23 envelope).
// The API key never leaves the backend: the frontend only sends provider id,
// model id, and messages.

import type { WorkbenchCommandDispatcher } from "./command-adapter";

export interface ChatCompletionArtifact {
  kind: "chat_completion_result";
  schema_version: string;
  action_type: "chat_completion";
  provider: string;
  model: string | null;
  content: string;
  usage: Record<string, unknown>;
}

export interface ModelListArtifact {
  kind: "model_list_result";
  schema_version: string;
  action_type: "model_list_refresh";
  provider: string;
  models: string[];
}

export interface ChatCompletionMessage {
  role: "user" | "assistant" | "system";
  content: string;
}

export interface ModelCommandResult {
  schema_version: string;
  action_type: string;
  status: string;
  reason_code: string;
  message: string;
  output_artifacts: unknown[];
}

export const isChatCompletionArtifact = (value: unknown): value is ChatCompletionArtifact => (
  typeof value === "object"
  && value !== null
  && (value as { kind?: unknown }).kind === "chat_completion_result"
);

export const isModelListArtifact = (value: unknown): value is ModelListArtifact => (
  typeof value === "object"
  && value !== null
  && (value as { kind?: unknown }).kind === "model_list_result"
);

export const isModelCommandResult = (value: unknown): value is ModelCommandResult => (
  typeof value === "object"
  && value !== null
  && !Array.isArray(value)
  && (value as { schema_version?: unknown }).schema_version === "v23.action_result.v1"
  && Array.isArray((value as { output_artifacts?: unknown }).output_artifacts)
);

export const submitChatCompletion = (
  dispatcher: WorkbenchCommandDispatcher,
  provider: string,
  messages: ChatCompletionMessage[],
  model?: string,
): Promise<unknown> => dispatcher.submitAction("chat_completion", {
  provider,
  messages,
  ...(model ? { model } : {}),
});

export const submitModelListRefresh = (
  dispatcher: WorkbenchCommandDispatcher,
  provider: string,
): Promise<unknown> => dispatcher.submitAction("model_list_refresh", { provider });

/** Human-readable failure text for a rejected model command (cc-switch style). */
export const modelCommandErrorMessage = (result: ModelCommandResult): string => {
  switch (result.reason_code) {
    case "missing_api_key":
      return "Set an API key for this provider first.";
    case "model_auth_failed":
      return "The model endpoint rejected the API key (HTTP 401/403).";
    case "model_endpoint_not_found":
      return "The model endpoint does not expose this API (HTTP 404/405).";
    case "model_list_unparseable":
      return "The provider returned an unexpected response format.";
    case "model_empty_response":
      return "The model returned no content.";
    default:
      return result.message || "The model command failed.";
  }
};
