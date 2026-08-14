import { describe, expect, it } from "vitest";
import { buildBackupPayload } from "../lib/backup";

describe("buildBackupPayload", () => {
  it("packages sessions and knowledge imports with a schema version", () => {
    const payload = buildBackupPayload([{ id: "s-1", title: "Session 1" }]);
    expect(payload.schemaVersion).toBe("v1");
    expect(payload.sessions).toEqual([{ id: "s-1", title: "Session 1" }]);
    expect(Array.isArray(payload.knowledgeImports)).toBe(true);
    expect(payload.exportedAt).toBeTruthy();
  });
});
