import React from "react";
import { MessageSquare } from "lucide-react";
import type { ScreeningResultState } from "../contracts/types";

export interface ScreeningCandidatePrompt {
  record_id: string;
  material_id: string;
  score: number;
  band_gap_ev: number;
  source_id: string;
}

export const buildCandidatePrompt = (candidate: ScreeningCandidatePrompt): string =>
  [
    `Analyze screening candidate ${candidate.material_id || candidate.record_id} (ranked ${candidate.score.toFixed(3)}, band gap ${candidate.band_gap_ev.toFixed(2)} eV, source ${candidate.source_id}).`,
    "Assess its fit as a Spiro-OMeTAD replacement and list the key evidence to check next.",
  ].join(" ");

export const ScreeningView: React.FC<{
  result?: ScreeningResultState;
  onAskInSession?: (prompt: string) => void;
}> = ({ result, onAskInSession }) => {
  if (!result) {
    return (
      <section className="screening-view">
        <div className="section-header">
          <h2>Screening</h2>
          <span>unavailable</span>
        </div>
        <p className="empty-state">No screening result loaded. Run a screening task first.</p>
      </section>
    );
  }
  return (
    <section className="screening-view">
      <div className="section-header">
        <h2>Screening</h2>
        <span>
          {result.module_id} · {result.layer}
        </span>
      </div>
      {result.review_required && (
        <div className="review-flag" style={{ color: "#fb7", fontSize: "12px", marginBottom: "8px" }}>
          Review required: {result.review_reasons.join(", ")}
        </div>
      )}
      <div className="metric-grid" style={{ display: "flex", gap: "16px", fontSize: "12px", marginBottom: "8px" }}>
        <span>sources: {result.source_ids.join(", ") || "unknown"}</span>
        <span>hits: {result.stats.hits ?? 0}</span>
        <span>source records: {result.stats.source_records ?? 0}</span>
        <span>missing facts: {(result.stats.homo_missing ?? 0) + (result.stats.lumo_missing ?? 0) + (result.stats.gap_missing ?? 0)}</span>
      </div>
      <table className="screening-table">
        <thead>
          <tr>
            <th>Rank</th>
            <th>Record</th>
            <th>HOMO (eV)</th>
            <th>LUMO (eV)</th>
            <th>Band gap (eV)</th>
            <th>Score</th>
            <th>Source</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {result.candidates.map((candidate) => (
            <tr key={`${candidate.record_id}:${candidate.rank}`}>
              <td>{candidate.rank}</td>
              <td>{candidate.record_id}</td>
              <td>{candidate.homo_ev}</td>
              <td>{candidate.lumo_ev}</td>
              <td>{candidate.band_gap_ev}</td>
              <td>{candidate.score}</td>
              <td>{candidate.source_id}</td>
              <td>
                {onAskInSession && (
                  <button
                    type="button"
                    className="btn btn--small"
                    title="Ask the model about this candidate in the session"
                    onClick={() => onAskInSession(buildCandidatePrompt(candidate))}
                  >
                    <MessageSquare size={12} aria-hidden="true" />
                    Ask
                  </button>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {result.candidates.length === 0 && (
        <p className="empty-state" style={{ fontSize: "12px" }}>
          No candidates inside the screening window.
        </p>
      )}
    </section>
  );
};
