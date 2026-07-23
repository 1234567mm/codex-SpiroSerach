export type ReadonlyRunOperatorMode = "fixture" | "readonly_run";

export interface ReadonlyRunOperatorConfig {
  mode: ReadonlyRunOperatorMode;
  outputDir: string | null;
  readOnly: boolean;
}

export const normalizeReadonlyRunOutputDir = (value: unknown): string | null => {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
};

export const buildReadonlyRunOperatorConfig = (
  outputDir: unknown,
): ReadonlyRunOperatorConfig => {
  const normalized = normalizeReadonlyRunOutputDir(outputDir);
  return {
    mode: normalized ? "readonly_run" : "fixture",
    outputDir: normalized,
    readOnly: normalized !== null,
  };
};

export const resolveConfiguredReadonlyOutputDir = (): string | null => {
  const globalValue = normalizeReadonlyRunOutputDir((globalThis as {
    __ATOMREASONX_READONLY_OUTPUT_DIR__?: unknown;
  }).__ATOMREASONX_READONLY_OUTPUT_DIR__);
  if (globalValue) {
    return globalValue;
  }
  const href = (globalThis as { location?: { href?: string } }).location?.href;
  if (!href) {
    return null;
  }
  try {
    return normalizeReadonlyRunOutputDir(new URL(href).searchParams.get("readonlyOutputDir"));
  } catch {
    return null;
  }
};
