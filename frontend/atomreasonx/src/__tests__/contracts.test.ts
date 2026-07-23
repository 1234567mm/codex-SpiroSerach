import { describe, expect, it } from "vitest";
import fixture from "../fixtures/atomreasonx-ui-fixture.json";
import type {
  AtomReasonXCommandResult,
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
  createTauriReadonlyRunSession,
  createTauriReadonlyRunTransport,
  isReadonlySidecarLoopbackBaseUrl,
  redactedReadonlySidecarLaunch,
  stopTauriReadonlySidecar,
  validateReadonlySidecarLaunch,
} from "../adapters/tauri-readonly-sidecar";
import {
  createLoadingWorkbenchWorkspaceState,
  loadWorkbenchWorkspace,
} from "../stores/workspace-store";
import { buildDataSourceDisplayRows } from "../components/DatabaseView";
import { buildSourceSettingsCommandPayload, submitSourceSettingsCommand } from "../components/SettingsModal";
import {
  buildWorkflowCommandPayload,
  canSubmitWorkflowCommandAction,
  submitWorkflowCommandAction,
} from "../components/WorkflowView";

const COMMAND_CONTROL_MODULES = import.meta.glob<string>("../components/{WorkflowView,SettingsModal}.tsx", {
  eager: true,
  import: "default",
  query: "?raw",
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

  it("exposes V33C HTL workbench source coverage and command actions", () => {
    const workspace = fixture as unknown as AtomReasonXWorkspaceState;
    const providers = workspace.source_coverage.sources.map(source => source.provider_id);
    const commands = workspace.command_actions.map(action => action.action_type);

    expect(workspace.source_coverage.lane).toBe("htl_only");
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

    expect(submitted).toHaveLength(2);
    expect(submitted[0].schema_version).toBe("v23.action_request.v1");
    expect(submitted[0].action_type).toBe("start_nomad_sync");
    expect(submitted[0].payload.declared_effects).toEqual(["provider_sync_jobs"]);
    expect(submitted[0].preconditions.expected_target_version).toBe("7");
    expect(submitted[1].action_type).toBe("key_rotate");
    expect(submitted[1].idempotency_key).toBe("atomx-dispatch-test-2");
    expect(submitted[1].payload.provider).toBe("materials_project");
    expect(submitted[1].payload.provider_scope).toBe("source");
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
});
