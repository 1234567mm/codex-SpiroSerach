// Session view — Reasonix-shaped transcript + composer for the AtomReasonX
// workbench. Message cards, reasoning fold, meta line and composer controls
// mirror Reasonix Message/Transcript/Composer classes and layout.

import React from "react";
import { Send, Trash2 } from "lucide-react";
import type { WorkbenchCommandDispatcher } from "../adapters/command-adapter";
import {
  isChatCompletionArtifact,
  isModelCommandResult,
  modelCommandErrorMessage,
  submitChatCompletion,
} from "../adapters/chat-adapter";
import type { ProviderConfigStatusEntry } from "../contracts/types";
import type { AtomReasonXTelemetryView } from "../lib/telemetry";
import {
  activateSession,
  clearActiveSessionMessages,
  createSession,
  deleteSession,
  sendSessionMessage,
  useActiveSessionId,
  useSessionMessages,
  useSessions,
  type LiveChatFn,
} from "../stores/session-store";
import { ModelSwitcher } from "./ModelSwitcher";

/** Minimal safe inline markdown: escapes HTML then renders **bold**. */
export function renderInlineMarkdown(text: string): string {
  const escaped = text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
  return escaped.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
}

export const formatMessageTime = (createdAt: string): string => {
  const date = new Date(createdAt);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
};

export const formatSessionTime = (createdAt: string): string => {
  const date = new Date(createdAt);
  if (Number.isNaN(date.getTime())) return "";
  const today = new Date();
  const sameDay = date.toDateString() === today.toDateString();
  if (sameDay) return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  return date.toLocaleDateString([], { month: "2-digit", day: "2-digit" });
};

export const SessionView: React.FC<{
  telemetry: AtomReasonXTelemetryView;
  models: ProviderConfigStatusEntry[];
  commandDispatcher?: WorkbenchCommandDispatcher;
  initialDraft?: string;
}> = ({ telemetry, models, commandDispatcher, initialDraft = "" }) => {
  const messages = useSessionMessages();
  const sessions = useSessions();
  const activeSessionId = useActiveSessionId();
  const [draft, setDraft] = React.useState(initialDraft);
  const [busy, setBusy] = React.useState(false);
  const [model, setModel] = React.useState<string>(() => {
    const available = models.filter((item) => item.enabled);
    return (available[0]?.provider ?? models[0]?.provider) ?? "default";
  });
  const transcriptRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    const el = transcriptRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length]);

  const liveChat = React.useMemo<LiveChatFn | undefined>(() => {
    if (!commandDispatcher) return undefined;
    return async (provider, _selectedModel, chatMessages) => {
      // Model id is intentionally omitted: the backend resolves the provider's
      // configured default model. The model switcher selects a provider, not a
      // concrete model id, so passing it here would send a provider id as the
      // model name.
      const result = await submitChatCompletion(
        commandDispatcher,
        provider,
        chatMessages,
      );
      if (!isModelCommandResult(result) || result.status !== "accepted") {
        throw new Error(
          isModelCommandResult(result)
            ? modelCommandErrorMessage(result)
            : "The model command did not return a result.",
        );
      }
      const artifact = result.output_artifacts.find(isChatCompletionArtifact);
      if (!artifact) {
        throw new Error("The model returned no result artifact.");
      }
      return {
        content: artifact.content,
        model: artifact.model,
        usage: artifact.usage,
      };
    };
  }, [commandDispatcher]);

  const submit = React.useCallback(async () => {
    const trimmed = draft.trim();
    if (!trimmed || busy) return;
    setDraft("");
    setBusy(true);
    try {
      await sendSessionMessage(trimmed, telemetry, model, liveChat);
    } finally {
      setBusy(false);
    }
  }, [draft, busy, telemetry, model, liveChat]);

  return (
    <div className="session-view">
      <aside className="session-view__rail" aria-label="Session history">
        <button
          type="button"
          className="btn btn--small session-view__new"
          onClick={() => createSession()}
        >
          New session
        </button>
        <div className="session-view__list">
          {sessions.map((session) => {
            const active = session.id === activeSessionId;
            return (
              <div key={session.id} className={`session-item${active ? " session-item--active" : ""}`}>
                <button
                  type="button"
                  className="session-item__main"
                  onClick={() => activateSession(session.id)}
                  aria-current={active ? "page" : undefined}
                >
                  <span className="session-item__title">{session.title}</span>
                  <span className="session-item__time">{formatSessionTime(session.updatedAt)}</span>
                </button>
                <button
                  type="button"
                  className="session-item__delete"
                  aria-label={`Delete session ${session.title}`}
                  onClick={() => deleteSession(session.id)}
                >
                  <Trash2 size={12} aria-hidden="true" />
                </button>
              </div>
            );
          })}
        </div>
      </aside>

      <div className="session-view__main">
        <div className="session-view__header">
          <span className="session-view__title">Session</span>
          <span className="session-view__meta">{messages.length} messages · {model}</span>
          <button
            type="button"
            className="btn btn--small session-view__clear"
            onClick={() => clearActiveSessionMessages()}
            aria-label="Clear session"
          >
            <Trash2 size={13} aria-hidden="true" />
            Clear
        </button>
      </div>

      <div className="transcript-shell">
        <div className="transcript" ref={transcriptRef} aria-live="polite">
          {messages.map((message) => (
            <div className="transcript__row" key={message.id}>
              {message.role === "user" ? (
                <div className="msg msg--user">
                  <div className="msg__body">
                    <div className="msg__text">{message.text}</div>
                  </div>
                  <div className="msg-meta">
                    <time className="msg-meta__time" dateTime={message.createdAt}>
                      {formatMessageTime(message.createdAt)}
                    </time>
                    <span className="msg-meta__tokens">{message.tokens} tok</span>
                  </div>
                </div>
              ) : (
                <div className="msg msg--assistant">
                  {message.reasoning ? (
                    <details className="msg-reasoning">
                      <summary>Reasoning</summary>
                      <pre className="msg-reasoning__body">{message.reasoning}</pre>
                    </details>
                  ) : null}
                  <div className="msg__body">
                    <div
                      className="msg__text msg__text--markdown"
                      dangerouslySetInnerHTML={{ __html: renderInlineMarkdown(message.text) }}
                    />
                  </div>
                  <div className="msg-meta">
                    <time className="msg-meta__time" dateTime={message.createdAt}>
                      {formatMessageTime(message.createdAt)}
                    </time>
                    <span className="msg-meta__tokens">{message.tokens} tok</span>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      <div className="composer-wrap">
        <div className="composer">
          <div className="composer__input-row">
            <textarea
              className="composer__input"
              placeholder="Ask AtomX… (Enter to send, Shift+Enter for newline)"
              value={draft}
              rows={2}
              onChange={(event) => setDraft(event.currentTarget.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void submit();
                }
              }}
            />
          </div>
          <div className="composer__meta">
            <ModelSwitcher
              models={models}
              value={model}
              onChange={setModel}
              disabled={busy}
            />
            <button
              type="button"
              className="btn btn--primary composer__send"
              disabled={busy || draft.trim() === ""}
              onClick={() => void submit()}
            >
              <Send size={14} aria-hidden="true" />
              {busy ? "…" : "Send"}
            </button>
          </div>
        </div>
      </div>
      </div>
    </div>
  );
};
