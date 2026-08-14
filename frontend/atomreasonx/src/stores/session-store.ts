// Session message store — Reasonix-shaped multi-session history for the
// AtomReasonX workbench. Messages persist to localStorage per session; the
// active session feeds the transcript. When a live chat function is wired
// (backend model channel via the Tauri config command plane), replies come
// from the remote model; failures surface as error messages. Without a live
// channel the assistant reply is a deterministic telemetry digest (preview).

import { useSyncExternalStore } from "react";
import type { AtomReasonXTelemetryView } from "../lib/telemetry";
import { formatCacheHitRate, formatTokenCount, formatTokensCompact } from "../lib/telemetry";
import type { ChatCompletionMessage } from "../adapters/chat-adapter";

export interface SessionMessage {
  id: string;
  role: "user" | "assistant";
  reasoning?: string;
  text: string;
  createdAt: string;
  tokens: number;
  preview?: boolean;
  error?: boolean;
}

export interface SessionMeta {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
}

export interface LiveChatResult {
  content: string;
  model?: string | null;
  usage?: Record<string, unknown>;
}

export type LiveChatFn = (
  provider: string,
  model: string,
  messages: ChatCompletionMessage[],
) => Promise<LiveChatResult>;

const MESSAGES_STORAGE_KEY = "atomreasonx-session-messages-v1";
const SESSIONS_STORAGE_KEY = "atomreasonx-sessions-v1";
const WELCOME_MESSAGE: SessionMessage = {
  id: "welcome",
  role: "assistant",
  text:
    "Welcome to the AtomReasonX session. Ask about the workbench, data sources, screening, or cache/context usage — replies include live telemetry metrics in the Reasonix format.",
  createdAt: new Date(0).toISOString(),
  tokens: 40,
};

let sessions: SessionMeta[] = [];
let activeSessionId: string | null = null;
let messagesBySession: Record<string, SessionMessage[]> = {};
let listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

function persist(): void {
  try {
    localStorage.setItem(
      SESSIONS_STORAGE_KEY,
      JSON.stringify({
        sessions,
        activeSessionId,
        messages: messagesBySession,
      }),
    );
  } catch {
    // storage unavailable: keep in-memory only
  }
}

function load(): void {
  try {
    const raw = localStorage.getItem(SESSIONS_STORAGE_KEY);
    if (raw) {
      const parsed = JSON.parse(raw) as {
        sessions?: SessionMeta[];
        activeSessionId?: string | null;
        messages?: Record<string, SessionMessage[]>;
      };
      sessions = Array.isArray(parsed.sessions) ? parsed.sessions : [];
      activeSessionId = typeof parsed.activeSessionId === "string" ? parsed.activeSessionId : null;
      messagesBySession = parsed.messages && typeof parsed.messages === "object"
        ? parsed.messages
        : {};
      if (sessions.length === 0) {
        const legacy = legacyLoad();
        const id = nextId();
        sessions = [{ id, title: "Session 1", createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() }];
        messagesBySession = { [id]: legacy };
        activeSessionId = id;
      }
      if (!activeSessionId || !messagesBySession[activeSessionId]) {
        const id = sessions[0]?.id ?? nextId();
        if (!sessions.some((item) => item.id === id)) {
          sessions = [{ id, title: "Session 1", createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() }, ...sessions];
        }
        activeSessionId = id;
        messagesBySession[id] = messagesBySession[id] ?? [WELCOME_MESSAGE];
      }
      return;
    }
    const legacy = legacyLoad();
    const id = nextId();
    sessions = [{ id, title: "Session 1", createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() }];
    messagesBySession = { [id]: legacy };
    activeSessionId = id;
  } catch {
    const id = nextId();
    sessions = [{ id, title: "Session 1", createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() }];
    messagesBySession = { [id]: [WELCOME_MESSAGE] };
    activeSessionId = id;
  }
}

function legacyLoad(): SessionMessage[] {
  try {
    const raw = localStorage.getItem(MESSAGES_STORAGE_KEY);
    if (!raw) return [WELCOME_MESSAGE];
    const parsed = JSON.parse(raw) as SessionMessage[];
    if (!Array.isArray(parsed) || parsed.length === 0) return [WELCOME_MESSAGE];
    return parsed;
  } catch {
    return [WELCOME_MESSAGE];
  }
}

