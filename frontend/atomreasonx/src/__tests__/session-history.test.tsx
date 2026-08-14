import { afterEach, describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import React from "react";
import {
  activateSession,
  createSession,
  deleteSession,
  ensureSession,
  resetSessionStoreForTest,
  sendSessionMessage,
  useActiveSessionId,
  useSessionMessages,
  useSessions,
} from "../stores/session-store";
import type { AtomReasonXTelemetryView } from "../lib/telemetry";

const telemetry: AtomReasonXTelemetryView = {
  model_provider: "deepseek",
  retrieval_hit_count: 0,
  average_hit_rate: 0,
  current_turn_tokens: 0,
  session_tokens: 0,
  context_window: 128000,
  context_usage_percent: 0,
  context_remaining: 128000,
  compression_threshold: 100000,
  current_turn_cost: 0,
  session_cost: 0,
  total_cost: 0,
  balance: 0,
  active_session_state: "active",
  request_count: 0,
  provider_usage: {},
};

const readSnapshot = <T,>(reader: () => T): T => {
  const Reader: React.FC = () => {
    const value = reader();
    return <div className="snapshot">{JSON.stringify(value)}</div>;
  };
  const markup = renderToStaticMarkup(<Reader />);
  const match = /class="snapshot">([^<]*)</.exec(markup);
  return match
    ? JSON.parse(match[1].replace(/&quot;/g, "\""))
    : (undefined as unknown as T);
};

afterEach(() => {
  resetSessionStoreForTest();
});

describe("multi-session history", () => {
  it("creates, activates and deletes sessions", () => {
    const first = ensureSession();
    const second = createSession();
    const ids = readSnapshot(useSessions).map((item: { id: string }) => item.id);
    expect(ids).toEqual([second, first]);

    activateSession(first);
    expect(readSnapshot(useActiveSessionId)).toBe(first);

    deleteSession(first);
    const remaining = readSnapshot(useSessions).map((item: { id: string }) => item.id);
    expect(remaining).toEqual([second]);
    expect(readSnapshot(useActiveSessionId)).toBe(second);
  });

  it("keeps messages per session and titles from the first user message", async () => {
    const first = ensureSession();
    await sendSessionMessage("first question about spiro", telemetry, "deepseek");
    const second = createSession();
    await sendSessionMessage("second question about cache", telemetry, "deepseek");

    const sessions = readSnapshot(useSessions);
    const firstMeta = sessions.find((item: { id: string }) => item.id === first);
    expect(firstMeta?.title).toContain("first question about spiro");
    const secondMeta = sessions.find((item: { id: string }) => item.id === second);
    expect(secondMeta?.title).toContain("second question about cache");

    activateSession(first);
    const firstMessages = readSnapshot(useSessionMessages);
    expect(firstMessages.some((item: { text: string }) => item.text === "first question about spiro")).toBe(true);
    expect(firstMessages.some((item: { text: string }) => item.text === "second question about cache")).toBe(false);

    activateSession(second);
    const secondMessages = readSnapshot(useSessionMessages);
    expect(secondMessages.some((item: { text: string }) => item.text === "second question about cache")).toBe(true);
  });

  it("deleting the last session creates a fresh one", () => {
    const first = createSession();
    deleteSession(first);
    const sessions = readSnapshot(useSessions);
    expect(sessions).toHaveLength(1);
    expect(readSnapshot(useActiveSessionId)).toBe(sessions[0].id);
  });
});
