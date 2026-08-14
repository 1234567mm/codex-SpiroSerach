import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import fixture from "../fixtures/atomreasonx-ui-fixture.json";
import type { AtomReasonXWorkspaceState } from "../contracts/types";
import { ScreeningView, buildCandidatePrompt } from "../components/ScreeningView";
import { SessionView } from "../components/SessionView";
import { toTelemetryView } from "../lib/telemetry";
import type { ProviderConfigStatusEntry } from "../contracts/types";

const workspace = fixture as unknown as AtomReasonXWorkspaceState;
const telemetry = toTelemetryView(workspace.telemetry);
const models = workspace.settings.providers as ProviderConfigStatusEntry[];

describe("buildCandidatePrompt", () => {
  it("builds a session-ready prompt from a candidate", () => {
    const prompt = buildCandidatePrompt({
      record_id: "rec-1",
      material_id: "MAT-1",
      score: 0.87,
      band_gap_ev: 1.5,
      source_id: "nomad_perla_psc",
    });
    expect(prompt).toContain("MAT-1");
    expect(prompt).toContain("0.870");
    expect(prompt).toContain("1.50 eV");
    expect(prompt).toContain("nomad_perla_psc");
  });
});

describe("ScreeningView ask-in-session", () => {
  it("renders an Ask button per candidate when wired", () => {
    const markup = renderToStaticMarkup(
      <ScreeningView
        result={workspace.screening_result}
        onAskInSession={() => undefined}
      />,
    );
    expect(markup).toContain("Ask");
  });

  it("omits the Ask button without the callback", () => {
    const markup = renderToStaticMarkup(<ScreeningView result={workspace.screening_result} />);
    expect(markup).not.toContain("Ask");
  });
});

describe("SessionView initial draft", () => {
  it("pre-fills the composer from the initial draft", () => {
    const markup = renderToStaticMarkup(
      <SessionView telemetry={telemetry} models={models} initialDraft="Analyze screening candidate MAT-1" />,
    );
    expect(markup).toContain("Analyze screening candidate MAT-1");
  });
});
