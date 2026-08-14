// Knowledge imports — local storage of imported .md/.txt notes (markdown/txt
// import, knowledge-base style). Falls back to in-memory state when
// localStorage is unavailable (SSR/tests). Only plain-text formats are
// supported; binary document import (pdf/docx) is out of scope by design.

export interface KnowledgeImport {
  id: string;
  name: string;
  kind: "markdown" | "text";
  text: string;
  importedAt: string;
}

const STORAGE_KEY = "atomreasonx-knowledge-imports-v1";

let memoryItems: KnowledgeImport[] | null = null;

function readAll(): KnowledgeImport[] {
  if (memoryItems) return memoryItems;
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as KnowledgeImport[];
    memoryItems = Array.isArray(parsed) ? parsed : [];
  } catch {
    memoryItems = [];
  }
  return memoryItems;
}

function persist(items: KnowledgeImport[]): void {
  memoryItems = items;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(-100)));
  } catch {
    // storage unavailable: keep in-memory only
  }
}

export function loadKnowledgeImports(): KnowledgeImport[] {
  return [...readAll()];
}

export function addKnowledgeImport(name: string, text: string): KnowledgeImport {
  const kind: KnowledgeImport["kind"] = name.toLocaleLowerCase().endsWith(".md") ? "markdown" : "text";
  const item: KnowledgeImport = {
    id: `imp-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`,
    name,
    kind,
    text,
    importedAt: new Date().toISOString(),
  };
  persist([item, ...readAll()]);
  return item;
}

export function removeKnowledgeImport(id: string): void {
  persist(readAll().filter((item) => item.id !== id));
}
