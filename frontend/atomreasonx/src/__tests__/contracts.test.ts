import { describe, expect, it } from "vitest";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import fixture from "../fixtures/atomreasonx-ui-fixture.json";
import type {
  AtomReasonXCommandResult,
  OperatorTaskExecutionReport,
  AtomReasonXWorkspaceState,
} from "../contracts/types";
import {
  buildWorkbenchCommandRequest,
  createWorkbenchCommandDispatcher,
  type WorkbenchCommandRequest,
} from "../adapters/command-adapter";
import {
  createFixtureWorkbenchReadAdapter,
  createNoopLocalWorkbenchTransport,
  createTransportWorkbenchReadAdapter,
  type WorkbenchReadAdapter,
} from "../adapters/workbench-read-adapter";
import {
  createHttpReadonlyRunTransport,
  readonlyRunUrl,
  type ReadonlyRunEnvelope,
} from "../adapters/go-readonly-run-transport";
import {
  createReadonlyRunWorkbenchReadAdapter,
  createRuntimeWorkbenchReadAdapter,
} from "../adapters/readonly-run-workbench-adapter";
import {
  buildReadonlyRunRecentOutputDirs,
  buildReadonlyRunOperatorConfig,
  normalizeReadonlyRunOutputDir,
  resolveConfiguredReadonlyRecentOutputDirs,
} from "../adapters/readonly-run-operator-config";
import {
  createTauriReadonlyRunSession,
  createTauriReadonlyRunTransport,
  isReadonlySidecarLoopbackBaseUrl,
  redactedReadonlySidecarLaunch,
  stopTauriReadonlySidecar,
  validateReadonlySidecarLaunch,
} from "../adapters/tauri-readonly-sidecar";
import {
  createTauriConfigCommandAdapter,
  createRuntimeWorkbenchCommandAdapter,
} from "../adapters/tauri-command-adapter";
import {
  DEFAULT_OPERATOR_TASK_LEDGER_PATH,
  OPERATOR_TASK_EXECUTION_SCHEMA_VERSION,
  buildWorkflowTaskExecutionRequest,
  canExecuteWorkflowTask,
  createTauriWorkflowTaskExecutor,
  projectWorkflowTaskExecutionReport,
  validateOperatorTaskExecutionReport,
} from "../adapters/workflow-task-execution-adapter";
import {
  OPERATOR_TASK_RESTORE_SCHEMA_VERSION,
  createTauriWorkflowTaskRestoreReader,
  projectWorkflowTaskRestoreReport,
  type OperatorTaskRestoreReport,
  validateOperatorTaskRestoreReport,
} from "../adapters/workflow-task-restore-adapter";
import { projectSourceSettingsCommandResult } from "../adapters/source-settings-command-projection";
import { projectWorkflowCommandTaskResult } from "../adapters/workflow-command-task-projection";
import {
  createLoadingWorkbenchWorkspaceState,
  loadWorkbenchWorkspace,
} from "../stores/workspace-store";
import { buildDataSourceDisplayRows } from "../components/DatabaseView";
import {
  DEFAULT_MATERIALS_PROJECT_PROBE_FORMULA,
  SOURCE_PROVIDER_CONNECTION_PROBE_SCHEMA_VERSION,
  buildSourceProviderTestConnectionPayload,
  buildSourceSettingsCommandPayload,
  submitSourceProviderTestConnectionCommand,
  submitSourceSettingsCommand,
} from "../components/SettingsModal";
import {
  WorkflowView,
  buildWorkflowCommandPayload,
  canSubmitWorkflowCommandAction,
  submitWorkflowCommandAction,
} from "../components/WorkflowView";

const COMMAND_CONTROL_MODULES = import.meta.glob<string>("../components/{WorkflowView,SettingsModal}.tsx", {
  eager: true,
  import: "default",
  query: "?raw",
});
const MAIN_MODULE = import.meta.glob<string>("../main.tsx", {
  eager: true,
  import: "default",
  query: "?raw",
});
const APP_SHELL_MODULE = import.meta.glob<string>("../AppShell.tsx", {
  eager: true,
  import: "default",
  query: "?raw",
});

const executionReportForTask = (
  task: Pick<AtomReasonXWorkspaceState["operator_tasks"][number], "task_id" | "admission_hash">,
  overrides: Partial<OperatorTaskExecutionReport> = {},
): OperatorTaskExecutionReport => ({
  schema_version: OPERATOR_TASK_EXECUTION_SCHEMA_VERSION,
  task_id: task.task_id,
  action_type: "start_nomad_sync",
  provider: "nomad_perla_psc",
  admission_hash: task.admission_hash ?? "a".repeat(64),
  execution_status: "source_snapshot_written",
  write_authorization_scope: "source_snapshot_only",
  live_calls_authorized: true,
  provider_cache_written: false,
  local_backend_written: false,
  scoring_written: false,
  experiment_written: false,
  started_at: "2026-07-25T00:00:00Z",
  target_data_library_path: `data/lib/nomad_perla_psc/snapshots/run-${task.task_id}`,
  source_manifest_path: `data/lib/nomad_perla_psc/snapshots/run-${task.task_id}/source-manifest.json`,
  normalized_record_count: 2,
  provider_response_hash: "b".repeat(64),
  raw_search_hash: "c".repeat(64),
  raw_archive_hash: "d".repeat(64),
  archive_status: "available",
  review_required: false,
  review_reasons: [],
  ...overrides,
});

const restoreReportForTasks = (
  restored_tasks: AtomReasonXWorkspaceState["operator_tasks"],
): OperatorTaskRestoreReport => ({
  schema_version: OPERATOR_TASK_RESTORE_SCHEMA_VERSION,
  read_authorization_scope: "operator_task_snapshots_readonly",
  provider_cache_written: false,
  local_backend_written: false,
  scoring_written: false,
  experiment_written: false,
  restored_tasks,
});

