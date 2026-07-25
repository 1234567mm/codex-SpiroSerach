export type ReadonlyRunOperatorMode = "fixture" | "readonly_run";

export interface ReadonlyRunOperatorConfig {
  mode: ReadonlyRunOperatorMode;
  outputDir: string | null;
  readOnly: boolean;
}

export interface ReadonlyRunRecentOutputDir {
  outputDir: string;
  label: string;
  source: "active" | "recent";
}

export const normalizeReadonlyRunOutputDir = (value: unknown): string | null => {
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim();
  if (trimmed.length === 0 || isForbiddenReadonlyRunOutputDir(trimmed)) {
    return null;
  }
  return trimmed;
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

export const buildReadonlyRunRecentOutputDirs = (
  values: readonly unknown[],
  activeOutputDir: unknown = null,
): ReadonlyRunRecentOutputDir[] => {
  const results: ReadonlyRunRecentOutputDir[] = [];
  const seen = new Set<string>();
  const add = (value: unknown, source: ReadonlyRunRecentOutputDir["source"]) => {
    const outputDir = normalizeReadonlyRunOutputDir(value);
    if (!outputDir || seen.has(outputDir)) {
      return;
    }
    seen.add(outputDir);
    results.push({
      outputDir,
      label: labelForReadonlyRunOutputDir(outputDir),
      source,
    });
  };
  add(activeOutputDir, "active");
  for (const value of values) {
    add(value, "recent");
  }
  return results.slice(0, 8);
};

export const resolveConfiguredReadonlyRecentOutputDirs = (): string[] => {
  const globalValue = (globalThis as {
    __ATOMREASONX_READONLY_RECENT_OUTPUT_DIRS__?: unknown;
  }).__ATOMREASONX_READONLY_RECENT_OUTPUT_DIRS__;
  const globalRecent = normalizeReadonlyRunOutputDirArray(globalValue);
  if (globalRecent.length > 0) {
    return globalRecent;
  }
  const href = (globalThis as { location?: { href?: string } }).location?.href;
  if (!href) {
    return [];
  }
  try {
    return normalizeReadonlyRunOutputDirArray(new URL(href).searchParams.getAll("readonlyRecentOutputDir"));
  } catch {
    return [];
  }
};

const normalizeReadonlyRunOutputDirArray = (value: unknown): string[] => {
  if (!Array.isArray(value)) {
    return [];
  }
  return buildReadonlyRunRecentOutputDirs(value).map(item => item.outputDir);
};

const labelForReadonlyRunOutputDir = (outputDir: string): string => {
  const parts = outputDir.split(/[\\/]+/).filter(Boolean);
  return parts.length > 0 ? parts[parts.length - 1] : outputDir;
};

const isForbiddenReadonlyRunOutputDir = (value: string): boolean => {
  const lower = value.toLowerCase();
  const credentialMarkers = ["readonly" + "_" + "token", "api" + "_" + "key"];
  if (credentialMarkers.some(marker => lower.includes(marker))) {
    return true;
  }
  const parts = lower.split(/[\\/]+/).filter(Boolean);
  const leaf = parts.length > 0 ? parts[parts.length - 1] : lower;
  return leaf === "spiroctl" || leaf === "spiroctl.exe" || leaf.endsWith(".exe");
};
