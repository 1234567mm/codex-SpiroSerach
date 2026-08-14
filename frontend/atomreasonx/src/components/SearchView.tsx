// Search view — local full-text search over the loaded workbench data
// (screening candidates + source catalog) with a Reasonix-style result list.

import React from "react";
import { Search, FileSearch, Database } from "lucide-react";
import type { ScreeningResultState, SourceCatalogSummary } from "../contracts/types";
import {
  buildSearchDocuments,
  searchDocuments,
  type SearchDocument,
} from "../lib/search";

const KIND_LABELS: Record<SearchDocument["kind"], string> = {
  candidate: "Screening candidate",
  source: "Data source",
};

const KIND_ICONS: Record<SearchDocument["kind"], React.ReactNode> = {
  candidate: <FileSearch size={14} aria-hidden="true" />,
  source: <Database size={14} aria-hidden="true" />,
};

export const SearchView: React.FC<{
  screeningResult?: ScreeningResultState;
  sourceCatalog?: SourceCatalogSummary;
  initialQuery?: string;
}> = ({ screeningResult, sourceCatalog, initialQuery = "" }) => {
  const [query, setQuery] = React.useState(initialQuery);
  const documents = React.useMemo(() => buildSearchDocuments({
    candidates: screeningResult?.candidates,
    catalogEntries: sourceCatalog?.families.flatMap((family) => family.entries),
  }), [screeningResult, sourceCatalog]);
  const hits = React.useMemo(() => searchDocuments(documents, query), [documents, query]);

  return (
    <div className="search-view">
      <div className="search-view__header">
        <span className="search-view__title">Local Search</span>
        <span className="search-view__meta">{documents.length} indexed records</span>
      </div>
      <div className="search-view__box">
        <Search size={16} aria-hidden="true" />
        <input
          className="search-view__input"
          value={query}
          onChange={(event) => setQuery(event.currentTarget.value)}
          placeholder="Search screening candidates and data sources…"
          aria-label="Local search"
        />
        {query && <span className="search-view__count">{hits.length} hits</span>}
      </div>
      <div className="search-view__results">
        {!query.trim() && (
          <div className="empty-state">Type to search the loaded workbench records.</div>
        )}
        {query.trim() && hits.length === 0 && (
          <div className="empty-state">No local records match “{query}”.</div>
        )}
        {hits.map((hit) => {
          const doc = hit.document;
          return (
            <article className="search-result" key={doc.id}>
              <div className="search-result__head">
                <span className="search-result__icon">{KIND_ICONS[doc.kind]}</span>
                <span className="search-result__title">{doc.title}</span>
                <span className="badge badge--neutral">{KIND_LABELS[doc.kind]}</span>
              </div>
              {doc.body && <div className="search-result__body">{doc.body.slice(0, 220)}</div>}
              {doc.meta.length > 0 && (
                <div className="search-result__meta">
                  {doc.meta.slice(0, 4).map((item) => (
                    <span className="search-result__tag" key={item}>{item}</span>
                  ))}
                </div>
              )}
            </article>
          );
        })}
      </div>
    </div>
  );
};
