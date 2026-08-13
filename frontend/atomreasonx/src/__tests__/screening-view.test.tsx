import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { ScreeningView } from "../components/ScreeningView";
import type { ScreeningResultState } from "../contracts/types";
import fixture from "../fixtures/atomreasonx-ui-fixture.json";

const sampleResult: ScreeningResultState = {
  schema_version: "v37.screening_result.v1",
  module_id: "spiro_replacement_conventional_nip_v1",
  layer: "htl",
  source_ids: ["hopv15"],
  window: { homo_min: -5.6, homo_max: -5.0, lumo_min: -2.6, lumo_max: -1.8, band_gap_min: 2.0 },
  stats: { source_records: 180, hits: 1, homo_missing: 0, lumo_missing: 0, gap_missing: 0 },
  review_required: false,
  review_reasons: [],
  candidates: [
    {
      rank: 1,
      record_id: "KCTYWEWDJUBVCZ-UHFFFAOYSA-N",
      material_id: "hopv15:KCTYWEWDJUBVCZ-UHFFFAOYSA-N",
      homo_ev: -5.42,
      lumo_ev: -2.48,
      band_gap_ev: 2.94,
      score: 0.529,
      source_id: "hopv15",
      record: {},
    },
  ],
};

describe("ScreeningView", () => {
  it("renders ranked candidates with properties and score", () => {
    const markup = renderToStaticMarkup(<ScreeningView result={sampleResult} />);
    expect(markup).toContain("Screening");
    expect(markup).toContain("KCTYWEWDJUBVCZ-UHFFFAOYSA-N");
    expect(markup).toContain("-5.42");
    expect(markup).toContain("0.529");
    expect(markup).toContain("spiro_replacement_conventional_nip_v1");
    expect(markup).toContain("hits: 1");
  });

  it("renders review flag when facts are missing", () => {
    const result: ScreeningResultState = {
      ...sampleResult,
      stats: { ...sampleResult.stats, homo_missing: 3 },
      review_required: true,
      review_reasons: ["source_records_missing_energy_facts"],
      candidates: [],
    };
    const markup = renderToStaticMarkup(<ScreeningView result={result} />);
    expect(markup).toContain("Review required");
    expect(markup).toContain("source_records_missing_energy_facts");
    expect(markup).toContain("No candidates inside the screening window.");
  });

  it("renders unavailable state without a result", () => {
    const markup = renderToStaticMarkup(<ScreeningView result={undefined} />);
    expect(markup).toContain("unavailable");
    expect(markup).toContain("Run a screening task first.");
  });

  it("renders the real fixture screening result", () => {
    const result = (fixture as unknown as { screening_result: ScreeningResultState }).screening_result;
    const markup = renderToStaticMarkup(<ScreeningView result={result} />);
    expect(markup).toContain("KCTYWEWDJUBVCZ-UHFFFAOYSA-N");
    expect(markup).toContain("spiro_replacement_conventional_nip_v1");
  });
});
