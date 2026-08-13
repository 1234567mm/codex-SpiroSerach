import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { SourceCategoriesView } from "../components/SourceCategoriesView";
import type { SourceCatalogSummary } from "../contracts/types";
import fixture from "../fixtures/atomreasonx-ui-fixture.json";

const sampleCatalog: SourceCatalogSummary = {
  schema_version: "v37.source_catalog.v1",
  source_count: 2,
  family_count: 1,
  families: [
    {
      family: "opv_benchmark",
      entry_count: 2,
      acquisition_modes: ["local_snapshot"],
      entries: [
        {
          provider: "hopv15",
          display_name: "HOPV15",
          source_family: "opv_benchmark",
          acquisition_mode: "local_snapshot",
          operational_status: "experimental",
          go_migration_state: "go_shadow_ready",
          data_library_path: "data/lib/hopv15",
          fixture_status: "fixture_only",
          local_snapshot_count: 2,
        },
        {
          provider: "opv_db",
          display_name: "OPV-DB",
          source_family: "opv_benchmark",
          acquisition_mode: "local_snapshot",
          operational_status: "experimental",
          go_migration_state: "go_shadow_ready",
          data_library_path: "data/lib/opv_db",
          fixture_status: "fixture_only",
          local_snapshot_count: 2,
        },
      ],
    },
  ],
};

describe("SourceCategoriesView", () => {
  it("renders families with entry details and snapshot counts", () => {
    const markup = renderToStaticMarkup(<SourceCategoriesView catalog={sampleCatalog} />);
    expect(markup).toContain("Source Categories");
    expect(markup).toContain("opv_benchmark");
    expect(markup).toContain("HOPV15");
    expect(markup).toContain("fixture_only");
    expect(markup).toContain("2 snapshots");
    expect(markup).toContain("2 sources · 1 categories");
  });

  it("renders an explicit unavailable state when the catalog is missing", () => {
    const markup = renderToStaticMarkup(<SourceCategoriesView catalog={undefined} />);
    expect(markup).toContain("unavailable");
    expect(markup).toContain("No classified source catalog loaded.");
  });

  it("renders the real fixture catalog from the workspace contract", () => {
    const catalog = (fixture as unknown as { source_catalog: SourceCatalogSummary }).source_catalog;
    const markup = renderToStaticMarkup(<SourceCategoriesView catalog={catalog} />);
    expect(markup).toContain("opv_benchmark");
    expect(markup).toContain("13 sources · 9 categories");
  });
});
