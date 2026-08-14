// Evidence graph — a simple layered SVG view of screening candidates, their
// sources and source families (knowledge-base style relationship graph).

import React from "react";
import type { ScreeningResultState, SourceCatalogSummary, HtlSourceCoverageMatrix } from "../contracts/types";
import { buildEvidenceGraph, layoutGraph } from "../lib/evidence-links";

const NODE_FILL: Record<string, string> = {
  family: "color-mix(in srgb, var(--accent) 14%, var(--bg-elev))",
  source: "color-mix(in srgb, var(--ok) 12%, var(--bg-elev))",
  candidate: "color-mix(in srgb, var(--warn) 12%, var(--bg-elev))",
};

const NODE_STROKE: Record<string, string> = {
  family: "var(--accent)",
  source: "var(--ok)",
  candidate: "var(--warn)",
};

export const EvidenceGraphView: React.FC<{
  screeningResult?: ScreeningResultState;
  sourceCatalog?: SourceCatalogSummary;
  sourceCoverage?: HtlSourceCoverageMatrix;
  onSearch?: (query: string) => void;
}> = ({ screeningResult, sourceCatalog, sourceCoverage, onSearch }) => {
  const graph = React.useMemo(
    () => buildEvidenceGraph(screeningResult, sourceCatalog, sourceCoverage),
    [screeningResult, sourceCatalog, sourceCoverage],
  );
  const positioned = React.useMemo(() => layoutGraph(graph), [graph]);
  if (graph.nodes.length === 0) {
    return <div className="empty-state">No screening or catalog data to graph.</div>;
  }
  const byId = new Map(positioned.map((node) => [node.id, node]));
  return (
    <div className="evidence-graph">
      <svg
        className="evidence-graph__svg"
        viewBox="0 0 960 200"
        role="img"
        aria-label="Evidence relationship graph"
      >
        {graph.edges.map((edge, index) => {
          const from = byId.get(edge.from);
          const to = byId.get(edge.to);
          if (!from || !to) return null;
          return (
            <line
              key={`${edge.from}-${edge.to}-${index}`}
              x1={from.x}
              y1={from.y}
              x2={to.x}
              y2={to.y}
              className="evidence-graph__edge"
            />
          );
        })}
        {positioned.map((node) => (
          <g
            key={node.id}
            className="evidence-graph__node"
            transform={`translate(${node.x}, ${node.y})`}
            onClick={() => onSearch?.(node.label)}
            role="button"
            aria-label={`${node.kind} ${node.label}`}
          >
            <circle
              r={node.kind === "candidate" ? 13 : 15}
              fill={NODE_FILL[node.kind]}
              stroke={NODE_STROKE[node.kind]}
              strokeWidth={1.5}
            />
            <text textAnchor="middle" dy="3.5" className="evidence-graph__label">
              {node.label.length > 14 ? `${node.label.slice(0, 13)}…` : node.label}
            </text>
          </g>
        ))}
      </svg>
      <div className="evidence-graph__legend">
        <span className="evidence-graph__legend-item"><i style={{ background: NODE_STROKE.family }} /> family</span>
        <span className="evidence-graph__legend-item"><i style={{ background: NODE_STROKE.source }} /> source</span>
        <span className="evidence-graph__legend-item"><i style={{ background: NODE_STROKE.candidate }} /> candidate</span>
        <span className="evidence-graph__hint">click a node to search it</span>
      </div>
    </div>
  );
};
