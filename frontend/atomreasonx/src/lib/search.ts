// Local full-text search over the loaded workbench data (screening candidates,
// source catalog). A lightweight in-memory index with simple relevance scoring —
// the FTS-style surface the UI needs today; swappable for SQLite/FTS5 when a
// backend index lands.

export interface SearchDocument {
  id: string;
  kind: "candidate" | "source";
  title: string;
  body: string;
  meta: string[];
}

export interface SearchHit {
  document: SearchDocument;
  score: number;
}

const STOP_WORDS = new Set([
  "the", "a", "an", "of", "for", "and", "or", "to", "in", "on", "with", "by", "is", "are",
  "htl", "v35", "v37", "spiro",
]);

export function tokenize(text: string): string[] {
  return text
    .toLocaleLowerCase()
    .split(/[^a-z0-9]+/)
    .filter((token) => token.length >= 2 && !STOP_WORDS.has(token));
}

/** Score a query against a document: substring hits + term overlaps, title-weighted. */
export function scoreDocument(queryTokens: string[], document: SearchDocument): number {
  const title = document.title.toLocaleLowerCase();
  const body = document.body.toLocaleLowerCase();
  const meta = document.meta.map((item) => item.toLocaleLowerCase());
  let score = 0;
  for (const token of queryTokens) {
    if (title.includes(token)) score += 10;
    if (meta.some((item) => item.includes(token))) score += 6;
    score += body.split(token).length - 1;
  }
  return score;
}

export function searchDocuments(documents: SearchDocument[], query: string): SearchHit[] {
  const trimmed = query.trim();
  if (!trimmed) return [];
  const tokens = tokenize(trimmed);
  if (tokens.length === 0) return [];
  return documents
    .map((document) => ({ document, score: scoreDocument(tokens, document) }))
    .filter((hit) => hit.score > 0)
    .sort((a, b) => b.score - a.score);
}

export interface ScreeningCandidateSource {
  record_id?: string;
  material_id?: string;
  source_id?: string;
  score?: number;
  homo_ev?: number;
  lumo_ev?: number;
  band_gap_ev?: number;
  record?: Record<string, unknown>;
}

export interface CatalogEntrySource {
  provider?: string;
  display_name?: string;
  source_family?: string;
  data_library_path?: string;
}

export interface SearchableWorkspaceSlice {
  candidates?: ScreeningCandidateSource[];
  catalogEntries?: CatalogEntrySource[];
}

export const buildSearchDocuments = (slice: SearchableWorkspaceSlice): SearchDocument[] => {
  const documents: SearchDocument[] = [];
  for (const candidate of slice.candidates ?? []) {
    const recordText = Object.entries(candidate.record ?? {})
      .map(([key, value]) => `${key}: ${String(value)}`)
      .join(" ");
    documents.push({
      id: `candidate:${candidate.material_id ?? candidate.record_id ?? "unknown"}`,
      kind: "candidate",
      title: candidate.material_id ?? candidate.record_id ?? "candidate",
      body: recordText,
      meta: [
        candidate.source_id ?? "",
        candidate.material_id ?? "",
        ...Object.keys(candidate.record ?? {}),
      ].filter(Boolean),
    });
  }
  for (const entry of slice.catalogEntries ?? []) {
    documents.push({
      id: `source:${entry.provider ?? entry.display_name ?? "unknown"}`,
      kind: "source",
      title: entry.display_name ?? entry.provider ?? "source",
      body: [
        entry.source_family ?? "",
        entry.data_library_path ?? "",
        entry.provider ?? "",
      ].join(" "),
      meta: [entry.provider ?? "", entry.source_family ?? ""].filter(Boolean),
    });
  }
  return documents;
};
