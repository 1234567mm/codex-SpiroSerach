import { afterEach, describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import React from "react";
import {
  resetSessionStoreForTest,
  sendSessionMessage,
  useSessionMessages,
} from "../stores/session-store";
import type { AtomReasonXTelemetryView } from "../lib/telemetry";

const telemetry: AtomReasonXTelemetryView = {
  model_provider: "deepseek",
  retrieval_hit_count: 3,
  average_hit_rate: 0.42,
  current_turn_tokens: 150,
  session_tokens: 1250,
  context_window: 128000,
  context_usage_percent: 1,
  context_remaining: 126750,
  compression_threshold: 100000,
  current_turn_cost: 0.001,
  session_cost: 0.012,
  total_cost: 0.012,
  balance: 50,
  active_session_state: "active",
  request_count: 5,
  provider_usage: { cache_read_input_tokens: 80, prompt_tokens: 150 },
};

/** Renders a component that subscribes to the session store (server snapshot). */
const readMessages = (): ReturnType<typeof useSessionMessages> => {
  const Reader: React.FC = () => {
    const messages = useSessionMessages();
    return <div className="session-reader">{JSON.stringify(messages)}</div>;
  };
  const markup = renderToStaticMarkup(<Reader />);
  const match = /class="session-reader">([^<]*)</.exec(markup);
  if (!match) return [];
  return JSON.parse(match[1].replace(/&quot;/g, "\"")) as ReturnType<typeof useSessionMessages>;
};

afterEach(() => {
  resetSessionStoreForTest();
});

describe("sendSessionMessage with live chat", () => {
  it("appends the remote reply when the live channel succeeds", async () => {
    const liveChat = async (): Promise<{ content: string; model?: string | null; usage?: Record<string, unknown> }> => ({
      content: "real model reply",
      model: "deepseek-v4-pro",
      usage: { total_tokens: 42 },
    });
    await sendSessionMessage("hello", telemetry, "deepseek", liveChat);
    const messages = readMessages();
    expect(messages.map((item) => item.text)).toEqual([
      "Welcome to the AtomReasonX session. Ask about the workbench, data sources, screening, or cache/context usage — replies include live telemetry metrics in the Reasonix format.",
      "hello",
      "real model reply",
    ]);
    expect(messages[2].role).toBe("assistant");
    expect(messages[2].reasoning).toContain("deepseek-v4-pro");
    expect(messages[2].error).toBeUndefined();
    expect(messages[2].preview).toBeUndefined();
  });

  it("pushes an error message when the live channel fails", async () => {
    const failing = async (): Promise<{ content: string }> => {
      throw new Error("model endpoint rejected the API key (HTTP 401)");
    };
    await sendSessionMessage("hi", telemetry, "deepseek", failing);
    const messages = readMessages();
    const error = messages[messages.length - 1];
    expect(error.role).toBe("assistant");
    expect(error.error).toBe(true);
    expect(error.text).toContain("HTTP 401");
  });

  it("falls back to a preview digest without a live channel", async () => {
    await sendSessionMessage("hi", telemetry, "deepseek");
    const messages = readMessages();
    const reply = messages[messages.length - 1];
    expect(reply.role).toBe("assistant");
    expect(reply.preview).toBe(true);
    expect(reply.text).toContain("preview");
    expect(reply.text).toContain("Context window");
  });

  it("excludes welcome and preview messages from live chat history", async () => {
    await sendSessionMessage("hello", telemetry, "deepseek"); // preview digest appended
    let received: unknown = null;
    await sendSessionMessage("second", telemetry, "deepseek", async (_p, _m, history) => {
      received = history;
      return { content: "ok" };
    });
    expect(received).toEqual([
      { role: "user", content: "hello" },
      { role: "user", content: "second" },
    ]);
  });
});
