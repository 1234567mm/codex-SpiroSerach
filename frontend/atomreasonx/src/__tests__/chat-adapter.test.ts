import { describe, expect, it } from "vitest";
import {
  isChatCompletionArtifact,
  isModelCommandResult,
  isModelListArtifact,
  modelCommandErrorMessage,
  submitChatCompletion,
  submitModelListRefresh,
} from "../adapters/chat-adapter";
import type { WorkbenchCommandDispatcher } from "../adapters/command-adapter";

const recorded: Array<{ actionType: string; payload: Record<string, unknown> }> = [];

const dispatcher: WorkbenchCommandDispatcher = {
  submitAction: async (actionType, payload) => {
    recorded.push({ actionType, payload });
    return {
      schema_version: "v23.action_result.v1",
      action_type: actionType,
      status: "accepted",
      reason_code: "ok",
      message: "ok",
      output_artifacts: [],
    };
  },
};

describe("chat-adapter command payloads", () => {
  it("submits chat_completion with provider, model and messages", async () => {
    await submitChatCompletion(dispatcher, "deepseek", [
      { role: "user", content: "hi" },
    ], "deepseek-v4-pro");
    expect(recorded[0]).toEqual({
      actionType: "chat_completion",
      payload: {
        provider: "deepseek",
        messages: [{ role: "user", content: "hi" }],
        model: "deepseek-v4-pro",
      },
    });
  });

  it("submits model_list_refresh with provider only", async () => {
    await submitModelListRefresh(dispatcher, "deepseek");
    expect(recorded[1]).toEqual({
      actionType: "model_list_refresh",
      payload: { provider: "deepseek" },
    });
  });
});

describe("chat-adapter result guards", () => {
  it("recognizes chat and model-list artifacts", () => {
    expect(isChatCompletionArtifact({ kind: "chat_completion_result", content: "x" })).toBe(true);
    expect(isChatCompletionArtifact({ kind: "other" })).toBe(false);
    expect(isModelListArtifact({ kind: "model_list_result", models: [] })).toBe(true);
    expect(isModelListArtifact(null)).toBe(false);
  });

  it("recognizes v23 command results", () => {
    expect(isModelCommandResult({
      schema_version: "v23.action_result.v1",
      output_artifacts: [],
    })).toBe(true);
    expect(isModelCommandResult({ schema_version: "other" })).toBe(false);
    expect(isModelCommandResult(null)).toBe(false);
  });
});

describe("model command error messages (cc-switch style)", () => {
  it("classifies auth, endpoint and payload failures", () => {
    expect(modelCommandErrorMessage({ reason_code: "model_auth_failed", message: "" } as never)).toContain("401/403");
    expect(modelCommandErrorMessage({ reason_code: "model_endpoint_not_found", message: "" } as never)).toContain("404/405");
    expect(modelCommandErrorMessage({ reason_code: "missing_api_key", message: "" } as never)).toContain("API key");
    expect(modelCommandErrorMessage({ reason_code: "model_empty_response", message: "" } as never)).toContain("no content");
    expect(modelCommandErrorMessage({ reason_code: "other", message: "boom" } as never)).toBe("boom");
  });
});
