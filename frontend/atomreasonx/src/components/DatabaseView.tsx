import React from "react";
import type { HtlSourceCoverageMatrix, HtlSyncJobSummary } from "../contracts/types";

export const DatabaseView: React.FC<{
  sourceCoverage: HtlSourceCoverageMatrix;
  syncJobs: HtlSyncJobSummary[];
}> = ({ sourceCoverage, syncJobs }) => {
  return (
    <section className="database-view">
      <div className="section-header">
        <h2>Database</h2>
        <span>{sourceCoverage.lane}</span>
      </div>
      <table className="dense-table">
        <thead>
          <tr>
            <th>Source</th>
            <th>Status</th>
            <th>Key</th>
            <th>Acquisition</th>
            <th>Blockers</th>
          </tr>
        </thead>
        <tbody>
          {sourceCoverage.sources.map(source => (
            <tr key={source.provider_id}>
              <td>{source.provider_id}</td>
              <td>{source.status} / {source.phase_status}</td>
              <td>{source.key_requirement}</td>
              <td>{source.automatic_acquisition}</td>
              <td>{source.review_blockers.join(", ") || "none"}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="job-strip">
        {syncJobs.map(job => (
          <div className="job-row" key={job.job_id}>
            <span>{job.provider}</span>
            <span>{job.status}</span>
          </div>
        ))}
      </div>
    </section>
  );
};
