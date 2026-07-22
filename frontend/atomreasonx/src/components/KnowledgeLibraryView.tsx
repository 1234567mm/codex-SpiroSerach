import React from "react";
import type { KnowledgeLibrarySummary } from "../contracts/types";

export const KnowledgeLibraryView: React.FC<{
  summary: KnowledgeLibrarySummary;
}> = ({ summary }) => {
  const rows = [
    ["Files", summary.file_count],
    ["Parsed papers", summary.parsed_papers],
    ["SI attachments", summary.si_attachments],
    ["Provider snapshots", summary.provider_snapshots],
    ["Claims", summary.extracted_claims],
    ["Review blockers", summary.blocked_review_items],
  ];
  return (
    <section className="knowledge-view">
      <div className="section-header">
        <h2>Knowledge Library</h2>
        <span>{summary.index_freshness ?? "unavailable"}</span>
      </div>
      <div className="metric-grid">
        {rows.map(([label, value]) => (
          <div className="metric-cell" key={String(label)}>
            <span>{label}</span>
            <strong>{String(value)}</strong>
          </div>
        ))}
      </div>
    </section>
  );
};
