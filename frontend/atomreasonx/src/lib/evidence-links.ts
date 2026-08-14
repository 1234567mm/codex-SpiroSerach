// Evidence link graph — builds a screening ↔ source ↔ family relationship
// graph from the loaded workbench data for the Evidence Graph view.

import type {
  HtlSourceCoverageMatrix,
  ScreeningResultState,
  SourceCatalogSummary,
} from "../contracts/types";

export type GraphNodeKind = "candidate" | "source" | "family";

export interface GraphNode {
  id: string;
  kind: GraphNodeKind;
  label: string;
  detail?: string;
}

export interface GraphEdge {
  from: string;
  to: string;
}

export interface EvidenceGraph {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export const buildEvidenceGraph = (
  screening?: ScreeningResultState,
  catalog?: SourceCatalogSummary,
  coverage?: HtlSourceCoverageMatrix,
): EvidenceGraph => {
  const nodes: GraphNode[] = [];
  const edges: GraphEdge[] = [];
  const seen = new Set<string>();

  const addNode = (node: GraphNode): void => {
    if (seen.has(node.id)) return;
    seen.add(node.id);
    nodes.push(node);
  };

  // Family nodes from the catalog.
  for (const family of catalog?.families ?? []) {
    addNode({ id: `family:${family.family}`, kind: "family", label: family.family, detail: `${family.entry_count} entries` });
    for (const entry of family.entries) {
      const sourceId = `source:${entry.provider}`;
      addNode({ id: sourceId, kind: "source", label: entry.display_name, detail: entry.data_library_path });
      edges.push({ from: sourceId, to: `family:${family.family}` });
    }
  }

  // Coverage sources may not appear in the catalog.
  for (const row of coverage?.sources ?? []) {
    const sourceId = `source:${row.provider_id}`;
    if (!seen.has(sourceId)) {
      addNode({ id: sourceId, kind: "source", label: row.provider_id, detail: row.htl_capability });
    }
  }

  // Candidates link to their source.
  for (const candidate of screening?.candidates ?? []) {
    const candidateId = `candidate:${candidate.material_id}`;
    addNode({
      id: candidateId,
      kind: "candidate",
      label: candidate.material_id,
      detail: `score ${candidate.score.toFixed(3)} · gap ${candidate.band_gap_ev.toFixed(2)} eV`,
    });
    if (candidate.source_id) {
      edges.push({ from: candidateId, to: `source:${candidate.source_id}` });
    }
  }

  return { nodes, edges };
};

/** Layered layout: families top, sources middle, candidates bottom. */
export const layoutGraph = (graph: EvidenceGraph): Array<GraphNode & { x: number; y: number }> => {
  const layers: Record<GraphNodeKind, GraphNode[]> = {
    family: graph.nodes.filter((node) => node.kind === "family"),
    source: graph.nodes.filter((node) => node.kind === "source"),
    candidate: graph.nodes.filter((node) => node.kind === "candidate"),
  };
  const order: GraphNodeKind[] = ["family", "source", "candidate"];
  const positions: Array<GraphNode & { x: number; y: number }> = [];
  const layerY: Record<GraphNodeKind, number> = { family: 24, source: 88, candidate: 152 };
  for (const kind of order) {
    const items = layers[kind];
    const spacing = Math.max(110, 880 / Math.max(1, items.length));
    items.forEach((node, index) => {
      positions.push({
        ...node,
        x: 60 + index * spacing,
        y: layerY[kind],
      });
    });
  }
  return positions;
};