describe("AtomReasonX contract fixtures", () => {
  it("loads workspace through the read adapter as a defensive fixture snapshot", async () => {
    const workspace = fixture as unknown as AtomReasonXWorkspaceState;
    const adapter = createFixtureWorkbenchReadAdapter(workspace);

    const loaded = await adapter.loadWorkspace();
    loaded.source_coverage.sources[0].provider_id = "mutated";

    expect(workspace.source_coverage.sources[0].provider_id).not.toBe("mutated");
    expect((await adapter.loadWorkspace()).source_profiles.profiles.map(profile => profile.provider_id)).toContain("materials_project");
  });

  it("models workspace store loading ready and error states", async () => {
    const workspace = fixture as unknown as AtomReasonXWorkspaceState;
    const ready = await loadWorkbenchWorkspace(createTransportWorkbenchReadAdapter(
      createNoopLocalWorkbenchTransport(workspace),
    ));
    const broken: WorkbenchReadAdapter = {
      async loadWorkspace() {
        throw new Error("read backend unavailable");
      },
    };

    expect(createLoadingWorkbenchWorkspaceState().status).toBe("loading");
    expect(ready.status).toBe("ready");
    if (ready.status === "ready") {
      expect(ready.workspace.source_coverage.lane).toBe("htl_only");
    }
    await expect(createNoopLocalWorkbenchTransport(workspace).request("missing" as never)).rejects.toThrow(
      "unsupported workbench read surface",
    );
    expect(await loadWorkbenchWorkspace(broken)).toEqual({
      status: "error",
      message: "read backend unavailable",
    });
  });

  it("projects Go readonly run envelopes into a defensive AtomReasonX workspace snapshot", async () => {
    const baseWorkspace = fixture as unknown as AtomReasonXWorkspaceState;
    const requestedSurfaces: string[] = [];
    const envelope = (
      surface: ReadonlyRunEnvelope["surface"],
      payload: unknown,
      artifactKind: string | null = null,
    ): ReadonlyRunEnvelope => ({
      schema_version: "v11.readonly_api.envelope.v1",
      status: "available",
      severity: "info",
      surface,
      read_only: true,
      run_id: "readonly-run-1",
      artifact_kind: artifactKind,
      source: {
        backend: "json_artifact_repository",
        manifest_path: "run-manifest.json",
      },
      payload,
      unavailable: null,
    });
    const adapter = createReadonlyRunWorkbenchReadAdapter({
      baseWorkspace,
      transport: {
        async read(surface) {
          requestedSurfaces.push(surface);
          if (surface === "manifest") {
            return envelope("manifest", {
              schema_version: "v6.run_manifest.v1",
              run_id: "readonly-run-1",
              generated_at: "2026-07-24T00:00:00+00:00",
              producer_version: "spirosearch-v35",
              candidate_count: 2,
              context: {
                provider_outcomes: {
                  hit_count: 2,
                  miss_count: 1,
                },
              },
            });
          }
          if (surface === "artifact_index") {
            return envelope("artifact_index", {
              artifact_count: 5,
              artifacts: [
                { kind: "scoring_view" },
                { kind: "review_summary" },
                { kind: "provider_cache", record_count: 4 },
                { kind: "provider_cache_index" },
                { kind: "agent_trace", record_count: 3 },
              ],
            });
          }
          if (surface === "scoring_view") {
            return envelope("scoring_view", {
              kind: "scoring_view",
              data: {
                schema_version: "v10.scoring_view.v1",
                energy_facts: [
                  { evidence_id: "energy-1" },
                  { evidence_id: "energy-2" },
                ],
              },
            }, "scoring_view");
          }
          if (surface === "review_summary") {
            return envelope("review_summary", {
              kind: "review_summary",
              data: {
                schema_version: "v10.review_summary.v1",
                run_id: "readonly-run-1",
                generated_at: "2026-07-24T00:00:00+00:00",
                review_count: 5,
                open_blocking_count: 3,
              },
            }, "review_summary");
          }
          if (surface === "provider_lineage") {
            return envelope("provider_lineage", {
              provider_cache: { kind: "provider_cache", record_count: 4, records: [{}, {}, {}, {}] },
              provider_cache_index: { kind: "provider_cache_index", data: {} },
              agent_trace: { kind: "agent_trace", record_count: 3, records: [{}, {}, {}] },
            });
          }
          throw new Error(`unexpected surface ${surface}`);
        },
      },
    });

    const workspace = await adapter.loadWorkspace();
    workspace.source_coverage.sources[0].provider_id = "mutated";

    expect(requestedSurfaces).toEqual([
      "manifest",
      "artifact_index",
      "scoring_view",
      "review_summary",
      "provider_lineage",
    ]);
    expect(workspace.active_workspace).toBe("readonly_run:readonly-run-1");
    expect(workspace._provisional).toBe(false);
    expect(workspace.knowledge_library).toMatchObject({
      candidate_entities: 2,
      extracted_claims: 2,
      provider_snapshots: 4,
      blocked_review_items: 3,
      index_freshness: "2026-07-24T00:00:00+00:00",
    });
    expect(workspace.telemetry.fields.find(field => field.name === "retrieval_hit_count")).toMatchObject({
      value: 2,
      source: "runtime_computed",
    });
    expect(workspace.telemetry.fields.find(field => field.name === "average_hit_rate")).toMatchObject({
      value: 0.6667,
      source: "runtime_computed",
    });
    expect(workspace.telemetry.fields.find(field => field.name === "active_session_state")).toMatchObject({
      value: "readonly_run",
      source: "runtime_computed",
    });
    expect(workspace.telemetry.fields.find(field => field.name === "provider_usage")).toMatchObject({
      value: {
        provider_cache_records: 4,
        agent_trace_records: 3,
      },
      source: "runtime_computed",
    });
    expect(baseWorkspace.source_coverage.sources[0].provider_id).not.toBe("mutated");
    expect("submit" in adapter).toBe(false);
    expect("execute" in adapter).toBe(false);
  });

  it("fails closed instead of projecting unavailable readonly run surfaces", async () => {
    const adapter = createReadonlyRunWorkbenchReadAdapter({
      baseWorkspace: fixture as unknown as AtomReasonXWorkspaceState,
      transport: {
        async read(surface) {
          if (surface === "manifest") {
            return {
              schema_version: "v11.readonly_api.envelope.v1",
              status: "available",
              severity: "info",
              surface,
              read_only: true,
              run_id: "readonly-run-1",
              artifact_kind: null,
              source: {
                backend: "json_artifact_repository",
                manifest_path: "run-manifest.json",
              },
              payload: { run_id: "readonly-run-1" },
              unavailable: null,
            };
          }
          return {
            schema_version: "v11.readonly_api.envelope.v1",
            status: "unavailable",
            severity: "error",
            surface,
            read_only: true,
            run_id: "readonly-run-1",
            artifact_kind: surface === "artifact_index" ? null : surface,
            source: {
              backend: "json_artifact_repository",
              manifest_path: "run-manifest.json",
            },
            payload: null,
            unavailable: {
              code: "artifact_path_unsafe",
            },
          };
        },
      },
    });

    await expect(adapter.loadWorkspace()).rejects.toThrow(
      "readonly artifact_index is not available: artifact_path_unsafe",
    );
  });

  it("guards runtime bootstrap between fixture mode and disposable Tauri readonly sidecar mode", async () => {
    const baseWorkspace = fixture as unknown as AtomReasonXWorkspaceState;
    const fixtureRuntime = createRuntimeWorkbenchReadAdapter({ baseWorkspace, readonlyOutputDir: "" });
    const stopped: number[] = [];
    const readonlyRuntime = createRuntimeWorkbenchReadAdapter({
      baseWorkspace,
      readonlyOutputDir: "D:\\runs\\readonly",
      createSidecarSession: async ({ outputDir }) => {
        expect(outputDir).toBe("D:\\runs\\readonly");
        return {
          launch: {
            base_url: "http://127.0.0.1:49152",
            run_id: "readonly-run-1",
            read_only: true,
            readonly_token: "0123456789abcdef",
            process_id: 4242,
          },
          transport: {
            async read(surface) {
              const payloadBySurface: Record<string, unknown> = {
                manifest: {
                  run_id: "readonly-run-1",
                  generated_at: "2026-07-24T00:00:00+00:00",
                },
                artifact_index: {
                  artifact_count: 3,
                  artifacts: [
                    { kind: "scoring_view" },
                    { kind: "review_summary" },
                    { kind: "provider_cache" },
                  ],
                },
                scoring_view: {
                  kind: "scoring_view",
                  data: {
                    schema_version: "v10.scoring_view.v1",
                    energy_facts: [],
                  },
                },
                review_summary: {
                  kind: "review_summary",
                  data: {
                    schema_version: "v10.review_summary.v1",
                    open_blocking_count: 0,
                  },
                },
                provider_lineage: {
                  provider_cache: { kind: "provider_cache", record_count: 0 },
                  provider_cache_index: { kind: "provider_cache_index", data: {} },
                  agent_trace: { kind: "agent_trace", record_count: 0 },
                },
              };
              return {
                schema_version: "v11.readonly_api.envelope.v1",
                status: "available",
                severity: "info",
                surface,
                read_only: true,
                run_id: "readonly-run-1",
                artifact_kind: surface === "scoring_view" || surface === "review_summary" ? surface : null,
                source: {
                  backend: "json_artifact_repository",
                  manifest_path: "run-manifest.json",
                },
                payload: payloadBySurface[surface],
                unavailable: null,
              };
            },
          },
          stop: async () => {
            stopped.push(4242);
          },
        };
      },
    });

    await expect(fixtureRuntime.adapter.loadWorkspace()).resolves.toMatchObject({
      active_workspace: baseWorkspace.active_workspace,
    });
    expect(fixtureRuntime.readOnly).toBe(false);
    expect(readonlyRuntime.readOnly).toBe(true);
    await expect(readonlyRuntime.adapter.loadWorkspace()).resolves.toMatchObject({
      active_workspace: "readonly_run:readonly-run-1",
      _provisional: false,
    });
    await readonlyRuntime.dispose();
    expect(stopped).toEqual([4242]);
  });

  it("models operator readonly run configuration as a read-side output directory only", () => {
    const readonlyConfig = buildReadonlyRunOperatorConfig("  D:\\runs\\readonly-v35  ");
    const fixtureConfig = buildReadonlyRunOperatorConfig("   ");
    const recent = buildReadonlyRunRecentOutputDirs([
      " D:\\runs\\readonly-v35 ",
      "D:\\runs\\readonly-v35",
      "",
      "C:\\bin\\spiroctl.exe",
      "readonly_token=secret",
      "api_key=secret",
    ], "D:\\runs\\active-run");

    expect(normalizeReadonlyRunOutputDir("  D:\\runs\\readonly-v35  ")).toBe("D:\\runs\\readonly-v35");
    expect(normalizeReadonlyRunOutputDir("   ")).toBeNull();
    expect(normalizeReadonlyRunOutputDir("C:\\bin\\spiroctl.exe")).toBeNull();
    expect(normalizeReadonlyRunOutputDir("readonly_token=secret")).toBeNull();
    expect(readonlyConfig).toEqual({
      mode: "readonly_run",
      outputDir: "D:\\runs\\readonly-v35",
      readOnly: true,
    });
    expect(fixtureConfig).toEqual({
      mode: "fixture",
      outputDir: null,
      readOnly: false,
    });
    expect(recent).toEqual([
      { outputDir: "D:\\runs\\active-run", label: "active-run", source: "active" },
      { outputDir: "D:\\runs\\readonly-v35", label: "readonly-v35", source: "recent" },
    ]);
    expect(JSON.stringify(readonlyConfig)).not.toContain("api_key");
    expect(JSON.stringify(readonlyConfig)).not.toContain("readonly_token");
    expect(JSON.stringify(readonlyConfig)).not.toContain("spiroctl");
    expect(JSON.stringify(recent)).not.toContain("api_key");
    expect(JSON.stringify(recent)).not.toContain("readonly_token");
    expect(JSON.stringify(recent)).not.toContain("spiroctl");
  });

  it("resolves recent readonly run directories without browser persistence or command paths", () => {
    const previousRecent = (globalThis as {
      __ATOMREASONX_READONLY_RECENT_OUTPUT_DIRS__?: unknown;
    }).__ATOMREASONX_READONLY_RECENT_OUTPUT_DIRS__;
    (globalThis as {
      __ATOMREASONX_READONLY_RECENT_OUTPUT_DIRS__?: unknown;
    }).__ATOMREASONX_READONLY_RECENT_OUTPUT_DIRS__ = [
      "D:\\runs\\one",
      "D:\\runs\\one",
      "C:\\tools\\spiroctl.exe",
      "readonly_token=secret",
    ];
    try {
      expect(resolveConfiguredReadonlyRecentOutputDirs()).toEqual(["D:\\runs\\one"]);
    } finally {
      (globalThis as {
        __ATOMREASONX_READONLY_RECENT_OUTPUT_DIRS__?: unknown;
      }).__ATOMREASONX_READONLY_RECENT_OUTPUT_DIRS__ = previousRecent;
    }
  });

  it("wires operator readonly run configuration through runtime read adapter state only", () => {
    const mainSource = Object.values(MAIN_MODULE)[0] ?? "";

    expect(mainSource).toContain("readonlyOutputDir");
    expect(mainSource).toContain("setReadonlyOutputDir");
    expect(mainSource).toContain("readonlyRecentOutputDirs");
    expect(mainSource).toContain("buildReadonlyRunRecentOutputDirs");
    expect(mainSource).toContain("createRuntimeWorkbenchReadAdapter");
    expect(mainSource).toContain("projectWorkflowCommandTaskResult");
    expect(mainSource).toContain("readonlyRunConfig");
    expect(mainSource).toContain("onApplyReadonlyRunOutputDir");
    expect(mainSource).toContain("workspaceState.status === \"error\"");
    expect(mainSource).toContain("<SettingsModal");
    expect(mainSource).toContain("runtimeReadAdapter.readOnly");
    expect(mainSource).toContain("!runtimeReadAdapter.readOnly");
    expect(mainSource).toContain(": undefined");
    expect(mainSource).not.toContain("spiroctlPath");
    expect(mainSource).not.toContain("localStorage");
    expect(mainSource).not.toContain("readonly_token");
  });

  it("wires SettingsModal recent readonly run selection without command or picker side effects", () => {
    const settingsSource = Object.entries(COMMAND_CONTROL_MODULES)
      .find(([path]) => path.includes("SettingsModal"))?.[1] ?? "";

    expect(settingsSource).toContain("readonlyRecentOutputDirs");
    expect(settingsSource).toContain("Recent readonly run output directories");
    expect(settingsSource).toContain("setReadonlyOutputDirDraft(event.currentTarget.value)");
    expect(settingsSource).toContain("onApplyReadonlyRunOutputDir");
    expect(settingsSource).not.toContain("showDirectoryPicker");
    expect(settingsSource).not.toContain("open(");
    expect(settingsSource).not.toContain("readonly_token");
    expect(settingsSource).not.toContain("spiroctlPath");
  });

  it("wires workflow operator tasks through workflow view without read-side imports", () => {
    const workflowSource = Object.entries(COMMAND_CONTROL_MODULES)
      .find(([path]) => path.includes("WorkflowView"))?.[1] ?? "";
    const appShellSource = Object.values(APP_SHELL_MODULE)[0] ?? "";

    expect(workflowSource).toContain("operatorTasks");
    expect(workflowSource).toContain("operator-task-list");
    expect(workflowSource).toContain("workflowTaskExecutor");
    expect(workflowSource).toContain("workflowProjectionKey");
    expect(workflowSource).toContain("onWorkflowTaskExecuted");
    expect(workflowSource).toContain("execution_report");
    expect(workflowSource).toContain("source_manifest_path");
    expect(workflowSource).toContain("canExecuteWorkflowTask");
    expect(workflowSource).toContain("execute(task)");
    expect(appShellSource).toContain("operatorTasks={workspace.operator_tasks}");
    expect(appShellSource).toContain("workflowTaskExecutor={workflowTaskExecutor}");
    expect(appShellSource).toContain("workflowProjectionKey={workflowProjectionKey}");
    expect(appShellSource).toContain("onWorkflowTaskExecuted={onWorkflowTaskExecuted}");
    expect(Object.values(MAIN_MODULE)[0]).toContain("workspaceResetKeyRef");
    expect(Object.values(MAIN_MODULE)[0]).toContain("projectionKey !== workspaceResetKeyRef.current");
    expect(workflowSource).not.toContain("workbench-read-adapter");
    expect(workflowSource).not.toContain("read-only-artifact-adapter");
  });

  it("renders workflow execution report rows and disables executed tasks", () => {
    const workspace = fixture as unknown as AtomReasonXWorkspaceState;
    const admittedTask = {
      schema_version: "v35.operator_task.v1",
      task_id: "task-start_nomad_sync-ab12cd",
      action_type: "start_nomad_sync",
      provider: "nomad_perla_psc",
      provider_scope: "source",
      status: "queued",
      queue_scope: "operator_local",
      declared_effects: ["provider_sync_jobs"],
      writes_authorized: false,
      execution_started: false,
      created_at: null,
      config: { transport: "operator_task_queue", runtime_writes: false },
      admission_status: "admitted",
      admission_hash: "a".repeat(64),
      ledger_path: DEFAULT_OPERATOR_TASK_LEDGER_PATH,
      admission_source: "operator_task_ledger",
    } satisfies AtomReasonXWorkspaceState["operator_tasks"][number];
    const report = {
      schema_version: OPERATOR_TASK_EXECUTION_SCHEMA_VERSION,
      task_id: admittedTask.task_id,
      action_type: "start_nomad_sync",
      provider: "nomad_perla_psc",
      admission_hash: admittedTask.admission_hash,
      execution_status: "source_snapshot_written",
      write_authorization_scope: "source_snapshot_only",
      live_calls_authorized: true,
      provider_cache_written: false,
      local_backend_written: false,
      scoring_written: false,
      experiment_written: false,
      started_at: "2026-07-25T00:00:00Z",
      target_data_library_path: `data/lib/nomad_perla_psc/snapshots/run-${admittedTask.task_id}`,
      source_manifest_path: `data/lib/nomad_perla_psc/snapshots/run-${admittedTask.task_id}/source-manifest.json`,
      normalized_record_count: 2,
      provider_response_hash: "b".repeat(64),
      raw_search_hash: "c".repeat(64),
      raw_archive_hash: "d".repeat(64),
      archive_status: "rate_limited",
      review_required: true,
      review_reasons: ["archive_rate_limited"],
    } satisfies OperatorTaskExecutionReport;
    const executor = { execute: async () => report };
    const admittedMarkup = renderToStaticMarkup(React.createElement(WorkflowView, {
      workflow: workspace.workflow,
      commandActions: [],
      operatorTasks: [admittedTask],
      workflowTaskExecutor: executor,
      workflowProjectionKey: "fixture:perovskite_htl_screening:0",
      onWorkflowTaskExecuted: () => undefined,
    }));
    const executedMarkup = renderToStaticMarkup(React.createElement(WorkflowView, {
      workflow: workspace.workflow,
      commandActions: [],
      operatorTasks: [{ ...admittedTask, execution_report: report }],
      workflowTaskExecutor: executor,
      workflowProjectionKey: "fixture:perovskite_htl_screening:0",
      onWorkflowTaskExecuted: () => undefined,
    }));

    expect(admittedMarkup).toContain(">Execute</button>");
    expect(admittedMarkup).not.toContain("operator-task-report");
    expect(executedMarkup).toContain("operator-task-report");
    expect(executedMarkup).toContain("source_snapshot_written");
    expect(executedMarkup).toContain("2 records");
    expect(executedMarkup).toContain("rate_limited");
    expect(executedMarkup).toContain("archive_rate_limited");
    expect(executedMarkup).toContain(report.source_manifest_path);
    expect(executedMarkup).toContain("disabled");
    expect(executedMarkup).not.toContain("api_key");
    expect(executedMarkup).not.toContain("readonly_token");
    expect(executedMarkup).not.toContain("spiroctl.exe");
  });

  it("reads Go readonly run envelopes through a side-effect-free transport facade", async () => {
    const requestedPaths: string[] = [];
    const requestedInits: Array<RequestInit | undefined> = [];
    const envelope = (
      surface: ReadonlyRunEnvelope["surface"],
      artifactKind: string | null = null,
    ): ReadonlyRunEnvelope => ({
      schema_version: "v11.readonly_api.envelope.v1",
      status: "available",
      severity: "info",
      surface,
      read_only: true,
      run_id: "run-1",
      artifact_kind: artifactKind,
      source: {
        backend: "json_artifact_repository",
        manifest_path: "run-manifest.json",
      },
      payload: {},
      unavailable: null,
    });
    const envelopesByPath: Record<string, ReadonlyRunEnvelope> = {
      "/runs/run-1/manifest": envelope("manifest"),
      "/runs/run-1/artifacts": envelope("artifact_index"),
      "/runs/run-1/artifacts/scoring_view": envelope("artifact_by_kind", "scoring_view"),
      "/runs/run-1/scoring-view": envelope("scoring_view", "scoring_view"),
      "/runs/run-1/review-summary": envelope("review_summary", "review_summary"),
      "/runs/run-1/provider-lineage": envelope("provider_lineage"),
    };
    const transport = createHttpReadonlyRunTransport({
      baseUrl: "http://127.0.0.1:47311",
      runId: "run-1",
      fetchJson: async (url, init) => {
        const path = new URL(url).pathname;
        requestedPaths.push(path);
        requestedInits.push(init);
        const result = envelopesByPath[path];
        if (!result) {
          throw new Error(`unexpected path: ${path}`);
        }
        return result;
      },
    });

    await expect(transport.read("manifest")).resolves.toMatchObject({ surface: "manifest" });
    await expect(transport.read("artifact_index")).resolves.toMatchObject({ surface: "artifact_index" });
    await expect(transport.read("artifact_by_kind", { artifactKind: "scoring_view" })).resolves.toMatchObject({
      surface: "artifact_by_kind",
      artifact_kind: "scoring_view",
    });
    await expect(transport.read("scoring_view")).resolves.toMatchObject({ surface: "scoring_view" });
    await expect(transport.read("review_summary")).resolves.toMatchObject({ surface: "review_summary" });
    await expect(transport.read("provider_lineage")).resolves.toMatchObject({ surface: "provider_lineage" });

    expect(requestedPaths).toEqual([
      "/runs/run-1/manifest",
      "/runs/run-1/artifacts",
      "/runs/run-1/artifacts/scoring_view",
      "/runs/run-1/scoring-view",
      "/runs/run-1/review-summary",
      "/runs/run-1/provider-lineage",
    ]);
    expect(requestedInits.every(init => init?.method === "GET" && init.headers === undefined)).toBe(true);
    expect("submit" in transport).toBe(false);
    expect("execute" in transport).toBe(false);
    expect("sync" in transport).toBe(false);
  });

  it("sends an optional readonly token without command credentials", async () => {
    const requestedInits: Array<RequestInit | undefined> = [];
    const envelope: ReadonlyRunEnvelope = {
      schema_version: "v11.readonly_api.envelope.v1",
      status: "available",
      severity: "info",
      surface: "manifest",
      read_only: true,
      run_id: "run-1",
      artifact_kind: null,
      source: {
        backend: "json_artifact_repository",
        manifest_path: "run-manifest.json",
      },
      payload: {},
      unavailable: null,
    };
    const transport = createHttpReadonlyRunTransport({
      baseUrl: "http://127.0.0.1:47311/",
      runId: "run-1",
      readonlyToken: " readonly-token-1 ",
      fetchJson: async (_url, init) => {
        requestedInits.push(init);
        return envelope;
      },
    });

    await expect(transport.read("manifest")).resolves.toMatchObject({ surface: "manifest" });

    expect(requestedInits).toEqual([{
      method: "GET",
      headers: {
        Authorization: "Bearer readonly-token-1",
      },
    }]);
    expect("submit" in transport).toBe(false);
    expect("execute" in transport).toBe(false);
    expect("sync" in transport).toBe(false);
  });

  it("encodes readonly run ids and artifact kinds as path segments", () => {
    const url = readonlyRunUrl(
      "http://127.0.0.1:47311/",
      "run id/1",
      "artifact_by_kind",
      "scoring view/unsafe",
    );

    expect(new URL(url).pathname).toBe("/runs/run%20id%2F1/artifacts/scoring%20view%2Funsafe");
  });

  it("creates readonly HTTP transport from a private Tauri sidecar launch", async () => {
    const invokeCalls: Array<{ command: string; args?: Record<string, unknown> }> = [];
    const fetchInits: Array<RequestInit | undefined> = [];
    const launch = {
      base_url: "http://127.0.0.1:49152",
      run_id: "run-1",
      read_only: true as const,
      readonly_token: "0123456789abcdef",
      process_id: 4242,
    };
    const envelope: ReadonlyRunEnvelope = {
      schema_version: "v11.readonly_api.envelope.v1",
      status: "available",
      severity: "info",
      surface: "manifest",
      read_only: true,
      run_id: "run-1",
      artifact_kind: null,
      source: {
        backend: "json_artifact_repository",
        manifest_path: "run-manifest.json",
      },
      payload: {},
      unavailable: null,
    };

    const transport = await createTauriReadonlyRunTransport({
      outputDir: "D:\\runs\\v11",
      invoke: async (command, args) => {
        invokeCalls.push({ command, args });
        return launch as never;
      },
      fetchJson: async (url, init) => {
        expect(new URL(url).pathname).toBe("/runs/run-1/manifest");
        fetchInits.push(init);
        return envelope;
      },
    });

    await expect(transport.read("manifest")).resolves.toMatchObject({ surface: "manifest" });

    expect(invokeCalls).toEqual([{
      command: "start_readonly_sidecar",
      args: {
        outputDir: "D:\\runs\\v11",
      },
    }]);
    expect(fetchInits).toEqual([{
      method: "GET",
      headers: {
        Authorization: "Bearer 0123456789abcdef",
      },
    }]);
    expect("submit" in transport).toBe(false);
    expect("execute" in transport).toBe(false);
    expect("sync" in transport).toBe(false);
  });

  it("redacts readonly sidecar tokens and stops sidecar by process id only", async () => {
    const launch = validateReadonlySidecarLaunch({
      base_url: "http://127.0.0.1:49152",
      run_id: "run-1",
      read_only: true,
      readonly_token: "0123456789abcdef",
      process_id: 4242,
    });
    const invokeCalls: Array<{ command: string; args?: Record<string, unknown> }> = [];

    await stopTauriReadonlySidecar(launch.process_id, async (command, args) => {
      invokeCalls.push({ command, args });
      return undefined as never;
    });

    expect(redactedReadonlySidecarLaunch(launch)).toEqual({
      base_url: "http://127.0.0.1:49152",
      run_id: "run-1",
      read_only: true,
      readonly_token: "REDACTED",
      process_id: 4242,
    });
    expect(invokeCalls).toEqual([{
      command: "stop_readonly_sidecar",
      args: { processId: 4242 },
    }]);
  });

  it("returns a managed Tauri readonly session without accepting executable paths from the WebView", async () => {
    const invokeCalls: Array<{ command: string; args?: Record<string, unknown> }> = [];
    const session = await createTauriReadonlyRunSession({
      outputDir: "D:\\runs\\v11",
      invoke: async (command, args) => {
        invokeCalls.push({ command, args });
        return {
          base_url: "http://127.0.0.1:49152",
          run_id: "run-1",
          read_only: true,
          readonly_token: "0123456789abcdef",
          process_id: 4242,
        } as never;
      },
      fetchJson: async () => ({
        schema_version: "v11.readonly_api.envelope.v1",
        status: "available",
        severity: "info",
        surface: "manifest",
        read_only: true,
        run_id: "run-1",
        artifact_kind: null,
        source: {
          backend: "json_artifact_repository",
          manifest_path: "run-manifest.json",
        },
        payload: {},
        unavailable: null,
      }),
    });

    await expect(session.transport.read("manifest")).resolves.toMatchObject({ run_id: "run-1" });
    await session.stop();

    expect(session.launch.process_id).toBe(4242);
    expect(invokeCalls).toEqual([
      {
        command: "start_readonly_sidecar",
        args: {
          outputDir: "D:\\runs\\v11",
        },
      },
      {
        command: "stop_readonly_sidecar",
        args: { processId: 4242 },
      },
    ]);
    expect(JSON.stringify(invokeCalls)).not.toContain("spiroctl");
  });

  it("fails closed for invalid Tauri readonly sidecar launches", () => {
    for (const launch of [
      null,
      { base_url: "http://0.0.0.0:49152", run_id: "run-1", read_only: true, readonly_token: "0123456789abcdef", process_id: 1 },
      { base_url: "http://127.0.0.1:49152", run_id: "", read_only: true, readonly_token: "0123456789abcdef", process_id: 1 },
      { base_url: "http://127.0.0.1:49152", run_id: "run-1", read_only: false, readonly_token: "0123456789abcdef", process_id: 1 },
      { base_url: "http://127.0.0.1:49152", run_id: "run-1", read_only: true, readonly_token: "short", process_id: 1 },
      { base_url: "http://127.0.0.1:49152", run_id: "run-1", read_only: true, readonly_token: "0123456789abcdef", process_id: 0 },
    ]) {
      expect(() => validateReadonlySidecarLaunch(launch)).toThrow("readonly sidecar launch");
    }
  });

  it("fails closed for malformed Go readonly envelopes and missing artifact kind", async () => {
    const notReadOnly: ReadonlyRunEnvelope = {
      schema_version: "v11.readonly_api.envelope.v1",
      status: "available",
      severity: "info",
      surface: "manifest",
      read_only: false,
      run_id: "run-1",
      artifact_kind: null,
      source: {
        backend: "json_artifact_repository",
        manifest_path: "run-manifest.json",
      },
      payload: {},
      unavailable: null,
    };
    const transport = createHttpReadonlyRunTransport({
      baseUrl: "http://127.0.0.1:47311",
      runId: "run-1",
      fetchJson: async () => notReadOnly,
    });

    await expect(transport.read("manifest")).rejects.toThrow("readonly envelope read_only");
    await expect(transport.read("artifact_by_kind")).rejects.toThrow("artifact_by_kind requires artifactKind");
  });

  it("fails closed when readonly envelopes return an unexpected run id", async () => {
    const transport = createHttpReadonlyRunTransport({
      baseUrl: "http://127.0.0.1:47311",
      runId: "run-1",
      fetchJson: async () => ({
        schema_version: "v11.readonly_api.envelope.v1",
        status: "available",
        severity: "info",
        surface: "manifest",
        read_only: true,
        run_id: "run-2",
        artifact_kind: null,
        source: {
          backend: "json_artifact_repository",
          manifest_path: "run-manifest.json",
        },
        payload: {},
        unavailable: null,
      }),
    });

    await expect(transport.read("manifest")).rejects.toThrow("readonly envelope run_id mismatch");
  });

  it("strictly validates Tauri sidecar loopback base URLs", () => {
    expect(isReadonlySidecarLoopbackBaseUrl("http://127.0.0.1:49152")).toBe(true);
    expect(isReadonlySidecarLoopbackBaseUrl("http://localhost:49152")).toBe(true);
    expect(isReadonlySidecarLoopbackBaseUrl("http://[::1]:49152")).toBe(true);
    expect(isReadonlySidecarLoopbackBaseUrl("http://user:pass@127.0.0.1:49152")).toBe(false);
    expect(isReadonlySidecarLoopbackBaseUrl("http://127.0.0.1")).toBe(false);
    expect(isReadonlySidecarLoopbackBaseUrl("https://127.0.0.1:49152")).toBe(false);
    expect(isReadonlySidecarLoopbackBaseUrl("http://0.0.0.0:49152")).toBe(false);
    expect(isReadonlySidecarLoopbackBaseUrl("not a url")).toBe(false);
  });

  it("keeps provider status and settings provider sets aligned", () => {
    const workspace = fixture as unknown as AtomReasonXWorkspaceState;
    const providerStatus = workspace.provider_status.providers.map(provider => provider.provider);
    const settings = workspace.settings.providers.map(provider => provider.provider);
    const sourceSettings = workspace.source_settings.sources.map(source => source.provider_id);

    expect(settings).toEqual(providerStatus);
    expect(settings).not.toContain("local_llm");
    expect(settings).not.toContain("materials_project");
    expect(sourceSettings).toContain("materials_project");
  });

  it("models sanitized command results with audit output artifacts", () => {
    const commandResult: AtomReasonXCommandResult = {
      schema_version: "v23.action_result.v1",
      request_id: "request-1",
      action_type: "config_write",
      status: "accepted",
      idempotency_key: "idem-1",
      actor_id: "operator-1",
      reason_code: "accepted",
      message: "accepted",
      output_artifacts: [{
        kind: "config_command_effect",
        schema_version: "v33.config_command.v1",
        action_type: "config_write",
        provider: "deepseek",
        provider_scope: "model",
        changed_fields: ["enabled"],
        validation_state: "validated",
        config_version: 1,
      }],
      audit: {
        idempotency_key: "idem-1",
        expected_source_version: "0",
        declared_effects: ["provider", "config"],
        changed_fields: ["enabled"],
        validation_state: "validated",
        config_version: 1,
        output_artifacts: [{
          kind: "config_command_effect",
          schema_version: "v33.config_command.v1",
          action_type: "config_write",
          provider: "deepseek",
          provider_scope: "model",
          changed_fields: ["enabled"],
          validation_state: "validated",
          config_version: 1,
        }],
      },
    };

    expect(commandResult.audit.declared_effects).toEqual(["provider", "config"]);
    expect(commandResult.audit.output_artifacts).toEqual(commandResult.output_artifacts);
  });

  it("models sanitized Materials Project source-provider probe command results", () => {
    const commandResult: AtomReasonXCommandResult = {
      schema_version: "v23.action_result.v1",
      request_id: "request-1",
      action_type: "test_connection",
      status: "accepted",
      idempotency_key: "idem-1",
      actor_id: "operator-1",
      reason_code: "accepted",
      message: "accepted",
      output_artifacts: [{
        kind: "config_command_effect",
        schema_version: "v33.config_command.v1",
        action_type: "test_connection",
        provider: "materials_project",
        provider_scope: "source",
        changed_fields: [],
        validation_state: "missing",
        validation_mode: "live_probe",
        config_version: 1,
        provider_probe: {
          schema_version: SOURCE_PROVIDER_CONNECTION_PROBE_SCHEMA_VERSION,
          provider: "materials_project",
          status: "missing_api_key",
          validation_state: "missing",
          read_only: true,
          live_enabled: true,
          requires_api_key: true,
          api_key_env: "MATERIALS_PROJECT_API_KEY",
          api_key_configured: false,
          formula: DEFAULT_MATERIALS_PROJECT_PROBE_FORMULA,
          normalized_field_count: 0,
          allowed_output_fields: ["resolution_status"],
          review_triggers: ["missing_api_key"],
          error_code: "missing_api_key",
          error_message: "Materials Project API key is required in MATERIALS_PROJECT_API_KEY",
        },
      }],
      audit: {
        idempotency_key: "idem-1",
        expected_source_version: "0",
        declared_effects: ["provider_connection_probe"],
        changed_fields: [],
        validation_state: "missing",
        config_version: 1,
        output_artifacts: [],
      },
    };
    commandResult.audit.output_artifacts = commandResult.output_artifacts;

    const blob = JSON.stringify(commandResult);
    expect(commandResult.output_artifacts[0].provider_probe?.schema_version).toBe(
      SOURCE_PROVIDER_CONNECTION_PROBE_SCHEMA_VERSION,
    );
    expect(commandResult.output_artifacts[0].provider_probe?.read_only).toBe(true);
    expect(commandResult.output_artifacts[0].provider_probe?.status).toBe("missing_api_key");
    expect(blob).not.toContain("mp-secret");
    expect(blob).not.toContain("api_key=");
  });

  it("projects accepted source key rotation into UI-local source settings without secrets", () => {
    const workspace = JSON.parse(JSON.stringify(fixture)) as AtomReasonXWorkspaceState;
    const before = JSON.stringify(workspace.source_settings);
    const result: AtomReasonXCommandResult = {
      schema_version: "v23.action_result.v1",
      request_id: "request-key-rotate",
      action_type: "key_rotate",
      status: "accepted",
      idempotency_key: "idem-key-rotate",
      actor_id: "operator-1",
      reason_code: "command_preconditions_passed",
      message: "accepted",
      output_artifacts: [{
        kind: "config_command_effect",
        schema_version: "v33.config_command.v1",
        action_type: "key_rotate",
        provider: "materials_project",
        provider_scope: "source",
        changed_fields: ["api_key"],
        validation_state: "validated",
        config_version: 8,
      }],
      audit: {
        idempotency_key: "idem-key-rotate",
        expected_source_version: "7",
        declared_effects: ["provider", "provider_scope", "api_key"],
        changed_fields: ["api_key"],
        validation_state: "validated",
        config_version: 8,
        output_artifacts: [],
      },
    };
    result.audit.output_artifacts = result.output_artifacts;

    const projected = projectSourceSettingsCommandResult(workspace, result);
    const source = projected.source_settings.sources.find(item => item.provider_id === "materials_project");

    expect(JSON.stringify(workspace.source_settings)).toBe(before);
    expect(projected).not.toBe(workspace);
    expect(projected.source_settings.config_version).toBe(8);
    expect(source?.has_api_key).toBe(true);
    expect(source?.key_fingerprint).toBeNull();
    expect(source?.validation_state).toBe("configured");
    expect(JSON.stringify(projected)).not.toContain("mp-test-key");
    expect(JSON.stringify(projected)).not.toContain("api_key=");
  });

  it("projects Materials Project probe validation without treating env keys as saved local keys", () => {
    const workspace = JSON.parse(JSON.stringify(fixture)) as AtomReasonXWorkspaceState;
    const sourceBefore = workspace.source_settings.sources.find(item => item.provider_id === "materials_project");
    const result: AtomReasonXCommandResult = {
      schema_version: "v23.action_result.v1",
      request_id: "request-probe",
      action_type: "test_connection",
      status: "accepted",
      idempotency_key: "idem-probe",
      actor_id: "operator-1",
      reason_code: "command_preconditions_passed",
      message: "accepted",
      output_artifacts: [{
        kind: "config_command_effect",
        schema_version: "v33.config_command.v1",
        action_type: "test_connection",
        provider: "materials_project",
        provider_scope: "source",
        changed_fields: [],
        validation_state: "validated",
        validation_mode: "live_probe",
        config_version: 9,
        provider_probe: {
          schema_version: SOURCE_PROVIDER_CONNECTION_PROBE_SCHEMA_VERSION,
          provider: "materials_project",
          status: "validated",
          validation_state: "validated",
          read_only: true,
          live_enabled: true,
          requires_api_key: true,
          api_key_env: "MATERIALS_PROJECT_API_KEY",
          api_key_configured: true,
          key_source: "environment",
          formula: DEFAULT_MATERIALS_PROJECT_PROBE_FORMULA,
          normalized_field_count: 3,
          allowed_output_fields: ["resolution_status"],
          review_triggers: [],
        },
      }],
      audit: {
        idempotency_key: "idem-probe",
        expected_source_version: "8",
        declared_effects: ["provider_connection_probe"],
        changed_fields: [],
        validation_state: "validated",
        config_version: 9,
        output_artifacts: [],
      },
    };
    result.audit.output_artifacts = result.output_artifacts;

    const projected = projectSourceSettingsCommandResult(workspace, result);
    const source = projected.source_settings.sources.find(item => item.provider_id === "materials_project");

    expect(sourceBefore?.has_api_key).toBe(false);
    expect(projected.source_settings.config_version).toBe(9);
    expect(source?.validation_state).toBe("validated");
    expect(source?.has_api_key).toBe(false);
    expect(source?.key_fingerprint).toBeNull();
  });

  it("does not project rejected queued or non-source command results", () => {
    const workspace = JSON.parse(JSON.stringify(fixture)) as AtomReasonXWorkspaceState;
    const rejected: AtomReasonXCommandResult = {
      schema_version: "v23.action_result.v1",
      request_id: "request-rejected",
      action_type: "key_rotate",
      status: "rejected",
      idempotency_key: "idem-rejected",
      actor_id: "operator-1",
      reason_code: "invalid_secret_value",
      message: "rejected",
      output_artifacts: [{
        kind: "config_command_effect",
        schema_version: "v33.config_command.v1",
        action_type: "key_rotate",
        provider: "materials_project",
        provider_scope: "source",
        changed_fields: ["api_key"],
        validation_state: "validated",
        config_version: 8,
      }],
      audit: {
        idempotency_key: "idem-rejected",
        expected_source_version: "7",
        declared_effects: [],
        changed_fields: [],
        validation_state: "rejected",
        config_version: 7,
        output_artifacts: [],
      },
    };
    rejected.audit.output_artifacts = rejected.output_artifacts;
    const queued = {
      ...rejected,
      request_id: "queued-local",
      status: "queued",
      reason_code: "transport_pending",
    };
    const modelEffect = {
      ...rejected,
      status: "accepted",
      output_artifacts: [{
        ...rejected.output_artifacts[0],
        provider: "deepseek",
        provider_scope: "model" as const,
      }],
    };

    expect(projectSourceSettingsCommandResult(workspace, rejected)).toBe(workspace);
    expect(projectSourceSettingsCommandResult(workspace, queued)).toBe(workspace);
    expect(projectSourceSettingsCommandResult(workspace, modelEffect)).toBe(workspace);
  });

  it("ignores stale accepted source command results that return out of order", () => {
    const workspace = JSON.parse(JSON.stringify(fixture)) as AtomReasonXWorkspaceState;
    const mp = workspace.source_settings.sources.find(item => item.provider_id === "materials_project");
    expect(mp).toBeDefined();
    workspace.source_settings.config_version = 9;
    mp!.has_api_key = false;
    mp!.validation_state = "missing";
    const staleProbe: AtomReasonXCommandResult = {
      schema_version: "v23.action_result.v1",
      request_id: "request-stale-probe",
      action_type: "test_connection",
      status: "accepted",
      idempotency_key: "idem-stale-probe",
      actor_id: "operator-1",
      reason_code: "command_preconditions_passed",
      message: "accepted",
      output_artifacts: [{
        kind: "config_command_effect",
        schema_version: "v33.config_command.v1",
        action_type: "test_connection",
        provider: "materials_project",
        provider_scope: "source",
        changed_fields: [],
        validation_state: "validated",
        validation_mode: "live_probe",
        config_version: 8,
        provider_probe: {
          schema_version: SOURCE_PROVIDER_CONNECTION_PROBE_SCHEMA_VERSION,
          provider: "materials_project",
          status: "validated",
          validation_state: "validated",
          read_only: true,
          live_enabled: true,
          requires_api_key: true,
          api_key_env: "MATERIALS_PROJECT_API_KEY",
          api_key_configured: true,
          key_source: "operator_secret",
          formula: DEFAULT_MATERIALS_PROJECT_PROBE_FORMULA,
          normalized_field_count: 3,
          allowed_output_fields: ["resolution_status"],
          review_triggers: [],
        },
      }],
      audit: {
        idempotency_key: "idem-stale-probe",
        expected_source_version: "8",
        declared_effects: ["provider_connection_probe"],
        changed_fields: [],
        validation_state: "validated",
        config_version: 8,
        output_artifacts: [],
      },
    };
    staleProbe.audit.output_artifacts = staleProbe.output_artifacts;

    const projected = projectSourceSettingsCommandResult(workspace, staleProbe);

    expect(projected).toBe(workspace);
    expect(mp!.has_api_key).toBe(false);
    expect(mp!.validation_state).toBe("missing");
    expect(workspace.source_settings.config_version).toBe(9);
  });

  it("exposes V33C HTL workbench source coverage and command actions", () => {
    const workspace = fixture as unknown as AtomReasonXWorkspaceState;
    const providers = workspace.source_coverage.sources.map(source => source.provider_id);
    const commands = workspace.command_actions.map(action => action.action_type);

    expect(workspace.source_coverage.lane).toBe("htl_only");
    expect(workspace.operator_tasks).toEqual([]);
    expect(providers).toContain("nomad_perla_psc");
    expect(providers).toContain("local_paper_vault");
    expect(commands).toContain("start_nomad_sync");
    expect(commands).toContain("import_doi_list");
    expect(workspace.workflow.gates).toContain("EvidenceQualityPolicy");
  });

  it("joins source profiles coverage and settings without mutating read models", () => {
    const workspace = fixture as unknown as AtomReasonXWorkspaceState;
    const before = JSON.stringify({
      source_coverage: workspace.source_coverage,
      source_profiles: workspace.source_profiles,
      source_settings: workspace.source_settings,
    });

    const rows = buildDataSourceDisplayRows(
      workspace.source_coverage,
      workspace.source_profiles,
      workspace.source_settings,
    );

    expect(JSON.stringify({
      source_coverage: workspace.source_coverage,
      source_profiles: workspace.source_profiles,
      source_settings: workspace.source_settings,
    })).toBe(before);

    const hopv15 = rows.find(row => row.provider_id === "hopv15");
    const localVault = rows.find(row => row.provider_id === "local_paper_vault");
    const nomad = rows.find(row => row.provider_id === "nomad");
    const customDft = rows.find(row => row.provider_id === "custom_htl_dft");
    const materialsProject = rows.find(row => row.provider_id === "materials_project");
    const pubchemqc = rows.find(row => row.provider_id === "pubchemqc");

    expect(rows.map(row => row.provider_id)).toContain("nomad");
    expect(rows.map(row => row.provider_id)).toContain("custom_htl_dft");
    expect(hopv15?.dataset_version).toBe("figshare-v4-fixture");
    expect(hopv15?.citation).toContain("Scientific Data");
    expect(localVault?.display_name).toBe("Local Paper Vault");
    expect(nomad?.provider_status).toBe("experimental / out_of_current_slice");
    expect(customDft?.key_state).toBe("none/configured");
    expect(materialsProject?.display_name).toBe("Materials Project");
    expect(materialsProject?.key_state).toBe("required/missing");
    expect(pubchemqc?.quarantine_state).toBe("provider_quarantined");
    expect(pubchemqc?.blocking_review_count).toBe(1);
  });

  it("keeps HOPV15 and OPV-DB source coverage fields aligned with P4 snapshot imports", () => {
    const workspace = fixture as unknown as AtomReasonXWorkspaceState;
    const hopv15 = workspace.source_coverage.sources.find(source => source.provider_id === "hopv15");
    const opvDb = workspace.source_coverage.sources.find(source => source.provider_id === "opv_db");
    const profiles = workspace.source_profiles.profiles;
    const hopv15Profile = profiles.find(profile => profile.provider_id === "hopv15");
    const opvDbProfile = profiles.find(profile => profile.provider_id === "opv_db");

    expect(hopv15?.expected_fields).toEqual(expect.arrayContaining([
      "inchi",
      "conformer_id",
      "voc_v",
      "jsc_ma_cm2",
      "method",
      "basis_set",
    ]));
    expect(opvDb?.expected_fields).toEqual(expect.arrayContaining([
      "donor_inchi_key",
      "acceptor_inchi_key",
      "benchmark_split",
      "quality_annotation",
    ]));
    expect(hopv15Profile?.go_migration_state).toBe("go_shadow_ready");
    expect(opvDbProfile?.go_migration_state).toBe("go_shadow_ready");
    expect(hopv15Profile?.python_bridge_required).toBe(true);
    expect(opvDbProfile?.python_bridge_required).toBe(false);
  });

  it("keeps Materials Project source coverage aligned with P5 Go shadow summary fields", () => {
    const workspace = fixture as unknown as AtomReasonXWorkspaceState;
    const materialsProject = workspace.source_coverage.sources.find(source => source.provider_id === "materials_project");
    const materialsProjectProfile = workspace.source_profiles.profiles.find(profile => profile.provider_id === "materials_project");
    const materialsProjectSettings = workspace.source_settings.sources.find(source => source.provider_id === "materials_project");

    expect(materialsProject?.expected_fields).toEqual(expect.arrayContaining([
      "resolution_status",
      "ambiguity_flag",
      "ambiguous_material_ids",
      "formation_energy_ev_per_atom",
      "energy_above_hull",
      "density",
      "space_group",
      "structure_ref",
      "database_version",
      "origins",
      "thermo_type",
      "deprecated",
      "license",
      "computed",
    ]));
    expect(materialsProjectProfile?.go_migration_state).toBe("go_shadow_ready");
    expect(materialsProjectProfile?.python_bridge_required).toBe(false);
    expect(materialsProjectSettings?.api_key_env).toBe("MATERIALS_PROJECT_API_KEY");
    expect(materialsProjectSettings?.has_api_key).toBe(false);
    expect(materialsProjectSettings?.key_fingerprint).toBeNull();
  });

  it("keeps NOMAD PERLA PSC source coverage aligned with P6 Go shadow query/archive parity", () => {
    const workspace = fixture as unknown as AtomReasonXWorkspaceState;
    const nomad = workspace.source_coverage.sources.find(source => source.provider_id === "nomad_perla_psc");
    const nomadProfile = workspace.source_profiles.profiles.find(profile => profile.provider_id === "nomad_perla_psc");

    expect(nomad?.expected_fields).toEqual(expect.arrayContaining([
      "upload_id",
      "device_architecture",
      "chemical_formula",
      "query_hash",
      "archive_required_tree_hash",
      "review_required",
      "review_reasons",
      "match_type",
      "device_count",
      "devices",
    ]));
    expect(nomad?.review_blockers).toEqual(expect.arrayContaining([
      "missing_source_doi",
      "missing_device_stack",
      "missing_htl_stack",
      "missing_core_metrics",
      "archive_rate_limited",
      "archive_schema_unrecognized",
    ]));
    expect(nomadProfile?.go_migration_state).toBe("go_shadow_ready");
    expect(nomadProfile?.python_bridge_required).toBe(true);
    expect(nomadProfile?.operational_status).toBe("experimental");
  });

  it("gates workflow commands that require form input", async () => {
    const workspace = fixture as unknown as AtomReasonXWorkspaceState;
    const action = workspace.command_actions.find(item => item.action_type === "import_materials_cloud_archive_record");

    expect(action).toBeDefined();
    const payload = buildWorkflowCommandPayload(action!);

    expect(payload.provider).toBe("materials_cloud");
    expect(payload.provider_scope).toBe("source");
    expect(payload.declared_effects).toEqual(["source_import_tasks"]);
    expect(canSubmitWorkflowCommandAction(action!)).toBe(false);
    await expect(submitWorkflowCommandAction({
      submitAction: async () => {
        throw new Error("unexpected submit");
      },
    }, action!)).rejects.toThrow("workflow command requires input");
  });

  it("exposes data-source settings separately from model settings", () => {
    const workspace = fixture as unknown as AtomReasonXWorkspaceState;
    const sourceSettings = workspace.source_settings.sources;
    const mp = sourceSettings.find(source => source.provider_id === "materials_project");
    const profileIds = new Set(workspace.source_profiles.profiles.map(profile => profile.provider_id));
    const sourceSettingsWithoutProfiles = sourceSettings.filter(source => !profileIds.has(source.provider_id));
    const coverageWithoutProfiles = workspace.source_coverage.sources.filter(source => !profileIds.has(source.provider_id));

    expect(workspace.source_settings.schema_version).toBe("v35.sanitized_source_config_status.v1");
    expect(workspace.source_profiles.schema_version).toBe("v35.atomreasonx_source_profiles.v1");
    expect(sourceSettingsWithoutProfiles).toEqual([]);
    expect(coverageWithoutProfiles).toEqual([]);
    expect(profileIds.has("materials_project")).toBe(true);
    expect(profileIds.has("local_paper_vault")).toBe(true);
    expect(profileIds.has("future_model_assisted_claim_extraction")).toBe(true);
    expect(mp?.provider_scope).toBe("source");
    expect(mp?.key_requirement).toBe("required");
    expect(mp?.api_key_env).toBe("MATERIALS_PROJECT_API_KEY");
    expect(mp?.key_fingerprint).toBeNull();
  });

  it("builds source-scoped Materials Project command requests with V23 envelope", () => {
    const request = buildWorkbenchCommandRequest(
      "key_rotate",
      {
        provider: "materials_project",
        provider_scope: "source",
        api_key: "mp-test-key",
      },
      {
        actorId: "operator-1",
        expectedTargetVersion: "7",
        idempotencyKey: "mp-key-rotate-1",
      },
    );

    expect(request.schema_version).toBe("v23.action_request.v1");
    expect(request.actor.role).toBe("operator");
    expect(request.idempotency_key).toBe("mp-key-rotate-1");
    expect(request.preconditions.expected_target_version).toBe("7");
    expect(request.payload.provider_scope).toBe("source");
  });

  it("submits workflow and source settings commands through the workbench dispatcher", async () => {
    const workspace = fixture as unknown as AtomReasonXWorkspaceState;
    const submitted: WorkbenchCommandRequest[] = [];
    let commandIndex = 0;
    const dispatcher = createWorkbenchCommandDispatcher({
      submit: async (request) => {
        submitted.push(request);
        return { status: "queued" };
      },
    }, () => ({
      actorId: "operator-1",
      expectedTargetVersion: "7",
      idempotencyKey: `atomx-dispatch-test-${++commandIndex}`,
    }));
    const workflowAction = workspace.command_actions.find(item => item.action_type === "start_nomad_sync");
    const source = workspace.source_settings.sources.find(item => item.provider_id === "materials_project");

    expect(workflowAction).toBeDefined();
    expect(source).toBeDefined();
    expect(canSubmitWorkflowCommandAction(workflowAction!)).toBe(true);
    await submitWorkflowCommandAction(dispatcher, workflowAction!);
    await submitSourceSettingsCommand(dispatcher, "key_rotate", source!, { api_key: "mp-test-key" });
    await submitSourceProviderTestConnectionCommand(dispatcher, source!);

    expect(submitted).toHaveLength(3);
    expect(submitted[0].schema_version).toBe("v23.action_request.v1");
    expect(submitted[0].action_type).toBe("start_nomad_sync");
    expect(submitted[0].payload.declared_effects).toEqual(["provider_sync_jobs"]);
    expect(submitted[0].preconditions.expected_target_version).toBe("7");
    expect(submitted[1].action_type).toBe("key_rotate");
    expect(submitted[1].idempotency_key).toBe("atomx-dispatch-test-2");
    expect(submitted[1].payload.provider).toBe("materials_project");
    expect(submitted[1].payload.provider_scope).toBe("source");
    expect(submitted[2].action_type).toBe("test_connection");
    expect(submitted[2].idempotency_key).toBe("atomx-dispatch-test-3");
    expect(submitted[2].payload.provider).toBe("materials_project");
    expect(submitted[2].payload.provider_scope).toBe("source");
    expect(submitted[2].payload.probe_contract).toBe(SOURCE_PROVIDER_CONNECTION_PROBE_SCHEMA_VERSION);
    expect(submitted[2].payload.formula).toBe(DEFAULT_MATERIALS_PROJECT_PROBE_FORMULA);
    expect(JSON.stringify(submitted[2].payload)).not.toContain("api_key");
  });

  it("routes Materials Project source-provider probes through the Tauri config command bridge", async () => {
    const source = (fixture as unknown as AtomReasonXWorkspaceState).source_settings.sources
      .find(item => item.provider_id === "materials_project");
    const calls: Array<{ command: string; args?: Record<string, unknown> }> = [];
    const adapter = createTauriConfigCommandAdapter({
      invoke: async <T,>(command: string, args?: Record<string, unknown>): Promise<T> => {
        calls.push({ command, args });
        const result = {
          schema_version: "v23.action_result.v1",
          request_id: "request-1",
          action_type: "test_connection",
          status: "accepted",
          idempotency_key: "idem-1",
          actor_id: "operator-1",
          reason_code: "accepted",
          message: "accepted",
          output_artifacts: [],
          audit: {
            idempotency_key: "idem-1",
            expected_source_version: "0",
            declared_effects: [],
            changed_fields: [],
            validation_state: "missing",
            config_version: 0,
            output_artifacts: [],
          },
        } satisfies AtomReasonXCommandResult;
        return result as T;
      },
    });
    const dispatcher = createWorkbenchCommandDispatcher(adapter, {
      idempotencyKey: "idem-1",
      expectedTargetVersion: "0",
    });

    expect(source).toBeDefined();
    const result = await submitSourceProviderTestConnectionCommand(dispatcher, source!);

    expect((result as AtomReasonXCommandResult).status).toBe("accepted");
    expect(calls).toHaveLength(1);
    expect(calls[0].command).toBe("submit_config_command");
    expect(calls[0].args?.request).toMatchObject({
      schema_version: "v23.action_request.v1",
      action_type: "test_connection",
      payload: {
        provider: "materials_project",
        provider_scope: "source",
        probe_contract: SOURCE_PROVIDER_CONNECTION_PROBE_SCHEMA_VERSION,
      },
    });
    expect(JSON.stringify(calls[0].args)).not.toContain("api_key");
  });

  it("queues known workflow commands as explicit local operator tasks without invoking Tauri", async () => {
    const workflowAction = (fixture as unknown as AtomReasonXWorkspaceState).command_actions
      .find(item => item.action_type === "start_nomad_sync");
    let invokeCount = 0;
    const adapter = createRuntimeWorkbenchCommandAdapter({
      invoke: async <T,>(): Promise<T> => {
        invokeCount += 1;
        throw new Error("workflow command should not reach Tauri config bridge");
      },
    });
    const dispatcher = createWorkbenchCommandDispatcher(adapter, {
      idempotencyKey: "workflow-1",
      expectedTargetVersion: "0",
    });

    expect(workflowAction).toBeDefined();
    const result = await submitWorkflowCommandAction(dispatcher, workflowAction!);

    expect(invokeCount).toBe(0);
    expect(result).toMatchObject({
      schema_version: "v23.action_result.v1",
      action_type: "start_nomad_sync",
      status: "accepted",
      reason_code: "operator_task_queued",
      output_artifacts: [{
        kind: "workflow_command_task",
        schema_version: "v35.operator_task.v1",
        action_type: "start_nomad_sync",
        provider: "nomad_perla_psc",
        provider_scope: "source",
        status: "queued",
        queue_scope: "operator_local",
        declared_effects: ["provider_sync_jobs"],
        writes_authorized: false,
        execution_started: false,
      }],
    });
    expect(JSON.stringify(result)).not.toContain("api_key");
    expect(JSON.stringify(result)).not.toContain("provider_cache_records");
  });

  it("builds fixed NOMAD workflow task execution requests only from admitted operator tasks", async () => {
    const workflowAction = (fixture as unknown as AtomReasonXWorkspaceState).command_actions
      .find(item => item.action_type === "start_nomad_sync");
    const adapter = createRuntimeWorkbenchCommandAdapter();
    const dispatcher = createWorkbenchCommandDispatcher(adapter, {
      idempotencyKey: "nomad-sync-execute-1",
      expectedTargetVersion: "0",
    });

    expect(workflowAction).toBeDefined();
    const result = await submitWorkflowCommandAction(dispatcher, workflowAction!) as AtomReasonXCommandResult;
    const workspace = projectWorkflowCommandTaskResult(
      JSON.parse(JSON.stringify(fixture)) as AtomReasonXWorkspaceState,
      result,
    );
    const task = workspace.operator_tasks[0];
    const admittedTask = {
      ...task,
      admission_status: "admitted" as const,
      admission_hash: "a".repeat(64),
      ledger_path: DEFAULT_OPERATOR_TASK_LEDGER_PATH,
      admission_source: "operator_task_ledger" as const,
    };
    const request = buildWorkflowTaskExecutionRequest(admittedTask);

    expect(canExecuteWorkflowTask(task)).toBe(false);
    expect(() => buildWorkflowTaskExecutionRequest(task)).toThrow("workflow task is not executable");
    expect(canExecuteWorkflowTask(admittedTask)).toBe(true);
    expect(request).toEqual({
      schema_version: "v35.operator_task_execution_request.v1",
      task_id: task.task_id,
      ledger_path: DEFAULT_OPERATOR_TASK_LEDGER_PATH,
      target_data_library_path: `data/lib/nomad_perla_psc/snapshots/run-${task.task_id}`,
      authorize_live_provider_calls: true,
      execution_contract: OPERATOR_TASK_EXECUTION_SCHEMA_VERSION,
    });
    expect(JSON.stringify(request)).not.toContain("api_key");
    expect(JSON.stringify(request)).not.toContain("readonly_token");
    expect(JSON.stringify(request)).not.toContain("SPIROCTL_PATH");
    expect(() => buildWorkflowTaskExecutionRequest({
      ...admittedTask,
      task_id: "task-start_nomad_sync-api_key",
    })).toThrow("workflow task is not executable");
    expect(canExecuteWorkflowTask({
      ...admittedTask,
      provider: "materials_project",
    })).toBe(false);
    expect(canExecuteWorkflowTask({
      ...admittedTask,
      action_type: "import_hopv15_snapshot",
      provider: "hopv15",
      declared_effects: ["source_import_tasks"],
    })).toBe(false);
  });

  it("routes reviewed NOMAD workflow task execution through a fixed Tauri command", async () => {
    const workflowAction = (fixture as unknown as AtomReasonXWorkspaceState).command_actions
      .find(item => item.action_type === "start_nomad_sync");
    const adapter = createRuntimeWorkbenchCommandAdapter();
    const dispatcher = createWorkbenchCommandDispatcher(adapter, {
      idempotencyKey: "nomad-sync-execute-2",
      expectedTargetVersion: "0",
    });
    const result = await submitWorkflowCommandAction(dispatcher, workflowAction!) as AtomReasonXCommandResult;
    const workspace = projectWorkflowCommandTaskResult(
      JSON.parse(JSON.stringify(fixture)) as AtomReasonXWorkspaceState,
      result,
    );
    const task = {
      ...workspace.operator_tasks[0],
      admission_status: "admitted" as const,
      admission_hash: "a".repeat(64),
      ledger_path: DEFAULT_OPERATOR_TASK_LEDGER_PATH,
      admission_source: "operator_task_ledger" as const,
    };
    const calls: Array<{ command: string; args?: Record<string, unknown> }> = [];
    const executor = createTauriWorkflowTaskExecutor({
      invoke: async <T,>(command: string, args?: Record<string, unknown>): Promise<T> => {
        calls.push({ command, args });
        const request = args?.request as ReturnType<typeof buildWorkflowTaskExecutionRequest>;
        const report = {
          schema_version: OPERATOR_TASK_EXECUTION_SCHEMA_VERSION,
          task_id: request.task_id,
          action_type: "start_nomad_sync",
          provider: "nomad_perla_psc",
          admission_hash: "a".repeat(64),
          execution_status: "source_snapshot_written",
          write_authorization_scope: "source_snapshot_only",
          live_calls_authorized: true,
          provider_cache_written: false,
          local_backend_written: false,
          scoring_written: false,
          experiment_written: false,
          started_at: "2026-07-24T00:00:00Z",
          target_data_library_path: request.target_data_library_path,
          source_manifest_path: `${request.target_data_library_path}/source-manifest.json`,
          normalized_record_count: 1,
          provider_response_hash: "b".repeat(64),
          raw_search_hash: "c".repeat(64),
          raw_archive_hash: "d".repeat(64),
          archive_status: "available",
          review_required: false,
          review_reasons: [],
        } satisfies OperatorTaskExecutionReport;
        return report as T;
      },
    });

    const execution = await executor.execute(task);

    expect(calls).toHaveLength(1);
    expect(calls[0].command).toBe("execute_workflow_task");
    expect(calls[0].args?.request).toMatchObject({
      schema_version: "v35.operator_task_execution_request.v1",
      task_id: task.task_id,
      ledger_path: DEFAULT_OPERATOR_TASK_LEDGER_PATH,
      authorize_live_provider_calls: true,
      execution_contract: OPERATOR_TASK_EXECUTION_SCHEMA_VERSION,
    });
    expect(execution).toMatchObject({
      schema_version: OPERATOR_TASK_EXECUTION_SCHEMA_VERSION,
      execution_status: "source_snapshot_written",
      write_authorization_scope: "source_snapshot_only",
      provider_cache_written: false,
      local_backend_written: false,
      scoring_written: false,
      experiment_written: false,
    });
    expect(JSON.stringify(calls[0].args)).not.toContain("api_key");
    expect(JSON.stringify(calls[0].args)).not.toContain("readonly_token");
    expect(JSON.stringify(calls[0].args)).not.toContain("spiroctl.exe");
  });

  it("projects NOMAD execution reports back into operator task summaries without writer state", async () => {
    const workflowAction = (fixture as unknown as AtomReasonXWorkspaceState).command_actions
      .find(item => item.action_type === "start_nomad_sync");
    const adapter = createRuntimeWorkbenchCommandAdapter();
    const dispatcher = createWorkbenchCommandDispatcher(adapter, {
      idempotencyKey: "nomad-sync-execute-report",
      expectedTargetVersion: "0",
    });
    const result = await submitWorkflowCommandAction(dispatcher, workflowAction!) as AtomReasonXCommandResult;
    const workspace = projectWorkflowCommandTaskResult(
      JSON.parse(JSON.stringify(fixture)) as AtomReasonXWorkspaceState,
      result,
    );
    const admittedTask = {
      ...workspace.operator_tasks[0],
      admission_status: "admitted" as const,
      admission_hash: "a".repeat(64),
      ledger_path: DEFAULT_OPERATOR_TASK_LEDGER_PATH,
      admission_source: "operator_task_ledger" as const,
    };
    const workspaceWithAdmittedTask = {
      ...workspace,
      operator_tasks: [admittedTask],
    } satisfies AtomReasonXWorkspaceState;
    const report = {
      schema_version: OPERATOR_TASK_EXECUTION_SCHEMA_VERSION,
      task_id: admittedTask.task_id,
      action_type: "start_nomad_sync",
      provider: "nomad_perla_psc",
      admission_hash: admittedTask.admission_hash,
      execution_status: "source_snapshot_written",
      write_authorization_scope: "source_snapshot_only",
      live_calls_authorized: true,
      provider_cache_written: false,
      local_backend_written: false,
      scoring_written: false,
      experiment_written: false,
      started_at: "2026-07-25T00:00:00Z",
      target_data_library_path: `data/lib/nomad_perla_psc/snapshots/run-${admittedTask.task_id}`,
      source_manifest_path: `data/lib/nomad_perla_psc/snapshots/run-${admittedTask.task_id}/source-manifest.json`,
      normalized_record_count: 2,
      provider_response_hash: "b".repeat(64),
      raw_search_hash: "c".repeat(64),
      raw_archive_hash: "d".repeat(64),
      archive_status: "rate_limited",
      review_required: true,
      review_reasons: ["archive_rate_limited"],
    } satisfies OperatorTaskExecutionReport;

    const projected = projectWorkflowTaskExecutionReport(workspaceWithAdmittedTask, report);
    const duplicate = projectWorkflowTaskExecutionReport(projected, report);
    const unrelated = projectWorkflowTaskExecutionReport(workspaceWithAdmittedTask, {
      ...report,
      task_id: "task-start_nomad_sync-unknown",
    });
    const hostileExtras = [
      { ...report, provider_cache_path: "data/provider_cache/index.json" },
      { ...report, spiroctl_path: "C:\\tools\\spiroctl.exe" },
      { ...report, api_key: "mp-secret" },
      { ...report, writer_metadata: { local_backend_written: true } },
    ] as unknown as OperatorTaskExecutionReport[];

    expect(projected).not.toBe(workspaceWithAdmittedTask);
    expect(projected.operator_tasks[0].execution_report).toMatchObject({
      schema_version: OPERATOR_TASK_EXECUTION_SCHEMA_VERSION,
      source_manifest_path: report.source_manifest_path,
      normalized_record_count: 2,
      archive_status: "rate_limited",
      review_required: true,
      review_reasons: ["archive_rate_limited"],
      provider_cache_written: false,
      local_backend_written: false,
      scoring_written: false,
      experiment_written: false,
    });
    expect(canExecuteWorkflowTask(admittedTask)).toBe(true);
    expect(canExecuteWorkflowTask(projected.operator_tasks[0])).toBe(false);
    expect(duplicate).toBe(projected);
    expect(unrelated).toBe(workspaceWithAdmittedTask);
    for (const hostileReport of hostileExtras) {
      expect(projectWorkflowTaskExecutionReport(workspaceWithAdmittedTask, hostileReport)).toBe(workspaceWithAdmittedTask);
    }
    expect(workspaceWithAdmittedTask.operator_tasks[0].execution_report).toBeUndefined();
    expect(projected.knowledge_library).toEqual(workspaceWithAdmittedTask.knowledge_library);
    expect(JSON.stringify(projected.operator_tasks)).not.toContain("api_key");
    expect(JSON.stringify(projected.operator_tasks)).not.toContain("readonly_token");
    expect(JSON.stringify(projected.operator_tasks)).not.toContain("spiroctl.exe");
  });

  it("restores persisted NOMAD execution reports during runtime workspace load", async () => {
    const workspace = JSON.parse(JSON.stringify(fixture)) as AtomReasonXWorkspaceState;
    const workflowAction = workspace.command_actions.find(item => item.action_type === "start_nomad_sync");
    const adapter = createRuntimeWorkbenchCommandAdapter();
    const dispatcher = createWorkbenchCommandDispatcher(adapter, {
      idempotencyKey: "nomad-sync-restore-report",
      expectedTargetVersion: "0",
    });
    const result = await submitWorkflowCommandAction(dispatcher, workflowAction!) as AtomReasonXCommandResult;
    const queued = projectWorkflowCommandTaskResult(workspace, result).operator_tasks[0];
    const restoredTask = {
      ...queued,
      admission_status: "admitted" as const,
      admission_hash: "a".repeat(64),
      ledger_path: DEFAULT_OPERATOR_TASK_LEDGER_PATH,
      admission_source: "operator_task_ledger" as const,
      execution_report: executionReportForTask({
        task_id: queued.task_id,
        admission_hash: "a".repeat(64),
      }),
    };
    const restoreReport = restoreReportForTasks([restoredTask]);
    const runtime = createRuntimeWorkbenchReadAdapter({
      baseWorkspace: workspace,
      workflowTaskRestoreReader: {
        async restore() {
          return validateOperatorTaskRestoreReport(restoreReport);
        },
      },
    });
    const restoreCalls: Array<{ command: string; args?: Record<string, unknown> }> = [];
    const tauriRestorer = createTauriWorkflowTaskRestoreReader({
      invoke: async <T,>(command: string, args?: Record<string, unknown>): Promise<T> => {
        restoreCalls.push({ command, args });
        return restoreReport as T;
      },
    });

    const loaded = await runtime.adapter.loadWorkspace();
    const nativeRestore = await tauriRestorer.restore();
    const duplicateProjection = projectWorkflowTaskRestoreReport({
      ...loaded,
      operator_tasks: [queued, ...loaded.operator_tasks],
    }, validateOperatorTaskRestoreReport(restoreReport));

    expect(runtime.readOnly).toBe(false);
    expect(loaded.operator_tasks).toHaveLength(1);
    expect(loaded.operator_tasks[0].execution_report).toMatchObject({
      schema_version: OPERATOR_TASK_EXECUTION_SCHEMA_VERSION,
      source_manifest_path: restoredTask.execution_report.source_manifest_path,
      provider_cache_written: false,
      local_backend_written: false,
      scoring_written: false,
      experiment_written: false,
    });
    expect(canExecuteWorkflowTask(loaded.operator_tasks[0])).toBe(false);
    expect(duplicateProjection.operator_tasks).toHaveLength(1);
    expect(nativeRestore.restored_tasks).toHaveLength(1);
    expect(restoreCalls).toEqual([{ command: "restore_workflow_tasks", args: undefined }]);
    expect(JSON.stringify(restoreCalls)).not.toContain("ledger");
    expect(JSON.stringify(restoreCalls)).not.toContain("spiroctl");
    expect(loaded.knowledge_library).toEqual(workspace.knowledge_library);
    expect(JSON.stringify(loaded.operator_tasks)).not.toContain("api_key");
    expect(JSON.stringify(loaded.operator_tasks)).not.toContain("readonly_token");
    expect(JSON.stringify(loaded.operator_tasks)).not.toContain("spiroctl.exe");
  });

  it("rejects execution reports that drift from the schema contract", () => {
    const request = {
      schema_version: "v35.operator_task_execution_request.v1" as const,
      task_id: "task-start_nomad_sync-ab12cd",
      ledger_path: DEFAULT_OPERATOR_TASK_LEDGER_PATH,
      target_data_library_path: "data/lib/nomad_perla_psc/snapshots/run-task-start_nomad_sync-ab12cd",
      authorize_live_provider_calls: true as const,
      execution_contract: OPERATOR_TASK_EXECUTION_SCHEMA_VERSION,
    };
    const report = {
      schema_version: OPERATOR_TASK_EXECUTION_SCHEMA_VERSION,
      task_id: request.task_id,
      action_type: "start_nomad_sync",
      provider: "nomad_perla_psc",
      admission_hash: "a".repeat(64),
      execution_status: "source_snapshot_written",
      write_authorization_scope: "source_snapshot_only",
      live_calls_authorized: true,
      provider_cache_written: false,
      local_backend_written: false,
      scoring_written: false,
      experiment_written: false,
      started_at: "2026-07-24T00:00:00Z",
      target_data_library_path: request.target_data_library_path,
      source_manifest_path: `${request.target_data_library_path}/source-manifest.json`,
      normalized_record_count: 1,
      provider_response_hash: "b".repeat(64),
      raw_search_hash: "c".repeat(64),
      raw_archive_hash: "d".repeat(64),
      archive_status: "available",
      review_required: false,
      review_reasons: [],
    };

    expect(validateOperatorTaskExecutionReport(report, request)).toEqual(report);
    for (const mutated of [
      { ...report, extra: true },
      { ...report, archive_status: "accepted" },
      { ...report, normalized_record_count: -1 },
      { ...report, review_reasons: [123] },
      { ...report, source_manifest_path: "data/lib/nomad_perla_psc/snapshots/run-task-start_nomad_sync-ab12cd/../source-manifest.json" },
    ]) {
      expect(() => validateOperatorTaskExecutionReport(mutated, request)).toThrow();
    }
  });

  it("rejects restore reports that drift from the readonly restore contract", () => {
    const task = {
      schema_version: "v35.operator_task.v1" as const,
      task_id: "task-start_nomad_sync-ab12cd",
      action_type: "start_nomad_sync",
      provider: "nomad_perla_psc",
      provider_scope: "source" as const,
      status: "queued" as const,
      queue_scope: "operator_local" as const,
      declared_effects: ["provider_sync_jobs"],
      writes_authorized: false as const,
      execution_started: false as const,
      created_at: null,
      config: {
        transport: "operator_task_queue",
        runtime_writes: false,
        config_source: "workflow_command_allowlist",
      },
      admission_status: "admitted" as const,
      admission_hash: "a".repeat(64),
      ledger_path: DEFAULT_OPERATOR_TASK_LEDGER_PATH,
      admission_source: "operator_task_ledger" as const,
      execution_report: executionReportForTask({
        task_id: "task-start_nomad_sync-ab12cd",
        admission_hash: "a".repeat(64),
      }),
    };
    const report = restoreReportForTasks([task]);

    expect(validateOperatorTaskRestoreReport(report)).toMatchObject(report);
    for (const mutated of [
      { ...report, extra: true },
      { ...report, provider_cache_written: true },
      { ...report, restored_tasks: [{ ...task, api_key: "mp-secret" }] },
      {
        ...report,
        restored_tasks: [{
          ...task,
          execution_report: { ...task.execution_report, admission_hash: "e".repeat(64) },
        }],
      },
    ]) {
      expect(() => validateOperatorTaskRestoreReport(mutated)).toThrow();
    }
  });

  it("queues every fixture workflow command action through the explicit operator task path", async () => {
    const workspace = fixture as unknown as AtomReasonXWorkspaceState;
    const adapter = createRuntimeWorkbenchCommandAdapter({
      invoke: async <T,>(): Promise<T> => {
        throw new Error("fixture workflow command should not reach Tauri config bridge");
      },
    });

    for (const action of workspace.command_actions) {
      const result = await adapter.submit(buildWorkbenchCommandRequest(
        action.action_type,
        buildWorkflowCommandPayload(action),
        { idempotencyKey: `workflow-${action.action_type}`, expectedTargetVersion: "0" },
      )) as AtomReasonXCommandResult;

      expect(result.status, action.action_type).toBe("accepted");
      expect(result.reason_code, action.action_type).toBe("operator_task_queued");
      expect(result.output_artifacts[0], action.action_type).toMatchObject({
        kind: "workflow_command_task",
        action_type: action.action_type,
        provider: action.provider ?? (action.action_type.endsWith("_nomad_sync") ? "nomad_perla_psc" : null),
        provider_scope: action.provider_scope ?? "source",
        declared_effects: action.declared_effects,
        writes_authorized: false,
        execution_started: false,
      });
    }

    const tamperedResult = await adapter.submit(buildWorkbenchCommandRequest(
      "import_hopv15_snapshot",
      {
        provider: "materials_project",
        provider_scope: "model",
        declared_effects: ["sqlite_write", "provider_cache_records"],
        api_key: "mp-secret",
        manifest_path: "D:\\private\\hopv15.json",
      },
      { idempotencyKey: "api_key=mp-secret", expectedTargetVersion: "0" },
    )) as AtomReasonXCommandResult;
    expect(tamperedResult.audit.declared_effects).toEqual(["source_import_tasks"]);
    expect(tamperedResult.output_artifacts[0]).toMatchObject({
      kind: "workflow_command_task",
      action_type: "import_hopv15_snapshot",
      provider: "hopv15",
      provider_scope: "source",
      declared_effects: ["source_import_tasks"],
    });
    expect(JSON.stringify(tamperedResult.output_artifacts)).not.toContain("mp-secret");
    expect(JSON.stringify(tamperedResult.output_artifacts)).not.toContain("api_key");
    expect(JSON.stringify(tamperedResult.output_artifacts)).not.toContain("D:\\private");
  });

  it("keeps unknown workflow-shaped commands pending instead of accepting arbitrary tasks", async () => {
    let invokeCount = 0;
    const adapter = createRuntimeWorkbenchCommandAdapter({
      invoke: async <T,>(): Promise<T> => {
        invokeCount += 1;
        throw new Error("unknown command should not reach Tauri config bridge");
      },
    });
    const request = buildWorkbenchCommandRequest(
      "provider_execution",
      {
        provider: "nomad_perla_psc",
        declared_effects: ["provider_cache"],
        api_key: "mp-secret",
      },
      { idempotencyKey: "unknown-workflow-1" },
    );

    const result = await adapter.submit(request);

    expect(invokeCount).toBe(0);
    expect(result).toMatchObject({
      schema_version: "v23.action_result.v1",
      action_type: "provider_execution",
      status: "queued",
      reason_code: "transport_pending",
      output_artifacts: [],
    });
    expect((result as AtomReasonXCommandResult).audit.declared_effects).toEqual([]);
    expect(JSON.stringify(result)).not.toContain("mp-secret");
    expect(JSON.stringify(result)).not.toContain("api_key");
  });

  it("projects workflow task results into a UI-local operator task queue without duplicates", async () => {
    const workspace = JSON.parse(JSON.stringify(fixture)) as AtomReasonXWorkspaceState;
    const workflowAction = workspace.command_actions.find(item => item.action_type === "start_nomad_sync");
    const adapter = createRuntimeWorkbenchCommandAdapter();
    const dispatcher = createWorkbenchCommandDispatcher(adapter, {
      idempotencyKey: "nomad-sync-task-1",
      expectedTargetVersion: "0",
    });

    expect(workflowAction).toBeDefined();
    const result = await submitWorkflowCommandAction(dispatcher, workflowAction!) as AtomReasonXCommandResult;
    const workflowTask = result.output_artifacts[0];
    const resultWithDuplicateArtifact = {
      ...result,
      output_artifacts: [workflowTask!, workflowTask!],
      audit: {
        ...result.audit,
        output_artifacts: [workflowTask!, workflowTask!],
      },
    } satisfies AtomReasonXCommandResult;
    const resultWithHostileConfig = {
      ...result,
      output_artifacts: [{
        ...workflowTask!,
        config: {
          api_key: "mp-secret",
          local_path: "D:\\private\\snapshot.json",
          doi_list: ["10.1000/example"],
        },
        created_at: "D:\\private\\snapshot.json",
      }],
      audit: {
        ...result.audit,
        output_artifacts: [{
          ...workflowTask!,
          config: {
            api_key: "mp-secret",
            local_path: "D:\\private\\snapshot.json",
            doi_list: ["10.1000/example"],
          },
          created_at: "D:\\private\\snapshot.json",
        }],
      },
    } as AtomReasonXCommandResult;
    const resultWithTamperedMetadata = {
      ...result,
      output_artifacts: [{
        ...workflowTask!,
        provider: "materials_project",
        provider_scope: "model",
        declared_effects: ["sqlite_write", "provider_cache_records"],
      }],
      audit: {
        ...result.audit,
        output_artifacts: [{
          ...workflowTask!,
          provider: "materials_project",
          provider_scope: "model",
          declared_effects: ["sqlite_write", "provider_cache_records"],
        }],
      },
    } as AtomReasonXCommandResult;
    const resultWithUnsafeTaskId = {
      ...result,
      output_artifacts: [{
        ...workflowTask!,
        task_id: "task-start_nomad_sync-api_key",
      }],
      audit: {
        ...result.audit,
        output_artifacts: [{
          ...workflowTask!,
          task_id: "task-start_nomad_sync-api_key",
        }],
      },
    } as AtomReasonXCommandResult;
    const projected = projectWorkflowCommandTaskResult(workspace, result);
    const projectedFromDuplicateArtifact = projectWorkflowCommandTaskResult(workspace, resultWithDuplicateArtifact);
    const projectedFromHostileConfig = projectWorkflowCommandTaskResult(workspace, resultWithHostileConfig);
    const rejectedTamperedMetadata = projectWorkflowCommandTaskResult(workspace, resultWithTamperedMetadata);
    const rejectedUnsafeTaskId = projectWorkflowCommandTaskResult(workspace, resultWithUnsafeTaskId);
    const duplicate = projectWorkflowCommandTaskResult(projected, result);

    expect(workspace.operator_tasks).toEqual([]);
    expect(projected).not.toBe(workspace);
    expect(projected.operator_tasks).toHaveLength(1);
    expect(projectedFromDuplicateArtifact.operator_tasks).toHaveLength(1);
    expect(projectedFromHostileConfig.operator_tasks).toHaveLength(1);
    expect(rejectedTamperedMetadata).toBe(workspace);
    expect(rejectedUnsafeTaskId).toBe(workspace);
    expect(projected.operator_tasks[0]).toMatchObject({
      schema_version: "v35.operator_task.v1",
      action_type: "start_nomad_sync",
      provider: "nomad_perla_psc",
      status: "queued",
      queue_scope: "operator_local",
      declared_effects: ["provider_sync_jobs"],
      writes_authorized: false,
      execution_started: false,
    });
    expect(projected.operator_tasks[0].config).toMatchObject({
      transport: "operator_task_queue",
      runtime_writes: false,
    });
    expect(duplicate).toBe(projected);
    expect(JSON.stringify(projectedFromHostileConfig.operator_tasks)).not.toContain("mp-secret");
    expect(JSON.stringify(projectedFromHostileConfig.operator_tasks)).not.toContain("D:\\private");
    expect(JSON.stringify(projectedFromHostileConfig.operator_tasks)).not.toContain("10.1000/example");
    expect(JSON.stringify(projected.operator_tasks)).not.toContain("api_key");
    expect(JSON.stringify(projected.operator_tasks)).not.toContain("readonly_token");
  });

  it("does not project non-accepted workflow task artifacts into the operator queue", async () => {
    const workspace = JSON.parse(JSON.stringify(fixture)) as AtomReasonXWorkspaceState;
    const workflowAction = workspace.command_actions.find(item => item.action_type === "start_nomad_sync");
    const adapter = createRuntimeWorkbenchCommandAdapter();
    const dispatcher = createWorkbenchCommandDispatcher(adapter, {
      idempotencyKey: "nomad-sync-task-rejected",
      expectedTargetVersion: "0",
    });

    expect(workflowAction).toBeDefined();
    const result = await submitWorkflowCommandAction(dispatcher, workflowAction!) as AtomReasonXCommandResult;
    const queuedResult = {
      ...result,
      status: "queued",
      reason_code: "transport_pending",
    } satisfies AtomReasonXCommandResult;
    const projected = projectWorkflowCommandTaskResult(workspace, queuedResult);

    expect(projected).toBe(workspace);
    expect(projected.operator_tasks).toEqual([]);
  });

  it("keeps command controls free of read-side adapter imports", () => {
    for (const [path, source] of Object.entries(COMMAND_CONTROL_MODULES)) {
      expect(source, path).not.toContain("workbench-read-adapter");
      expect(source, path).not.toContain("read-only-artifact-adapter");
      expect(source, path).toContain("WorkbenchCommandDispatcher");
    }
  });

  it("keeps source settings command identity authoritative over extra payload", () => {
    const workspace = fixture as unknown as AtomReasonXWorkspaceState;
    const source = workspace.source_settings.sources.find(item => item.provider_id === "materials_project");

    expect(source).toBeDefined();
    const payload = buildSourceSettingsCommandPayload(source!, {
      provider: "wrong_provider",
      provider_scope: "model",
      api_key: "mp-test-key",
    });

    expect(payload.provider).toBe("materials_project");
    expect(payload.provider_scope).toBe("source");
    expect(payload.api_key).toBe("mp-test-key");
  });

  it("builds Materials Project test-connection payload for the Go source-provider probe", () => {
    const workspace = fixture as unknown as AtomReasonXWorkspaceState;
    const source = workspace.source_settings.sources.find(item => item.provider_id === "materials_project");

    expect(source).toBeDefined();
    const payload = buildSourceProviderTestConnectionPayload(source!, {
      provider: "wrong_provider",
      provider_scope: "model",
      probe_contract: "wrong_contract",
      formula: "FAPbI3",
      api_key: "should-not-win",
      apiKey: "should-not-win",
      secret: "should-not-win",
      token: "should-not-win",
      password: "should-not-win",
      credential: "should-not-win",
      authorization: "should-not-win",
    });

    expect(payload.provider).toBe("materials_project");
    expect(payload.provider_scope).toBe("source");
    expect(payload.probe_contract).toBe(SOURCE_PROVIDER_CONNECTION_PROBE_SCHEMA_VERSION);
    expect(payload.formula).toBe("FAPbI3");
    expect(JSON.stringify(payload)).not.toContain("api_key");
    expect(JSON.stringify(payload)).not.toContain("should-not-win");
    expect(JSON.stringify(payload)).not.toContain("wrong_contract");
  });
});
