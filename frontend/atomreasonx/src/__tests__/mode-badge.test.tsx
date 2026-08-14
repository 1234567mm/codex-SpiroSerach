import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { workspaceModeBadge } from "../AppShell";
import type { AtomReasonXWorkspaceState } from "../contracts/types";
import fixture from "../fixtures/atomreasonx-ui-fixture.json";

const base = fixture as unknown as AtomReasonXWorkspaceState;

describe("workspace mode badge", () => {
  it("marks the provisional fixture as demo data", () => {
    expect(workspaceModeBadge(base)).toEqual({ label: "demo data", tone: "fixture" });
  });

  it("marks a readonly run workspace", () => {
    const readonly = { ...base, active_workspace: "readonly_run:abc", _provisional: false };
    expect(workspaceModeBadge(readonly)).toEqual({ label: "readonly run", tone: "readonly" });
  });

  it("marks a repository workspace", () => {
    const repo = { ...base, _provisional: false };
    expect(workspaceModeBadge(repo)).toEqual({ label: "workspace", tone: "repo" });
  });

  it("renders the badge in the session header", () => {
    const markup = renderToStaticMarkup(
      <span className={`mode-badge mode-badge--${workspaceModeBadge(base).tone}`}>
        {workspaceModeBadge(base).label}
      </span>,
    );
    expect(markup).toContain("mode-badge--fixture");
    expect(markup).toContain("demo data");
  });
});
