import { describe, expect, it } from "vitest";
import { createRuntimeWorkbenchReadAdapter } from "../adapters/readonly-run-workbench-adapter";
import type { WorkflowTaskRestoreReader } from "../adapters/workflow-task-restore-adapter";
import fixture from "../fixtures/atomreasonx-ui-fixture.json";
import type { AtomReasonXWorkspaceState } from "../contracts/types";

const baseWorkspace = fixture as unknown as AtomReasonXWorkspaceState;

describe("runtime workbench read adapter fixture fallback", () => {
  it("degrades to fixture workspace when restore fails (installed app without repo)", async () => {
    const failingRestore: WorkflowTaskRestoreReader = {
      async restore() {
        throw new Error("workflow task restore unavailable (no repository)");
      },
    };
    const runtime = createRuntimeWorkbenchReadAdapter({
      baseWorkspace,
      readonlyOutputDir: null,
      workflowTaskRestoreReader: failingRestore,
    });
    const workspace = await runtime.adapter.loadWorkspace();
    expect(workspace.app).toBe("AtomX");
    expect(workspace.source_coverage.lane).toBe("htl_only");
    expect(runtime.readOnly).toBe(false);
  });

  it("applies restored tasks when restore succeeds", async () => {
    const restoringReader: WorkflowTaskRestoreReader = {
      async restore() {
        return {
          schema_version: "v35.operator_task_restore.v1",
          read_authorization_scope: "operator_task_snapshots_readonly",
          provider_cache_written: false,
          local_backend_written: false,
          scoring_written: false,
          experiment_written: false,
          restored_tasks: [],
        };
      },
    };
    const runtime = createRuntimeWorkbenchReadAdapter({
      baseWorkspace,
      readonlyOutputDir: null,
      workflowTaskRestoreReader: restoringReader,
    });
    const workspace = await runtime.adapter.loadWorkspace();
    expect(workspace.app).toBe("AtomX");
  });
});
