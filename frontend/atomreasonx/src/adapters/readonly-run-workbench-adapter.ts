import type {
  AtomReasonXTelemetryState,
  AtomReasonXWorkspaceState,
  TelemetryField,
} from "../contracts/types";
import {
  cloneWorkspaceState,
  createFixtureWorkbenchReadAdapter,
  type WorkbenchReadAdapter,
} from "./workbench-read-adapter";
import type {
  ReadonlyRunEnvelope,
  ReadonlyRunSurface,
  ReadonlyRunTransport,
} from "./go-readonly-run-transport";
import {
  createTauriReadonlyRunSession,
  type TauriReadonlyRunSession,
} from "./tauri-readonly-sidecar";
import {
  normalizeReadonlyRunOutputDir,
  resolveConfiguredReadonlyOutputDir,
} from "./readonly-run-operator-config";
import {
  projectWorkflowTaskRestoreReport,
  type WorkflowTaskRestoreReader,
} from "./workflow-task-restore-adapter";

export interface ReadonlyRunWorkbenchReadAdapterOptions {
  baseWorkspace: AtomReasonXWorkspaceState;
  transport: ReadonlyRunTransport;
}

export interface RuntimeWorkbenchReadAdapterOptions {
  baseWorkspace: AtomReasonXWorkspaceState;
  readonlyOutputDir?: string | null;
  createSidecarSession?: (options: { outputDir: string }) => Promise<TauriReadonlyRunSession>;
  workflowTaskRestoreReader?: WorkflowTaskRestoreReader;
}

export interface RuntimeWorkbenchReadAdapter {
  adapter: WorkbenchReadAdapter;
  readOnly: boolean;
  dispose(): Promise<void>;
}

export const createReadonlyRunWorkbenchReadAdapter = ({
  baseWorkspace,
  transport,
}: ReadonlyRunWorkbenchReadAdapterOptions): WorkbenchReadAdapter => ({
  async loadWorkspace() {
    const manifest = await transport.read("manifest");
    const artifactIndex = await transport.read("artifact_index");
    const scoringView = await transport.read("scoring_view");
    const reviewSummary = await transport.read("review_summary");
    const providerLineage = await transport.read("provider_lineage");

    const manifestPayload = requireAvailablePayload(manifest, "manifest");
    const artifactIndexPayload = requireAvailablePayload(artifactIndex, "artifact_index");
    const scoringData = requireArtifactData(scoringView, "scoring_view");
    const reviewData = requireArtifactData(reviewSummary, "review_summary");
    const lineagePayload = requireAvailablePayload(providerLineage, "provider_lineage");

    const workspace = cloneWorkspaceState(baseWorkspace);
    const runId = stringValue(manifestPayload.run_id) ?? stringValue(manifest.run_id) ?? "unknown";
    const generatedAt = stringValue(manifestPayload.generated_at);
    const energyFactCount = arrayValue(scoringData.energy_facts).length;
    const artifactCount = numberValue(artifactIndexPayload.artifact_count)
      ?? arrayValue(artifactIndexPayload.artifacts).length;
    const providerCacheRecords = artifactRecordCount(lineagePayload, "provider_cache");
    const agentTraceRecords = artifactRecordCount(lineagePayload, "agent_trace");
    const openBlockingCount = numberValue(reviewData.open_blocking_count) ?? 0;
    const candidateCount = numberValue(manifestPayload.candidate_count) ?? 0;
    const providerOutcomes = providerOutcomeCounts(manifestPayload);

    workspace.active_workspace = `readonly_run:${runId}`;
    workspace._provisional = false;
    workspace.knowledge_library = {
      ...workspace.knowledge_library,
      candidate_entities: candidateCount,
      extracted_claims: energyFactCount,
      material_records: energyFactCount,
      provider_snapshots: providerCacheRecords,
      blocked_review_items: openBlockingCount,
      index_freshness: generatedAt,
    };
    workspace.telemetry = updateReadonlyTelemetry(workspace.telemetry, {
      artifactCount,
      providerCacheRecords,
      agentTraceRecords,
      hitCount: providerOutcomes.hitCount,
      missCount: providerOutcomes.missCount,
    });
    workspace.telemetry_fields = workspace.telemetry.fields.map(field => field.name);
    return workspace;
  },
});

