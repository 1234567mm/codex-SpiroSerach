// Desktop settings bridge for the AtomReasonX settings centre.
//
// Reasonix desktop persists UI settings through Wails Go bindings
// (lib/bridge.ts -> app.Settings() / app.SetDesktopXxx()). AtomReasonX adapts
// the same settings object to the Rust settings store behind the
// `settings_read` / `settings_write` Tauri commands (see
// src-tauri/src/settings_store.rs): a single JSON document under the app data
// directory, merged key-by-key on every write.

export type TauriCommandInvoke = <T>(
  command: string,
  args?: Record<string, unknown>,
) => Promise<T>;

export const DESKTOP_SETTINGS_LANG_KEY = "langPref";

/** Reads the full desktop settings object from the Rust settings store. */
export const readDesktopSettings = async (
  invoke: TauriCommandInvoke = defaultTauriInvoke,
): Promise<Record<string, unknown>> => {
  const value = await invoke<unknown>("settings_read");
  if (!isRecord(value)) {
    throw new Error("settings_read must return an object");
  }
  return value;
};

/** Deep-merges `patch` into the stored settings and returns the merged object. */
export const writeDesktopSettings = async (
  patch: Record<string, unknown>,
  invoke: TauriCommandInvoke = defaultTauriInvoke,
): Promise<Record<string, unknown>> => {
  const value = await invoke<unknown>("settings_write", { patch });
  if (!isRecord(value)) {
    throw new Error("settings_write must return an object");
  }
  return value;
};

const defaultTauriInvoke: TauriCommandInvoke = async (command, args) => {
  const invoke = (globalThis as {
    __TAURI__?: { core?: { invoke?: TauriCommandInvoke } };
  }).__TAURI__?.core?.invoke;
  if (typeof invoke !== "function") {
    throw new Error(`Tauri invoke is unavailable (${command})`);
  }
  return invoke(command, args);
};

const isRecord = (value: unknown): value is Record<string, unknown> => (
  typeof value === "object" && value !== null && !Array.isArray(value)
);
