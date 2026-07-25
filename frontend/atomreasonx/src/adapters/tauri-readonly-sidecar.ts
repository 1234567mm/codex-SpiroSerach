import {
  createHttpReadonlyRunTransport,
  type HttpReadonlyRunTransportOptions,
  type ReadonlyRunTransport,
} from "./go-readonly-run-transport";

export interface ReadonlySidecarLaunch {
  base_url: string;
  run_id: string;
  read_only: true;
  readonly_token: string;
  process_id: number;
}

export interface TauriReadonlySidecarOptions {
  outputDir: string;
  invoke?: TauriInvoke;
  fetchJson?: HttpReadonlyRunTransportOptions["fetchJson"];
}

export interface TauriReadonlyRunSession {
  transport: ReadonlyRunTransport;
  launch: ReadonlySidecarLaunch;
  stop(): Promise<void>;
}

export type TauriInvoke = <T>(command: string, args?: Record<string, unknown>) => Promise<T>;

export const createTauriReadonlyRunTransport = async ({
  outputDir,
  invoke = defaultTauriInvoke,
  fetchJson,
}: TauriReadonlySidecarOptions): Promise<ReadonlyRunTransport> => {
  return (await createTauriReadonlyRunSession({ outputDir, invoke, fetchJson })).transport;
};

export const createTauriReadonlyRunSession = async ({
  outputDir,
  invoke = defaultTauriInvoke,
  fetchJson,
}: TauriReadonlySidecarOptions): Promise<TauriReadonlyRunSession> => {
  const launch = validateReadonlySidecarLaunch(await invoke("start_readonly_sidecar", {
    outputDir,
  }));
  const transport = createHttpReadonlyRunTransport({
    baseUrl: launch.base_url,
    runId: launch.run_id,
    readonlyToken: launch.readonly_token,
    fetchJson,
  });
  return {
    transport,
    launch,
    stop() {
      return stopTauriReadonlySidecar(launch.process_id, invoke);
    },
  };
};

export const stopTauriReadonlySidecar = async (
  processId: number,
  invoke: TauriInvoke = defaultTauriInvoke,
): Promise<void> => {
  await invoke("stop_readonly_sidecar", { processId });
};

export const validateReadonlySidecarLaunch = (value: unknown): ReadonlySidecarLaunch => {
  if (!isRecord(value)) {
    throw new Error("readonly sidecar launch must be an object");
  }
  if (value.read_only !== true) {
    throw new Error("readonly sidecar launch read_only must be true");
  }
  if (typeof value.base_url !== "string" || !isReadonlySidecarLoopbackBaseUrl(value.base_url)) {
    throw new Error("readonly sidecar launch base_url must be loopback HTTP");
  }
  if (typeof value.run_id !== "string" || value.run_id.trim().length === 0) {
    throw new Error("readonly sidecar launch run_id is required");
  }
  if (typeof value.readonly_token !== "string" || value.readonly_token.trim().length < 16) {
    throw new Error("readonly sidecar launch token is missing or too short");
  }
  if (typeof value.process_id !== "number" || !Number.isInteger(value.process_id) || value.process_id <= 0) {
    throw new Error("readonly sidecar launch process_id is invalid");
  }
  return value as unknown as ReadonlySidecarLaunch;
};

export const redactedReadonlySidecarLaunch = (
  launch: ReadonlySidecarLaunch,
): Omit<ReadonlySidecarLaunch, "readonly_token"> & { readonly_token: "REDACTED" } => ({
  base_url: launch.base_url,
  run_id: launch.run_id,
  read_only: launch.read_only,
  process_id: launch.process_id,
  readonly_token: "REDACTED",
});

const defaultTauriInvoke: TauriInvoke = async (command, args) => {
  const invoke = (globalThis as {
    __TAURI__?: { core?: { invoke?: TauriInvoke } };
  }).__TAURI__?.core?.invoke;
  if (typeof invoke !== "function") {
    throw new Error("Tauri invoke is unavailable");
  }
  return invoke(command, args);
};

export const isReadonlySidecarLoopbackBaseUrl = (value: string): boolean => {
  try {
    const url = new URL(value);
    return url.protocol === "http:" &&
      url.username === "" &&
      url.password === "" &&
      url.port !== "" &&
      (url.hostname === "127.0.0.1" || url.hostname === "localhost" || url.hostname === "[::1]");
  } catch {
    return false;
  }
};

const isRecord = (value: unknown): value is Record<string, unknown> => (
  typeof value === "object" && value !== null && !Array.isArray(value)
);