function nextId(): string {
  return `s-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

function estimateTokens(text: string): number {
  return Math.max(1, Math.round(text.length / 4));
}

function currentMessages(): SessionMessage[] {
  return activeSessionId ? (messagesBySession[activeSessionId] ?? []) : [];
}

function touchSession(id: string): void {
  sessions = sessions.map((item) => (
    item.id === id ? { ...item, updatedAt: new Date().toISOString() } : item
  ));
}

function buildTelemetryDigest(telemetry: AtomReasonXTelemetryView): string {
  const cacheRate = currentTurnCacheRateText(telemetry);
  const lines = [
    `- Context window: **${formatTokensCompact(telemetry.context_window)}** tokens, **${telemetry.context_usage_percent}%** used (${formatTokensCompact(telemetry.context_remaining)} remaining; compact threshold ${formatTokensCompact(telemetry.compression_threshold)})`,
    `- Session tokens: **${formatTokenCount(telemetry.session_tokens)}** (turn ${formatTokenCount(telemetry.current_turn_tokens)})`,
    `- Prompt cache: **${cacheRate}** this turn, session average **${(telemetry.average_hit_rate * 100).toFixed(1)}%** across ${telemetry.request_count} requests (${telemetry.retrieval_hit_count} retrieval hits)`,
    `- Session cost: **$${telemetry.session_cost.toFixed(4)}** · balance $${telemetry.balance.toFixed(2)}`,
  ];
  return lines.join("\n");
}

function currentTurnCacheRateText(telemetry: AtomReasonXTelemetryView): string {
  const usage = telemetry.provider_usage;
  const hit = usage.cache_read_input_tokens ?? 0;
  const miss = usage.prompt_tokens ?? 0;
  const rate = formatCacheHitRate(hit, miss);
  return rate === "-" ? "not reported" : rate;
}

function buildAssistantReply(
  prompt: string,
  telemetry: AtomReasonXTelemetryView,
  model: string,
): { reasoning: string; text: string } {
  const trimmed = prompt.trim();
  const digest = buildTelemetryDigest(telemetry);
  const reasoning = [
    `Handling "${trimmed.slice(0, 80)}" for the AtomReasonX workbench.`,
    `Current session: ${telemetry.session_tokens} tokens across ${telemetry.request_count} requests on ${model}.`,
    `Context at ${telemetry.context_usage_percent}% (compact threshold ${formatTokensCompact(telemetry.compression_threshold)}).`,
    "No live model channel is wired — replying with the telemetry digest (preview mode).",
  ].join("\n");
  const text = [
    `Here is the current AtomReasonX telemetry snapshot (model **${model}**, session state **${telemetry.active_session_state}**):`,
    "",
    digest,
    "",
    "This is a **preview** reply: connect the model backend (Settings → Models, set an API key) to get real assistant turns.",
  ].join("\n");
  return { reasoning, text };
}

function sessionTitleFor(messages: SessionMessage[]): string {
  const firstUser = messages.find((item) => item.role === "user");
  if (!firstUser) return "New session";
  const text = firstUser.text.trim().replace(/\s+/g, " ");
  return text.length > 40 ? `${text.slice(0, 40)}…` : text;
}

/* ── public API ─────────────────────────────────────────────────────────────── */

export function useSessionMessages(): SessionMessage[] {
  return useSyncExternalStore(
    (callback) => {
      listeners.add(callback);
      return () => listeners.delete(callback);
    },
    () => {
      const messages = currentMessages();
      return messages.length === 0 ? [WELCOME_MESSAGE] : messages;
    },
    () => {
      const messages = currentMessages();
      return messages.length === 0 ? [WELCOME_MESSAGE] : messages;
    },
  );
}

export function useSessions(): SessionMeta[] {
  return useSyncExternalStore(
    (callback) => {
      listeners.add(callback);
      return () => listeners.delete(callback);
    },
    () => sessions,
    () => sessions,
  );
}

export function useActiveSessionId(): string | null {
  return useSyncExternalStore(
    (callback) => {
      listeners.add(callback);
      return () => listeners.delete(callback);
    },
    () => activeSessionId,
    () => activeSessionId,
  );
}

export async function sendSessionMessage(
  prompt: string,
  telemetry: AtomReasonXTelemetryView,
  model: string,
  liveChat?: LiveChatFn,
): Promise<void> {
  const trimmed = prompt.trim();
  if (!trimmed) return;
  const sessionId = activeSessionId ?? ensureSession();
  const base = messagesBySession[sessionId] ?? [];
  const userMessage: SessionMessage = {
    id: nextId(),
    role: "user",
    text: trimmed,
    createdAt: new Date().toISOString(),
    tokens: estimateTokens(trimmed),
  };
  messagesBySession = {
    ...messagesBySession,
    [sessionId]: [...base, userMessage],
  };
  sessions = sessions.map((item) => (
    item.id === sessionId
      ? { ...item, title: sessionTitleFor(messagesBySession[sessionId]), updatedAt: new Date().toISOString() }
      : item
  ));
  emit();
  persist();

  if (!liveChat) {
    await new Promise((resolve) => setTimeout(resolve, 280 + Math.random() * 240));
    const reply = buildAssistantReply(trimmed, telemetry, model);
    const assistantMessage: SessionMessage = {
      id: nextId(),
      role: "assistant",
      reasoning: reply.reasoning,
      text: reply.text,
      createdAt: new Date().toISOString(),
      tokens: estimateTokens(reply.reasoning + reply.text),
      preview: true,
    };
    messagesBySession = {
      ...messagesBySession,
      [sessionId]: [...messagesBySession[sessionId], assistantMessage],
    };
    touchSession(sessionId);
    emit();
    persist();
    return;
  }

  const history: ChatCompletionMessage[] = messagesBySession[sessionId]
    .filter((item) => (
      item.role === "user"
      || (item.role === "assistant" && !item.error && !item.preview && item.id !== "welcome")
    ))
    .map((item) => ({ role: item.role, content: item.text }));

  try {
    const reply = await liveChat(model, model, [...history]);
    const assistantMessage: SessionMessage = {
      id: nextId(),
      role: "assistant",
      reasoning: `Answered via **${reply.model ?? model}** with ${reply.usage?.total_tokens ?? "?"} tokens this turn.`,
      text: reply.content,
      createdAt: new Date().toISOString(),
      tokens: estimateTokens(reply.content),
    };
    messagesBySession = {
      ...messagesBySession,
      [sessionId]: [...messagesBySession[sessionId], assistantMessage],
    };
    touchSession(sessionId);
    emit();
    persist();
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    const errorMessage: SessionMessage = {
      id: nextId(),
      role: "assistant",
      text: `The model request failed: ${detail}`,
      createdAt: new Date().toISOString(),
      tokens: 0,
      error: true,
    };
    messagesBySession = {
      ...messagesBySession,
      [sessionId]: [...messagesBySession[sessionId], errorMessage],
    };
    touchSession(sessionId);
    emit();
    persist();
  }
}

export function ensureSession(): string {
  if (activeSessionId && messagesBySession[activeSessionId]) return activeSessionId;
  const id = nextId();
  sessions = [
    { id, title: "New session", createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() },
    ...sessions,
  ];
  messagesBySession = { ...messagesBySession, [id]: [WELCOME_MESSAGE] };
  activeSessionId = id;
  emit();
  persist();
  return id;
}

export function createSession(): string {
  const id = nextId();
  sessions = [
    { id, title: "New session", createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() },
    ...sessions,
  ];
  messagesBySession = { ...messagesBySession, [id]: [WELCOME_MESSAGE] };
  activeSessionId = id;
  emit();
  persist();
  return id;
}

export function activateSession(id: string): void {
  if (!messagesBySession[id]) return;
  activeSessionId = id;
  emit();
  persist();
}

export function deleteSession(id: string): void {
  const remaining = sessions.filter((item) => item.id !== id);
  if (remaining.length === 0) {
    sessions = [];
    messagesBySession = {};
    activeSessionId = null;
    createSession();
    return;
  }
  sessions = remaining;
  messagesBySession = Object.fromEntries(
    Object.entries(messagesBySession).filter(([key]) => key !== id),
  );
  if (activeSessionId === id) {
    activeSessionId = remaining[0].id;
  }
  emit();
  persist();
}

export function clearActiveSessionMessages(): void {
  const sessionId = activeSessionId ?? ensureSession();
  messagesBySession = { ...messagesBySession, [sessionId]: [WELCOME_MESSAGE] };
  emit();
  persist();
}

/** Replaces the in-memory snapshot (used by tests). */
export function resetSessionStoreForTest(): void {
  sessions = [];
  activeSessionId = null;
  messagesBySession = {};
  listeners = new Set();
}

/** Restores the persisted snapshot on boot (no-op when already loaded). */
export function initializeSessionStore(): void {
  if (sessions.length > 0 || activeSessionId) return;
  load();
  emit();
}
