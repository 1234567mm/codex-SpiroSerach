// Backup export — packages session history and knowledge imports into a single
// JSON document for download (knowledge-base style local backup). Binary ZIP
// bundling is out of scope by design.

import { loadKnowledgeImports } from "./knowledge-imports";

export interface BackupPayload {
  schemaVersion: "v1";
  exportedAt: string;
  sessions: unknown;
  knowledgeImports: unknown;
}

export const buildBackupPayload = (sessions: unknown): BackupPayload => ({
  schemaVersion: "v1",
  exportedAt: new Date().toISOString(),
  sessions,
  knowledgeImports: loadKnowledgeImports(),
});

export function downloadBackup(payload: BackupPayload): void {
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  const stamp = new Date().toISOString().slice(0, 10).replace(/-/g, "");
  anchor.href = url;
  anchor.download = `atomreasonx-backup-${stamp}.json`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}
