import React from "react";
import type { SourceCatalogSummary } from "../contracts/types";

export const SourceCategoriesView: React.FC<{
  catalog?: SourceCatalogSummary;
}> = ({ catalog }) => {
  if (!catalog || catalog.families.length === 0) {
    return (
      <section className="source-categories-view">
        <div className="section-header">
          <h2>Source Categories</h2>
          <span>unavailable</span>
        </div>
        <p className="empty-state">No classified source catalog loaded.</p>
      </section>
    );
  }
  return (
    <section className="source-categories-view">
      <div className="section-header">
        <h2>Source Categories</h2>
        <span>
          {catalog.source_count} sources · {catalog.family_count} categories
        </span>
      </div>
      {catalog.families.map((family) => (
        <div className="catalog-family" key={family.family}>
          <div className="catalog-family-header">
            <strong>{family.family}</strong>
            <span>
              {family.entry_count} sources · {family.acquisition_modes.join(", ")}
            </span>
          </div>
          <table className="catalog-table">
            <thead>
              <tr>
                <th>Source</th>
                <th>Status</th>
                <th>Acquisition</th>
                <th>Local library</th>
              </tr>
            </thead>
            <tbody>
              {family.entries.map((entry) => (
                <tr key={entry.provider}>
                  <td>{entry.display_name}</td>
                  <td>{entry.operational_status}</td>
                  <td>{entry.acquisition_mode}</td>
                  <td>
                    {entry.fixture_status}
                    {entry.local_snapshot_count > 0
                      ? ` · ${entry.local_snapshot_count} snapshots`
                      : ""}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
    </section>
  );
};
