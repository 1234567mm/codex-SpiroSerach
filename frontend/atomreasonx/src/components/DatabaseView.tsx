import React from "react";
import type {
  AtomReasonXSourceProfilesState,
  AtomReasonXSourceSettingsState,
  HtlSourceCoverageMatrix,
  HtlSyncJobSummary,
  SourceConfigStatusEntry,
} from "../contracts/types";

export interface DataSourceDisplayRow {
  provider_id: string;
  display_name: string;
  provider_status: string;
  key_state: string;
  quarantine_state: string;
  dataset_version: string;
  citation: string;
  blocking_review_count: number;
  review_blockers: string;
}

export const buildDataSourceDisplayRows = (
  sourceCoverage: HtlSourceCoverageMatrix,
  sourceProfiles: AtomReasonXSourceProfilesState,
  sourceSettings: AtomReasonXSourceSettingsState,
): DataSourceDisplayRow[] => {
  const profiles = new Map(sourceProfiles.profiles.map(profile => [profile.provider_id, profile]));
  const settings = new Map(sourceSettings.sources.map(source => [source.provider_id, source]));
  const coverage = new Map(sourceCoverage.sources.map(source => [source.provider_id, source]));
  const providerIds = [
    ...sourceCoverage.sources.map(source => source.provider_id),
    ...sourceSettings.sources.map(source => source.provider_id),
    ...sourceProfiles.profiles.map(profile => profile.provider_id),
  ].filter((providerId, index, allProviderIds) => allProviderIds.indexOf(providerId) === index);

  return providerIds.map((providerId: string) => {
    const source = coverage.get(providerId);
    const profile = profiles.get(providerId);
    const setting: SourceConfigStatusEntry | undefined = settings.get(providerId);
    const keyState = setting
      ? `${setting.key_requirement}/${setting.validation_state}`
      : source?.key_requirement ?? (profile?.requires_api_key ? "required" : "none");
    const quarantineState = profile?.quarantine_state
      ?? (source?.status === "quarantined" ? "provider_quarantined" : "none");
    const citation = profile?.required_citation
      ?? profile?.license_hint
      ?? "source metadata required";
    const datasetVersion = profile?.dataset_version
      ?? profile?.last_verified_at
      ?? (source?.local_dataset || setting?.data_library_path ? "snapshot pending" : "live");
    const operationalStatus = source?.status ?? setting?.status ?? profile?.operational_status ?? "disabled";
    const phaseStatus = source?.phase_status ?? profile?.v35_slice ?? setting?.v35_slice ?? "out_of_current_slice";

    return {
      provider_id: providerId,
      display_name: profile?.display_name ?? providerId,
      provider_status: `${operationalStatus} / ${phaseStatus}`,
      key_state: keyState,
      quarantine_state: quarantineState,
      dataset_version: datasetVersion,
      citation,
      blocking_review_count: source?.blocking_review_count ?? 0,
      review_blockers: source?.review_blockers.join(", ") || "none",
    };
  });
};

export const DatabaseView: React.FC<{
  sourceCoverage: HtlSourceCoverageMatrix;
  sourceProfiles: AtomReasonXSourceProfilesState;
  sourceSettings: AtomReasonXSourceSettingsState;
  syncJobs: HtlSyncJobSummary[];
}> = ({ sourceCoverage, sourceProfiles, sourceSettings, syncJobs }) => {
  const rows = buildDataSourceDisplayRows(sourceCoverage, sourceProfiles, sourceSettings);

  return (
    <section className="database-view">
      <div className="section-header">
        <h2>Data Sources</h2>
        <span>{sourceCoverage.lane}</span>
      </div>
      <table className="dense-table">
        <thead>
          <tr>
            <th>Source</th>
            <th>Status</th>
            <th>Key</th>
            <th>Quarantine</th>
            <th>Dataset</th>
            <th>Citation</th>
            <th>Blocking Reviews</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr key={row.provider_id}>
              <td>
                <strong>{row.display_name}</strong>
                <span>{row.provider_id}</span>
              </td>
              <td>{row.provider_status}</td>
              <td>{row.key_state}</td>
              <td>{row.quarantine_state}</td>
              <td>{row.dataset_version}</td>
              <td>{row.citation}</td>
              <td title={row.review_blockers}>{row.blocking_review_count}</td>
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