export const createRuntimeWorkbenchReadAdapter = ({
  baseWorkspace,
  readonlyOutputDir = resolveConfiguredReadonlyOutputDir(),
  createSidecarSession = ({ outputDir }) => createTauriReadonlyRunSession({ outputDir }),
  workflowTaskRestoreReader,
}: RuntimeWorkbenchReadAdapterOptions): RuntimeWorkbenchReadAdapter => {
  const outputDir = normalizeReadonlyRunOutputDir(readonlyOutputDir);
  if (!outputDir) {
    const fixtureAdapter = createFixtureWorkbenchReadAdapter(baseWorkspace);
    const adapter: WorkbenchReadAdapter = {
      async loadWorkspace() {
        const workspace = await fixtureAdapter.loadWorkspace();
        if (!workflowTaskRestoreReader) {
          return workspace;
        }
        return projectWorkflowTaskRestoreReport(
          workspace,
          await workflowTaskRestoreReader.restore(),
        );
      },
    };
    return {
      adapter,
      readOnly: false,
      async dispose() {},
    };
  }

  let session: TauriReadonlyRunSession | null = null;
  let stopRequested = false;
  const stopSession = async () => {
    const current = session;
    session = null;
    if (current) {
      await current.stop();
    }
  };
  const adapter: WorkbenchReadAdapter = {
    async loadWorkspace() {
      stopRequested = false;
      await stopSession();
      const nextSession = await createSidecarSession({ outputDir });
      if (stopRequested) {
        await nextSession.stop();
        throw new Error("readonly run load cancelled");
      }
      session = nextSession;
      try {
        return await createReadonlyRunWorkbenchReadAdapter({
          baseWorkspace,
          transport: nextSession.transport,
        }).loadWorkspace();
      } catch (error) {
        await stopSession();
        throw error;
      }
    },
    async dispose() {
      stopRequested = true;
      await stopSession();
    },
  };

  return {
    adapter,
    readOnly: true,
    dispose() {
      return adapter.dispose?.() ?? Promise.resolve();
    },
  };
};

const requireAvailablePayload = (
  envelope: ReadonlyRunEnvelope,
  expectedSurface: ReadonlyRunSurface,
): Record<string, unknown> => {
  if (envelope.surface !== expectedSurface) {
    throw new Error(`readonly envelope surface mismatch: expected ${expectedSurface}`);
  }
  if (envelope.status !== "available") {
    const code = isRecord(envelope.unavailable) && typeof envelope.unavailable.code === "string"
      ? `: ${envelope.unavailable.code}`
      : "";
    throw new Error(`readonly ${expectedSurface} is not available${code}`);
  }
  if (!isRecord(envelope.payload)) {
    throw new Error(`readonly ${expectedSurface} payload must be an object`);
  }
  return envelope.payload;
};

const requireArtifactData = (
  envelope: ReadonlyRunEnvelope,
  expectedSurface: ReadonlyRunSurface,
): Record<string, unknown> => {
  const payload = requireAvailablePayload(envelope, expectedSurface);
  if (!isRecord(payload.data)) {
    throw new Error(`readonly ${expectedSurface} artifact data must be an object`);
  }
  return payload.data;
};

const updateReadonlyTelemetry = (
  telemetry: AtomReasonXTelemetryState,
  values: {
    artifactCount: number;
    providerCacheRecords: number;
    agentTraceRecords: number;
    hitCount: number;
    missCount: number;
  },
): AtomReasonXTelemetryState => {
  const totalLookups = values.hitCount + values.missCount;
  return {
    ...telemetry,
    fields: upsertTelemetryFields(telemetry.fields, [
      { name: "retrieval_hit_count", value: values.hitCount, source: "runtime_computed" },
      {
        name: "average_hit_rate",
        value: totalLookups > 0 ? round4(values.hitCount / totalLookups) : 0,
        source: "runtime_computed",
      },
      { name: "active_session_state", value: "readonly_run", source: "runtime_computed" },
      { name: "request_count", value: values.artifactCount, source: "runtime_computed" },
      {
        name: "provider_usage",
        value: {
          provider_cache_records: values.providerCacheRecords,
          agent_trace_records: values.agentTraceRecords,
        },
        source: "runtime_computed",
      },
    ]),
  };
};

const upsertTelemetryFields = (
  fields: TelemetryField[],
  updates: TelemetryField[],
): TelemetryField[] => {
  const pending = new Map(updates.map(field => [field.name, field]));
  const result = fields.map(field => pending.get(field.name) ?? field);
  for (const update of updates) {
    if (!fields.some(field => field.name === update.name)) {
      result.push(update);
    }
  }
  return result;
};

const providerOutcomeCounts = (
  manifestPayload: Record<string, unknown>,
): { hitCount: number; missCount: number } => {
  const context = isRecord(manifestPayload.context) ? manifestPayload.context : {};
  const outcomes = isRecord(context.provider_outcomes) ? context.provider_outcomes : {};
  return {
    hitCount: numberValue(outcomes.hit_count) ?? 0,
    missCount: numberValue(outcomes.miss_count) ?? 0,
  };
};

const artifactRecordCount = (
  lineagePayload: Record<string, unknown>,
  kind: string,
): number => {
  const artifact = lineagePayload[kind];
  if (!isRecord(artifact)) {
    return 0;
  }
  const recordCount = numberValue(artifact.record_count);
  if (recordCount !== null) {
    return recordCount;
  }
  const records = arrayValue(artifact.records);
  if (records.length > 0) {
    return records.length;
  }
  return numberValue(isRecord(artifact.metadata) ? artifact.metadata.record_count : undefined) ?? 0;
};

const stringValue = (value: unknown): string | null => (
  typeof value === "string" && value.trim().length > 0 ? value : null
);

const numberValue = (value: unknown): number | null => (
  typeof value === "number" && Number.isFinite(value) ? value : null
);

const arrayValue = (value: unknown): unknown[] => (
  Array.isArray(value) ? value : []
);

const isRecord = (value: unknown): value is Record<string, unknown> => (
  typeof value === "object" && value !== null && !Array.isArray(value)
);

const round4 = (value: number): number => Math.round(value * 10000) / 10000;
