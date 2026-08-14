import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import fixture from "../fixtures/atomreasonx-ui-fixture.json";
import type { AtomReasonXWorkspaceState } from "../contracts/types";
import { buildEvidenceGraph, layoutGraph } from "../lib/evidence-links";
import { EvidenceGraphView } from "../components/EvidenceGraphView";
import {
  addKnowledgeImport,
  loadKnowledgeImports,
  removeKnowledgeImport,
} from "../lib/knowledge-imports";

const workspace = fixture as unknown as AtomReasonXWorkspaceState;

describe("buildEvidenceGraph", () => {
  it("links candidates to sources and sources to families", () => {
    const graph = buildEvidenceGraph(
      workspace.screening_result,
      workspace.source_catalog,
      workspace.source_coverage,
    );
    expect(graph.nodes.some((node) => node.kind === "candidate")).toBe(true);
    expect(graph.nodes.some((node) => node.kind === "source")).toBe(true);
    expect(graph.nodes.some((node) => node.kind === "family")).toBe(true);
    expect(graph.edges.length).toBeGreaterThan(0);
    // Candidate edges point at source nodes that exist.
    for (const edge of graph.edges) {
      expect(graph.nodes.some((node) => node.id === edge.from)).toBe(true);
      expect(graph.nodes.some((node) => node.id === edge.to)).toBe(true);
    }
  });

  it("layers the graph and keeps every node positioned", () => {
    const graph = buildEvidenceGraph(undefined, undefined, undefined);
    const positions = layoutGraph(graph);
    expect(positions).toHaveLength(graph.nodes.length);
    for (const position of positions) {
      expect(position.x).toBeGreaterThan(0);
      expect(position.y).toBeGreaterThan(0);
    }
  });
});

describe("EvidenceGraphView", () => {
  it("renders nodes and edges from workspace data", () => {
    const markup = renderToStaticMarkup(
      <EvidenceGraphView
        screeningResult={workspace.screening_result}
        sourceCatalog={workspace.source_catalog}
        sourceCoverage={workspace.source_coverage}
      />,
    );
    expect(markup).toContain("evidence-graph__svg");
    expect(markup).toContain("evidence-graph__node");
  });

  it("shows an empty state without data", () => {
    const markup = renderToStaticMarkup(<EvidenceGraphView />);
    expect(markup).toContain("No screening or catalog data to graph");
  });
});

describe("knowledge imports", () => {
  it("stores and lists markdown/text imports", () => {
    try {
      addKnowledgeImport("notes.md", "# Notes\nSome HTL candidate analysis.");
      addKnowledgeImport("readme.txt", "plain text");
      const items = loadKnowledgeImports();
      expect(items).toHaveLength(2);
      expect(items[1].kind).toBe("markdown");
      expect(items[0].kind).toBe("text");
      removeKnowledgeImport(items[0].id);
      expect(loadKnowledgeImports()).toHaveLength(1);
    } finally {
      try {
        localStorage.removeItem("atomreasonx-knowledge-imports-v1");
      } catch {
        // no localStorage in this environment
      }
    }
  });
});
