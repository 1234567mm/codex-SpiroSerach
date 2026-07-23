export type ReadonlyRunSurface =
  | "manifest"
  | "artifact_index"
  | "artifact_by_kind"
  | "scoring_view"
  | "review_summary"
  | "provider_lineage";

export type ReadonlyRunStatus = "available" | "degraded" | "invalid" | "unavailable";
export type ReadonlyRunSeverity = "info" | "warning" | "error" | "critical";

export interface ReadonlyRunEnvelope {
  schema_version: string;
  status: ReadonlyRunStatus;
  severity: ReadonlyRunSeverity;
  surface: ReadonlyRunSurface;
  read_only: boolean;
  run_id: string | null;
  artifact_kind: string | null;
  source: {
    backend: string;
    manifest_path: string;
  };
  payload: unknown;
  unavailable: Record<string, unknown> | null;
}

export interface ReadonlyRunReadOptions {
  artifactKind?: string;
}

export interface ReadonlyRunTransport {
  read(surface: ReadonlyRunSurface, options?: ReadonlyRunReadOptions): Promise<ReadonlyRunEnvelope>;
}

export interface HttpReadonlyRunTransportOptions {
  baseUrl: string;
  runId: string;
  readonlyToken?: string;
  fetchJson?: (url: string, init?: RequestInit) => Promise<unknown>;
}

export const createHttpReadonlyRunTransport = ({
  baseUrl,
  runId,
  readonlyToken,
  fetchJson = defaultFetchJson,
}: HttpReadonlyRunTransportOptions): ReadonlyRunTransport => ({
  async read(surface, options = {}) {
    const artifactKind = surface === "artifact_by_kind" ? requireArtifactKind(options) : undefined;
    const raw = await fetchJson(readonlyRunUrl(baseUrl, runId, surface, artifactKind), readonlyFetchInit(readonlyToken));
    return validateReadonlyRunEnvelope(raw, surface, artifactKind);
  },
});

export const validateReadonlyRunEnvelope = (
  value: unknown,
  expectedSurface: ReadonlyRunSurface,
  expectedArtifactKind?: string,
): ReadonlyRunEnvelope => {
  if (!isRecord(value)) {
    throw new Error("readonly envelope must be an object");
  }
  if (value.schema_version !== "v11.readonly_api.envelope.v1") {
    throw new Error("readonly envelope schema_version mismatch");
  }
  if (value.read_only !== true) {
    throw new Error("readonly envelope read_only must be true");
  }
  if (value.surface !== expectedSurface) {
    throw new Error(`readonly envelope surface mismatch: expected ${expectedSurface}`);
  }
  if (expectedArtifactKind && value.artifact_kind !== expectedArtifactKind) {
    throw new Error(`readonly envelope artifact_kind mismatch: expected ${expectedArtifactKind}`);
  }
  if (!isReadonlyRunStatus(value.status)) {
    throw new Error("readonly envelope status is not supported");
  }
  if (!isReadonlyRunSeverity(value.severity)) {
    throw new Error("readonly envelope severity is not supported");
  }
  if (!isRecord(value.source) || value.source.backend !== "json_artifact_repository") {
    throw new Error("readonly envelope source backend mismatch");
  }
  if (typeof value.source.manifest_path !== "string" || value.source.manifest_path.length === 0) {
    throw new Error("readonly envelope manifest_path missing");
  }
  return value as unknown as ReadonlyRunEnvelope;
};

export const readonlyRunUrl = (
  baseUrl: string,
  runId: string,
  surface: ReadonlyRunSurface,
  artifactKind?: string,
): string => {
  const encodedRunId = encodeURIComponent(runId);
  const basePath = `/runs/${encodedRunId}`;
  const pathBySurface: Record<Exclude<ReadonlyRunSurface, "artifact_by_kind">, string> = {
    manifest: `${basePath}/manifest`,
    artifact_index: `${basePath}/artifacts`,
    scoring_view: `${basePath}/scoring-view`,
    review_summary: `${basePath}/review-summary`,
    provider_lineage: `${basePath}/provider-lineage`,
  };
  const path = surface === "artifact_by_kind"
    ? `${basePath}/artifacts/${encodeURIComponent(requireArtifactKind({ artifactKind }))}`
    : pathBySurface[surface];
  return new URL(path, normalizeBaseUrl(baseUrl)).toString();
};

const requireArtifactKind = (options: ReadonlyRunReadOptions): string => {
  if (!options.artifactKind || options.artifactKind.trim().length === 0) {
    throw new Error("artifact_by_kind requires artifactKind");
  }
  return options.artifactKind;
};

const normalizeBaseUrl = (baseUrl: string): string => (
  baseUrl.endsWith("/") ? baseUrl : `${baseUrl}/`
);

const readonlyFetchInit = (readonlyToken?: string): RequestInit => {
  const token = readonlyToken?.trim();
  if (!token) {
    return { method: "GET" };
  }
  return {
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  };
};

const defaultFetchJson = async (url: string, init?: RequestInit): Promise<unknown> => {
  const response = await fetch(url, init ?? { method: "GET" });
  if (!response.ok) {
    throw new Error(`readonly run request failed: ${response.status}`);
  }
  return response.json() as Promise<unknown>;
};

const isRecord = (value: unknown): value is Record<string, unknown> => (
  typeof value === "object" && value !== null && !Array.isArray(value)
);

const isReadonlyRunStatus = (value: unknown): value is ReadonlyRunStatus => (
  value === "available" || value === "degraded" || value === "invalid" || value === "unavailable"
);

const isReadonlyRunSeverity = (value: unknown): value is ReadonlyRunSeverity => (
  value === "info" || value === "warning" || value === "error" || value === "critical"
);
