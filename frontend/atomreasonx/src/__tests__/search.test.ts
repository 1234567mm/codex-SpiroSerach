import { describe, expect, it } from "vitest";
import {
  buildSearchDocuments,
  searchDocuments,
  scoreDocument,
  tokenize,
} from "../lib/search";

const docs = buildSearchDocuments({
  candidates: [
    {
      material_id: "MAT-CsPbI3-001",
      source_id: "nomad_perla_psc",
      record: { formula: "CsPbI3", htl: "Spiro-OMeTAD", pce: 12.4 },
    },
    {
      material_id: "MAT-Spiro-002",
      source_id: "materials_project",
      record: { formula: "C81H68N4", band_gap_ev: 3.1 },
    },
  ],
  catalogEntries: [
    { provider: "nomad_perla_psc", display_name: "NOMAD PERLA PSC", source_family: "perovskite" },
    { provider: "materials_project", display_name: "Materials Project", source_family: "database" },
  ],
});

describe("tokenize", () => {
  it("lowercases, splits and drops stop words", () => {
    expect(tokenize("HTL Spiro-OMeTAD 12.4")).toEqual(["ometad", "12"]);
    expect(tokenize("the spiro om")).toEqual(["om"]);
  });
});

describe("scoreDocument", () => {
  it("weights title and meta hits above body hits", () => {
    const doc = docs[0];
    const titleHit = scoreDocument(["mat", "cspbi3"], doc);
    const bodyHit = scoreDocument(["ometad"], doc);
    expect(titleHit).toBeGreaterThan(bodyHit);
  });
});

describe("searchDocuments", () => {
  it("finds candidates and sources by material or record text", () => {
    const hits = searchDocuments(docs, "CsPbI3");
    expect(hits.length).toBeGreaterThan(0);
    expect(hits[0].document.id).toContain("MAT-CsPbI3-001");
  });

  it("finds source catalog entries", () => {
    const hits = searchDocuments(docs, "materials project");
    expect(hits.some((hit) => hit.document.kind === "source")).toBe(true);
  });

  it("returns nothing for an empty query or no match", () => {
    expect(searchDocuments(docs, "")).toEqual([]);
    expect(searchDocuments(docs, "qqqzzz")).toEqual([]);
  });
});
