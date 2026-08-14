import React from "react";
import { FileUp, Trash2, FileText, FileCode } from "lucide-react";
import type { KnowledgeLibrarySummary } from "../contracts/types";
import {
  addKnowledgeImport,
  loadKnowledgeImports,
  removeKnowledgeImport,
  type KnowledgeImport,
} from "../lib/knowledge-imports";

const IMPORT_HINTS = ".md and .txt files are imported locally. Binary document import (PDF/docx) is out of scope.";

export const KnowledgeLibraryView: React.FC<{
  summary: KnowledgeLibrarySummary;
}> = ({ summary }) => {
  const [imports, setImports] = React.useState<KnowledgeImport[]>(() => loadKnowledgeImports());
  const fileRef = React.useRef<HTMLInputElement>(null);

  const onFiles = React.useCallback(async (files: FileList | null) => {
    if (!files) return;
    const accepted = Array.from(files).filter((file) => (
      file.name.toLocaleLowerCase().endsWith(".md") || file.name.toLocaleLowerCase().endsWith(".txt")
    ));
    for (const file of accepted) {
      const text = await file.text();
      addKnowledgeImport(file.name, text);
    }
    setImports(loadKnowledgeImports());
  }, []);

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

      <div className="knowledge-import">
        <div className="knowledge-import__head">
          <span className="knowledge-import__title">Local imports</span>
          <button
            type="button"
            className="btn btn--small"
            onClick={() => fileRef.current?.click()}
          >
            <FileUp size={13} aria-hidden="true" />
            Import .md / .txt
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".md,.txt"
            multiple
            hidden
            onChange={(event) => void onFiles(event.currentTarget.files)}
          />
        </div>
        <p className="knowledge-import__hint">{IMPORT_HINTS}</p>
        {imports.length === 0 ? (
          <div className="empty-state">No local imports yet.</div>
        ) : (
          <div className="knowledge-import__list">
            {imports.map((item) => (
              <div className="knowledge-import__row" key={item.id}>
                <span className="knowledge-import__icon" aria-hidden="true">
                  {item.kind === "markdown" ? <FileCode size={14} /> : <FileText size={14} />}
                </span>
                <span className="knowledge-import__name">{item.name}</span>
                <span className="knowledge-import__meta">
                  {item.kind} · {item.text.length} chars · {new Date(item.importedAt).toLocaleString()}
                </span>
                <button
                  type="button"
                  className="knowledge-import__delete"
                  aria-label={`Delete ${item.name}`}
                  onClick={() => {
                    removeKnowledgeImport(item.id);
                    setImports(loadKnowledgeImports());
                  }}
                >
                  <Trash2 size={12} aria-hidden="true" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
};
