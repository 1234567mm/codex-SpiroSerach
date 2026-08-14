import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { SessionView, formatMessageTime, renderInlineMarkdown } from "../components/SessionView";
import { ContextWindowRing, contextWindowStatus } from "../components/ContextWindowRing";
import { BottomTelemetryBar } from "../components/BottomTelemetryBar";
import { buildNavGroups } from "../AppShell";
import fixture from "../fixtures/atomreasonx-ui-fixture.json";
import type { AtomReasonXWorkspaceState, ProviderConfigStatusEntry } from "../contracts/types";
import { toTelemetryView } from "../lib/telemetry";

const workspace = fixture as unknown as AtomReasonXWorkspaceState;
const telemetry = toTelemetryView(workspace.telemetry);
const models = workspace.settings.providers as ProviderConfigStatusEntry[];

describe("context window status tones", () => {
  it("maps usage percentages to good/notice/warn like Reasonix", () => {
    expect(contextWindowStatus(5, 78)).toBe("good");
    expect(contextWindowStatus(70, 78)).toBe("notice");
    expect(contextWindowStatus(80, 78)).toBe("warn");
    expect(contextWindowStatus(95, 78)).toBe("warn");
    expect(contextWindowStatus(120, 78)).toBe("warn");
  });
});

describe("SessionView transcript", () => {
  it("renders welcome message, composer and model select", () => {
    const markup = renderToStaticMarkup(
      <SessionView telemetry={telemetry} models={models} />,
    );
    expect(markup).toContain("Welcome to the AtomReasonX session");
    expect(markup).toContain("msg--assistant");
    expect(markup).toContain("composer__input");
    expect(markup).toContain("model-switcher");
    expect(markup).toContain("Send");
    expect(markup).toContain("private_new_api");
  });

  it("renders user and assistant messages in Reasonix msg format", () => {
    const messages = [
      { id: "u1", role: "user" as const, text: "show cache", createdAt: new Date().toISOString(), tokens: 3 },
      {
        id: "a1",
        role: "assistant" as const,
        reasoning: "Checking telemetry.",
        text: "Cache hit **34.8%**.",
        createdAt: new Date().toISOString(),
        tokens: 12,
      },
    ];
    const markup = renderToStaticMarkup(
      <div>
        {messages.map((message) => (
          <div key={message.id} className="transcript__row">
            {message.role === "user" ? (
              <div className="msg msg--user">
                <div className="msg__body"><div className="msg__text">{message.text}</div></div>
              </div>
            ) : (
              <div className="msg msg--assistant">
                <details className="msg-reasoning"><summary>Reasoning</summary></details>
                <div className="msg__body">
                  <div className="msg__text msg__text--markdown"
                    dangerouslySetInnerHTML={{ __html: renderInlineMarkdown(message.text) }} />
                </div>
              </div>
            )}
          </div>
        ))}
      </div>,
    );
    expect(markup).toContain("msg--user");
    expect(markup).toContain("msg--assistant");
    expect(markup).toContain("msg-reasoning");
    expect(markup).toContain("<strong>34.8%</strong>");
  });
});

describe("ContextWindowRing", () => {
  it("renders the ring with telemetry-derived usage", () => {
    const markup = renderToStaticMarkup(<ContextWindowRing telemetry={telemetry} />);
    expect(markup).toContain("context-ring");
    expect(markup).toContain("context-ring__svg");
    expect(markup).toContain("aria-label");
  });

  it("renders cache and cost rows when opened", () => {
    const markup = renderToStaticMarkup(
      <div className="context-ring-wrap">
        <div className="context-ring-popover">
          <div className="context-ring-popover__inner">
            <span className="context-ring-popover__label">Prompt cache</span>
            <span className="context-ring-popover__value">34.78%</span>
          </div>
        </div>
      </div>,
    );
    expect(markup).toContain("context-ring-popover");
    expect(markup).toContain("Prompt cache");
    expect(markup).toContain("34.78%");
  });

  it("hides when disabled", () => {
    const markup = renderToStaticMarkup(<ContextWindowRing telemetry={telemetry} enabled={false} />);
    expect(markup).toBe("");
  });
});

describe("BottomTelemetryBar (Reasonix statusbar)", () => {
  it("renders model, cache, tokens, cost and balance metrics", () => {
    const markup = renderToStaticMarkup(<BottomTelemetryBar telemetry={workspace.telemetry} />);
    expect(markup).toContain("statusbar");
    expect(markup).toContain("fake-private-new-api");
    expect(markup).toContain("Cache");
    expect(markup).toContain("Avg");
    expect(markup).toContain("Tokens");
    expect(markup).toContain("Cost");
    expect(markup).toContain("Balance");
  });
});

describe("nav groups", () => {
  it("maps sidebar entries to workbench views", () => {
    const groups = buildNavGroups(workspace.sidebar_entries, Boolean(workspace.screening_result));
    const labels = groups[0].views.map((view) => view.label);
    expect(labels).toContain("Session");
    expect(labels).toContain("Database");
    expect(labels).toContain("Knowledge Library");
    expect(labels).toContain("Workflow");
    expect(labels).toContain("Projects");
    expect(labels).toContain("Screening");
  });

  it("falls back to a session-only nav when entries are empty", () => {
    const groups = buildNavGroups([], false);
    expect(groups[0].views.map((view) => view.id)).toEqual(["session", "search"]);
  });
});

describe("message time formatting", () => {
  it("formats ISO timestamps as local time and tolerates invalid input", () => {
    expect(formatMessageTime(new Date(0).toISOString())).not.toBe("");
    expect(formatMessageTime("not-a-date")).toBe("");
  });
});
