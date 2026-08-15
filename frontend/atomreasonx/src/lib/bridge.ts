// Desktop bridge for the AtomReasonX settings centre. This is the adaptation
// layer that replaces the Reasonix Wails Go bindings (its lib/bridge.ts, MIT):
// desktop preferences route to the Rust settings store (settings_read /
// settings_write), and model-provider mutations route to the existing Python
// sidecar config command bridge (config_write / key_rotate / key_remove /
// model_list_refresh).

import type {
  AtomReasonXProviderStatus,
  AtomReasonXSettingsState,
  AtomReasonXSourceSettingsState,
  ProviderConfigStatusEntry,
  ProviderRegistryStatusEntry,
} from "../contracts/types";
import type { WorkbenchCommandDispatcher } from "../adapters/command-adapter";
import type { ReadonlyRunOperatorConfig, ReadonlyRunRecentOutputDir } from "../adapters/readonly-run-operator-config";
import { isModelListArtifact } from "../adapters/chat-adapter";
import { readDesktopSettings, writeDesktopSettings } from "./settings-bridge";
import type {
  HookConfigView,
  HooksSettingsView,
  MCPInstallResult,
  MCPMarketplaceEntry,
  MemoryFact,
  MemorySuggestionsView,
  MemoryView,
  PermissionsView,
  PluginView,
  ProviderView,
  RemoteConnectionStatus,
  RemoteHostInput,
  RemoteHostView,
  RemoteLegacyWorkbenchData,
  SandboxView,
  SettingsView,
  TabMeta,
  UpdateInfo,
  UsageStatsRange,
} from "./settings-types";
import type { ThemePackView } from "./themePack";

export interface WorkspaceSettingsSlice {
  modelSettings: AtomReasonXSettingsState;
  providerRegistry: AtomReasonXProviderStatus;
  sourceSettings?: AtomReasonXSourceSettingsState;
  readonlyRunConfig?: ReadonlyRunOperatorConfig;
  readonlyRecentOutputDirs?: ReadonlyRunRecentOutputDir[];
  onApplyReadonlyRunOutputDir?: (outputDir: string | null) => void;
  commandDispatcher: WorkbenchCommandDispatcher;
}

let workspaceSlice: WorkspaceSettingsSlice | null = null;

/** Registers the live workspace projection used by Settings()/model bindings. */
export function registerWorkspaceSettingsSlice(slice: WorkspaceSettingsSlice | null): void {
  workspaceSlice = slice;
}

export function getWorkspaceSettingsSlice(): WorkspaceSettingsSlice | null {
  return workspaceSlice;
}

const DEFAULTS = {
  desktopTheme: "auto",
  desktopThemeStyle: "graphite",
  desktopLanguage: "",
  desktopCurrency: "",
  desktopLayoutStyle: "workbench",
  desktopTerminalTheme: "auto",
  closeBehavior: "background",
  displayMode: "standard",
  reasoningDisplayMode: "auto",
  statusBarStyle: "text",
  statusBarItems: [] as string[],
  conversationWidth: "standard",
  checkUpdates: true,
  telemetry: true,
  metrics: true,
};

function stringSetting(value: unknown, fallback: string): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function booleanSetting(value: unknown, fallback: boolean): boolean {
  return typeof value === "boolean" ? value : fallback;
}

/** Maps the AtomReasonX provider config status onto a Reasonix ProviderView. */
export function providerConfigToView(
  entry: ProviderConfigStatusEntry,
  registry: ProviderRegistryStatusEntry | undefined,
): ProviderView {
  const registryModels = registry?.default_models ?? [];
  return {
    name: entry.provider,
    builtIn: false,
    added: true,
    kind: registry?.provider_kind ?? "model_provider",
    baseUrl: entry.base_url ?? registry?.base_url ?? "",
    models: entry.default_model ? [entry.default_model, ...registryModels.filter((m) => m !== entry.default_model)] : registryModels,
    visionModels: [],
    visionModelsConfigured: false,
    modelsUrl: "",
    default: entry.default_model ?? "",
    apiKeyEnv: registry?.api_key_env ?? "",
    keySet: entry.has_api_key,
    requiresKey: entry.requires_api_key,
    configured: entry.has_api_key || !entry.requires_api_key,
    balanceUrl: "",
    contextWindow: registry?.context_window_tokens ?? 0,
    reasoningProtocol: "",
    thinking: "",
    supportedEfforts: [],
    defaultEffort: "",
  };
}

/** Maps a registry-only provider (not yet in user config) onto a ProviderView. */
export function registryToOfficialView(entry: ProviderRegistryStatusEntry): ProviderView {
  return {
    name: entry.provider,
    builtIn: false,
    added: false,
    kind: entry.provider_kind,
    baseUrl: entry.base_url ?? "",
    models: entry.default_models,
    visionModels: [],
    visionModelsConfigured: false,
    modelsUrl: "",
    default: entry.default_model ?? "",
    apiKeyEnv: entry.api_key_env ?? "",
    keySet: false,
    requiresKey: entry.requires_api_key,
    configured: !entry.requires_api_key,
    balanceUrl: "",
    contextWindow: entry.context_window_tokens ?? 0,
    reasoningProtocol: "",
    thinking: "",
    supportedEfforts: [],
    defaultEffort: "",
  };
}

function defaultPermissions(): PermissionsView {
  return { mode: "ask", allow: [], ask: [], deny: [] };
}

function defaultSandbox(): SandboxView {
  return {
    bash: "off",
    network: false,
    workspaceRoot: "",
    allowWrite: [],
    effectiveWorkspaceRoot: "",
    effectiveWriteRoots: [],
    shell: "auto",
    effectiveShell: "",
  };
}

function emptyMemoryView(): MemoryView {
  return {
    docs: [],
    facts: [],
    archives: [],
    scopes: [],
    instructionDiagnostics: [],
    conflicts: [],
    lastRecall: { query: "", hits: [], omitted: 0, charBudget: 0, usedChars: 0 },
    storeDir: "",
    available: false,
  };
}

function emptyMemoryFact(): MemoryFact {
  return { name: "", description: "", type: "", scope: "global", body: "", freshness: "fresh" };
}

async function readSettingsObject(..._args: unknown[]): Promise<Record<string, unknown>> {
  try {
    return await readDesktopSettings();
  } catch {
    return {};
  }
}

async function buildSettingsView(..._args: unknown[]): Promise<SettingsView> {
  const [stored, slice] = await Promise.all([readSettingsObject(), Promise.resolve(workspaceSlice)]);
  const configured = slice?.modelSettings.providers ?? [];
  const registry = slice?.providerRegistry.providers ?? [];
  const configuredNames = new Set(configured.map((p) => p.provider));
  const providers: ProviderView[] = configured.map((entry) => (
    providerConfigToView(entry, registry.find((r) => r.provider === entry.provider))
  ));
  const officialProviders: ProviderView[] = registry
    .filter((entry) => !configuredNames.has(entry.provider))
    .map(registryToOfficialView);
  const enabledWithDefault = configured.find((p) => p.enabled && p.default_model);
  const agent = (stored.agent && typeof stored.agent === "object" ? stored.agent : {}) as Record<string, unknown>;
  return {
    defaultModel: typeof stored.defaultModel === "string" && stored.defaultModel
      ? stored.defaultModel
      : enabledWithDefault ? `${enabledWithDefault.provider}/${enabledWithDefault.default_model}` : "",
    plannerModel: typeof agent.plannerModel === "string" ? agent.plannerModel : "",
    subagentModel: typeof agent.subagentModel === "string" ? agent.subagentModel : "",
    subagentEffort: typeof agent.subagentEffort === "string" ? agent.subagentEffort : "",
    autoPlan: "off",
    providers,
    officialProviders,
    providerPresets: [],
    permissions: stored.permissions as PermissionsView ?? defaultPermissions(),
    sandbox: stored.sandbox as SandboxView ?? defaultSandbox(),
    network: (stored.network as SettingsView["network"]) ?? { proxyMode: "auto", proxyUrl: "", noProxy: "", proxy: { type: "socks5", server: "", port: 0, username: "", password: "" } },
    agent: {
      temperature: 0,
      maxSteps: 0,
      plannerMaxSteps: 0,
      maxSubagentDepth: 2,
      maxSubagentConcurrency: 6,
      maxParallelWriters: 3,
      systemPrompt: "",
      reasoningLanguage: "auto",
      compactRatio: 0.85,
      ...agent,
    },
    desktopLanguage: stringSetting(stored.desktopLanguage, DEFAULTS.desktopLanguage),
    desktopCurrency: stringSetting(stored.desktopCurrency, DEFAULTS.desktopCurrency),
    desktopLayoutStyle: stringSetting(stored.desktopLayoutStyle, DEFAULTS.desktopLayoutStyle),
    desktopTheme: stringSetting(stored.desktopTheme, DEFAULTS.desktopTheme),
    desktopThemeStyle: stringSetting(stored.desktopThemeStyle, DEFAULTS.desktopThemeStyle),
    desktopTerminalTheme: stringSetting(stored.desktopTerminalTheme, DEFAULTS.desktopTerminalTheme),
    closeBehavior: stringSetting(stored.closeBehavior, DEFAULTS.closeBehavior),
    displayMode: stringSetting(stored.displayMode, DEFAULTS.displayMode),
    reasoningDisplayMode: stringSetting(stored.reasoningDisplayMode, DEFAULTS.reasoningDisplayMode),
    statusBarStyle: stringSetting(stored.statusBarStyle, DEFAULTS.statusBarStyle),
    statusBarItems: Array.isArray(stored.statusBarItems)
      ? stored.statusBarItems.filter((item): item is string => typeof item === "string")
      : DEFAULTS.statusBarItems,
    defaultToolApprovalMode: stringSetting(stored.defaultToolApprovalMode, "ask"),
    checkUpdates: booleanSetting(stored.checkUpdates, DEFAULTS.checkUpdates),
    updateChannel: "stable",
    telemetry: booleanSetting(stored.telemetry, DEFAULTS.telemetry),
    metrics: booleanSetting(stored.metrics, DEFAULTS.metrics),
    configPath: "",
    providerKinds: [],
    autoApproveTools: false,
    bypass: false,
    conversationWidth: stringSetting(stored.conversationWidth, DEFAULTS.conversationWidth),
  };
}

function requireDispatcher(): WorkbenchCommandDispatcher {
  const dispatcher = workspaceSlice?.commandDispatcher;
  if (!dispatcher) {
    throw new Error("Command transport is unavailable");
  }
  return dispatcher;
}

function findConfiguredProviderByName(name: string): ProviderConfigStatusEntry | undefined {
  return workspaceSlice?.modelSettings.providers.find((p) => p.provider === name);
}

function findProviderByApiKeyEnv(apiKeyEnv: string): ProviderConfigStatusEntry | undefined {
  const registry = workspaceSlice?.providerRegistry.providers ?? [];
  const entry = registry.find((r) => r.api_key_env === apiKeyEnv);
  if (!entry) return undefined;
  return findConfiguredProviderByName(entry.provider);
}

async function submitModelAction(
  actionType: string,
  provider: string,
  extra: Record<string, unknown> = {},
): Promise<unknown> {
  const dispatcher = requireDispatcher();
  return dispatcher.submitAction(actionType, { provider, provider_scope: "model", ...extra });
}

async function runModelAction(
  actionType: string,
  provider: string,
  extra: Record<string, unknown> = {},
): Promise<void> {
  const result = await submitModelAction(actionType, provider, extra);
  if (isAtomReasonXCommandResult(result) && result.status !== "accepted" && result.status !== "queued") {
    throw new Error(result.message || "The model command failed.");
  }
}

function isAtomReasonXCommandResult(value: unknown): value is {
  schema_version: string;
  status: string;
  message: string;
  reason_code: string;
  output_artifacts: unknown[];
} {
  return typeof value === "object" && value !== null
    && (value as { schema_version?: unknown }).schema_version === "v23.action_result.v1";
}

// ── The adapted `app` surface (Reasonix lib/bridge.ts shape) ────────────────

export const app = {
  async Settings(..._args: unknown[]): Promise<SettingsView> {
    return buildSettingsView();
  },

  async ReloadSettings(..._args: unknown[]): Promise<void> {
    /* State lives in the Rust settings store; nothing to reload locally. */
  },

  async Version(..._args: unknown[]): Promise<string> {
    const tauri = (globalThis as {
      __TAURI__?: { app?: { getVersion?: () => Promise<string> } };
    }).__TAURI__;
    if (tauri?.app?.getVersion) return tauri.app.getVersion();
    return "0.1.0";
  },

  async SetDesktopAppearance(theme: string, style: string): Promise<void> {
    await writeDesktopSettings({ desktopTheme: theme, desktopThemeStyle: style });
  },

  async SetDesktopLanguage(lang: string): Promise<void> {
    await writeDesktopSettings({ desktopLanguage: lang });
  },

  async SetDesktopCurrency(currency: string): Promise<void> {
    await writeDesktopSettings({ desktopCurrency: currency });
  },

  async SetDesktopLayoutStyle(style: string): Promise<void> {
    await writeDesktopSettings({ desktopLayoutStyle: style });
  },

  async SetDesktopTerminalTheme(theme: string): Promise<void> {
    await writeDesktopSettings({ desktopTerminalTheme: theme });
  },

  async SetDesktopZoomFactor(factor: number): Promise<void> {
    await writeDesktopSettings({ zoomFactor: factor });
  },

  async GetDesktopZoomFactor(..._args: unknown[]): Promise<number> {
    const stored = await readSettingsObject();
    return typeof stored.zoomFactor === "number" ? stored.zoomFactor : 1;
  },

  async SetDesktopConversationWidth(width: string): Promise<void> {
    await writeDesktopSettings({ conversationWidth: width });
  },

  async SetDesktopCheckUpdates(enabled: boolean): Promise<void> {
    await writeDesktopSettings({ checkUpdates: enabled });
  },

  async SetDesktopTelemetry(enabled: boolean): Promise<void> {
    await writeDesktopSettings({ telemetry: enabled });
  },

  async SetDesktopMetrics(enabled: boolean): Promise<void> {
    await writeDesktopSettings({ metrics: enabled });
  },

  async SetCloseBehavior(mode: string): Promise<void> {
    await writeDesktopSettings({ closeBehavior: mode });
  },

  async SetDisplayMode(mode: string): Promise<void> {
    await writeDesktopSettings({ displayMode: mode });
  },

  async SetReasoningDisplayMode(mode: string): Promise<void> {
    await writeDesktopSettings({ reasoningDisplayMode: mode, reasoningDisplayModeExplicit: true });
  },

  async SetStatusBarItems(items: string[]): Promise<void> {
    await writeDesktopSettings({ statusBarItems: items });
  },

  async SetStatusBarStyle(style: string): Promise<void> {
    await writeDesktopSettings({ statusBarStyle: style });
  },

  async SetDefaultToolApprovalMode(mode: string): Promise<void> {
    await writeDesktopSettings({ defaultToolApprovalMode: mode });
  },

  async SetCompactRatio(ratio: number): Promise<void> {
    const stored = await readSettingsObject();
    const agent = { ...((stored.agent && typeof stored.agent === "object" ? stored.agent : {}) as Record<string, unknown>), compactRatio: ratio };
    await writeDesktopSettings({ agent });
  },

  async SetMaxParallelWriters(n: number): Promise<void> {
    const stored = await readSettingsObject();
    const agent = { ...((stored.agent && typeof stored.agent === "object" ? stored.agent : {}) as Record<string, unknown>), maxParallelWriters: n };
    await writeDesktopSettings({ agent });
  },

  async SetReasoningLanguage(lang: string): Promise<void> {
    const stored = await readSettingsObject();
    const agent = { ...((stored.agent && typeof stored.agent === "object" ? stored.agent : {}) as Record<string, unknown>), reasoningLanguage: lang };
    await writeDesktopSettings({ agent });
  },

  async SetPermissionMode(mode: string): Promise<void> {
    const stored = await readSettingsObject();
    const permissions = { ...(stored.permissions && typeof stored.permissions === "object" ? stored.permissions : {}) as Record<string, unknown>, mode };
    await writeDesktopSettings({ permissions });
  },

  async AddPermissionRule(list: string, rule: string): Promise<void> {
    const stored = await readSettingsObject();
    const permissions = { ...(stored.permissions && typeof stored.permissions === "object" ? stored.permissions : {}) as Record<string, string[]> };
    const current = Array.isArray(permissions[list]) ? permissions[list] : [];
    if (!current.includes(rule)) {
      await writeDesktopSettings({ permissions: { ...permissions, [list]: [...current, rule] } });
    }
  },

  async RemovePermissionRule(list: string, rule: string): Promise<void> {
    const stored = await readSettingsObject();
    const permissions = { ...(stored.permissions && typeof stored.permissions === "object" ? stored.permissions : {}) as Record<string, string[]> };
    const current = Array.isArray(permissions[list]) ? permissions[list] : [];
    await writeDesktopSettings({ permissions: { ...permissions, [list]: current.filter((entry) => entry !== rule) } });
  },

  async SetSandbox(bash: string, network: boolean, workspaceRoot: string, allowWrite: string[], shell: string): Promise<void> {
    const stored = await readSettingsObject();
    const sandbox = { ...(stored.sandbox && typeof stored.sandbox === "object" ? stored.sandbox : {}) as Record<string, unknown> };
    await writeDesktopSettings({ sandbox: { ...sandbox, bash, network, workspaceRoot, allowWrite, shell } });
  },

  async SetNetwork(..._args: unknown[]): Promise<void> {
    const [network] = _args;
    await writeDesktopSettings({ network: network as Record<string, unknown> });
  },

  async HooksSettings(scope: string): Promise<HooksSettingsView> {
    const stored = await readSettingsObject();
    const hooks = (stored.hooks && typeof stored.hooks === "object" ? stored.hooks : {}) as Record<string, unknown>;
    const scoped = (hooks[scope] && typeof hooks[scope] === "object" ? hooks[scope] : {}) as Record<string, unknown>;
    return {
      scope,
      path: "",
      projectRoot: "",
      trusted: Boolean(scoped.trusted),
      hooks: Array.isArray(scoped.hooks) ? (scoped.hooks as HookConfigView[]) : [],
      events: [],
    };
  },

  async SaveHooksSettings(scope: string, hooks: HookConfigView[]): Promise<void> {
    const stored = await readSettingsObject();
    const existing = (stored.hooks && typeof stored.hooks === "object" ? stored.hooks : {}) as Record<string, unknown>;
    await writeDesktopSettings({ hooks: { ...existing, [scope]: { hooks } } });
  },

  async SaveHooksSettingsForRoot(..._args: unknown[]): Promise<void> {
    const [scope, , hooks] = _args;
    await this.SaveHooksSettings(String(scope ?? ""), hooks as HookConfigView[]);
  },

  // ── Model-provider bindings (Python sidecar config command bridge) ────────

  async SaveProvider(provider: ProviderView): Promise<string> {
    await runModelAction("config_write", provider.name, {
      config: {
        enabled: provider.added !== false,
        base_url: provider.baseUrl,
        default_model: provider.default,
      },
    });
    return "";
  },

  async SaveProviderWithKey(provider: ProviderView, key: string): Promise<string> {
    await submitModelAction("key_rotate", provider.name, { api_key: key });
    await runModelAction("config_write", provider.name, {
      config: {
        enabled: provider.added !== false,
        base_url: provider.baseUrl,
        default_model: provider.default,
      },
    });
    return "";
  },

  async SaveProviderKey(apiKeyEnv: string, value: string): Promise<void> {
    const provider = findProviderByApiKeyEnv(apiKeyEnv);
    if (!provider) throw new Error(`No provider resolves API key env ${apiKeyEnv}`);
    await runModelAction("key_rotate", provider.provider, { api_key: value });
  },

  async SetProviderKey(providerName: string, value: string): Promise<void> {
    await runModelAction("key_rotate", providerName, { api_key: value });
  },

  async ClearProviderKey(apiKeyEnv: string): Promise<void> {
    const provider = findProviderByApiKeyEnv(apiKeyEnv);
    if (!provider) throw new Error(`No provider resolves API key env ${apiKeyEnv}`);
    await runModelAction("key_remove", provider.provider);
  },

  async SetDefaultModel(ref: string): Promise<void> {
    const [providerName, ...modelParts] = ref.split("/");
    const model = modelParts.join("/");
    if (!providerName || !model) return;
    await runModelAction("config_write", providerName, { config: { default_model: model } });
  },

  async SetPlannerModel(ref: string): Promise<void> {
    const stored = await readSettingsObject();
    const agent = { ...((stored.agent && typeof stored.agent === "object" ? stored.agent : {}) as Record<string, unknown>), plannerModel: ref };
    await writeDesktopSettings({ agent });
  },

  async SetSubagentModel(ref: string): Promise<void> {
    const stored = await readSettingsObject();
    const agent = { ...((stored.agent && typeof stored.agent === "object" ? stored.agent : {}) as Record<string, unknown>), subagentModel: ref };
    await writeDesktopSettings({ agent });
  },

  async SetSubagentEffort(effort: string): Promise<void> {
    const stored = await readSettingsObject();
    const agent = { ...((stored.agent && typeof stored.agent === "object" ? stored.agent : {}) as Record<string, unknown>), subagentEffort: effort };
    await writeDesktopSettings({ agent });
  },

  async SetMaxSubagentDepth(depth: number): Promise<void> {
    const stored = await readSettingsObject();
    const agent = { ...((stored.agent && typeof stored.agent === "object" ? stored.agent : {}) as Record<string, unknown>), maxSubagentDepth: depth };
    await writeDesktopSettings({ agent });
  },

  async SetMaxSubagentConcurrency(n: number): Promise<void> {
    const stored = await readSettingsObject();
    const agent = { ...((stored.agent && typeof stored.agent === "object" ? stored.agent : {}) as Record<string, unknown>), maxSubagentConcurrency: n };
    await writeDesktopSettings({ agent });
  },

  async SetProviderWebSearch(providerNames: string[], enabled: boolean): Promise<void> {
    for (const name of providerNames) {
      await runModelAction("config_write", name, { config: { web_search: enabled } });
    }
  },

  async RemoveProviderAccesses(providerNames: string[]): Promise<string> {
    for (const name of providerNames) {
      await runModelAction("config_write", name, { config: { enabled: false } });
    }
    return "";
  },

  async AddOfficialProviderAccess(kind: string, key: string): Promise<void> {
    // The registry entry only exists in the Python source registry; enable it
    // through config_write so the provider joins the user config.
    const registry = workspaceSlice?.providerRegistry.providers.find((r) => r.provider === kind);
    if (!registry) throw new Error(`Unknown provider kind ${kind}`);
    if (key.trim()) {
      await submitModelAction("key_rotate", kind, { api_key: key.trim() });
    }
    await runModelAction("config_write", kind, { config: { enabled: true } });
  },

  async UpgradeDeepSeekProviderAccess(kind: string): Promise<void> {
    await this.AddOfficialProviderAccess(kind, "");
  },

  async AddProviderPresetAccess(..._args: unknown[]): Promise<void> {
    const [id] = _args;
    await this.AddOfficialProviderAccess(String(id ?? ""), "");
  },

  async ResetProviderPresetAccess(id: string): Promise<void> {
    await runModelAction("config_write", id, { config: { enabled: false } });
  },

  async FetchProviderModels(provider: ProviderView): Promise<string[]> {
    const result = await submitModelAction("model_list_refresh", provider.name);
    if (!isAtomReasonXCommandResult(result)) return [];
    const artifact = result.output_artifacts.find(isModelListArtifact);
    if (!artifact || !Array.isArray(artifact.models)) return [];
    return artifact.models.filter((model): model is string => typeof model === "string");
  },

  async FetchAllProviderModels(providers: ProviderView[]): Promise<Record<string, string[]>> {
    const out: Record<string, string[]> = {};
    for (const provider of providers) {
      try {
        out[provider.name] = await this.FetchProviderModels(provider);
      } catch {
        out[provider.name] = [];
      }
    }
    return out;
  },

  async SaveProviderModelCatalogs(updates: Array<{ name: string; models: string[]; default: string }>): Promise<void> {
    for (const update of updates) {
      await runModelAction("config_write", update.name, {
        config: { default_model: update.default || "" },
      });
    }
  },

  // ── Capability tabs (config persisted in the Rust settings store; runtime
  // ── engines are not bundled yet, so views start empty) ────────────────────

  async Capabilities(..._args: unknown[]): Promise<{ servers: never[]; skills: never[]; skillRoots: never[]; plugins: never[] }> {
    return { servers: [], skills: [], skillRoots: [], plugins: [] };
  },

  async MCPServers(..._args: unknown[]): Promise<never[]> {
    return [];
  },

  async SkillsSettings(..._args: unknown[]): Promise<{ skills: never[]; skillRoots: never[] }> {
    return { skills: [], skillRoots: [] };
  },

  async Plugins(..._args: unknown[]): Promise<never[]> {
    return [];
  },

  async MCPMarketplace(..._args: unknown[]): Promise<{ servers: never[]; cached: boolean }> {
    return { servers: [], cached: true };
  },

  async MCPMarketplaceResolve(..._args: unknown[]): Promise<MCPMarketplaceEntry> {
    const [name = ""] = _args as [string?];
    return { name: String(name), suggestedName: String(name), installable: false, args: [] };
  },

  async Meta(..._args: unknown[]): Promise<{ tabs: TabMeta[]; workspaceRoot?: string; workspacePath?: string; cwd?: string; eventChannel?: string }> {
    return { tabs: [] };
  },

  async ListTabs(..._args: unknown[]): Promise<TabMeta[]> {
    return [];
  },

  async AddMCPServer(..._args: unknown[]): Promise<MCPInstallResult | null> {
    return null;
  },

  async UpdateMCPServer(..._args: unknown[]): Promise<MCPInstallResult | null> {
    return null;
  },

  async InstallMCPServer(..._args: unknown[]): Promise<MCPInstallResult> {
    return { name: "", state: "issue", toolCount: 0, action: "none", message: "" };
  },

  async RemoveMCPServer(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  async ReconnectMCPServer(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  async AuthenticateMCPServer(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  async ClearMCPServerAuthentication(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  async SetMCPServerEnabled(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  async RefreshSkills(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  async AddSkillPath(..._args: unknown[]): Promise<null> {
    return null;
  },

  async SetSkillPathEnabled(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  async SetSkillEnabled(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  async SetSkillImplicitInvocation(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  async PickSkillFolder(..._args: unknown[]): Promise<string> {
    return "";
  },

  async InstallPlugin(..._args: unknown[]): Promise<string> {
    return "";
  },

  async PlanPluginInstall(..._args: unknown[]): Promise<string> {
    return "";
  },

  async UpdatePlugin(..._args: unknown[]): Promise<string> {
    return "";
  },

  async RemovePlugin(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  async SetPluginEnabled(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  async PluginDoctor(..._args: unknown[]): Promise<PluginView> {
    return { name: "", root: "", enabled: false, skills: 0, hooks: 0, mcpServers: 0 };
  },

  async PickPluginFolder(..._args: unknown[]): Promise<string> {
    return "";
  },

  // ── Memory tab ─────────────────────────────────────────────────────────────

  async Memory(..._args: unknown[]): Promise<MemoryView> {
    return emptyMemoryView();
  },

  async MemoryForTab(..._args: unknown[]): Promise<MemoryView> {
    return emptyMemoryView();
  },

  async MemoryRevisions(..._args: unknown[]): Promise<null> {
    return null;
  },

  async MemoryRevisionsForTab(..._args: unknown[]): Promise<null> {
    return null;
  },

  async MemorySuggestions(..._args: unknown[]): Promise<MemorySuggestionsView> {
    return { memories: [], skills: [], generatedAt: "", available: false, source: "" };
  },

  async MemorySuggestionsForTab(..._args: unknown[]): Promise<MemorySuggestionsView> {
    return { memories: [], skills: [], generatedAt: "", available: false, source: "" };
  },

  async Remember(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  async RememberForTab(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  async Forget(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  async ForgetForTab(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  async AcceptMemorySuggestion(..._args: unknown[]): Promise<string> {
    return "";
  },

  async AcceptMemorySuggestionForTab(..._args: unknown[]): Promise<string> {
    return "";
  },

  async AcceptSkillSuggestion(..._args: unknown[]): Promise<string> {
    return "";
  },

  async AcceptSkillSuggestionForTab(..._args: unknown[]): Promise<string> {
    return "";
  },

  async RestoreArchivedMemory(..._args: unknown[]): Promise<MemoryFact> {
    return emptyMemoryFact();
  },

  async RestoreArchivedMemoryForTab(..._args: unknown[]): Promise<MemoryFact> {
    return emptyMemoryFact();
  },

  async RestoreMemoryRevision(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  async RestoreMemoryRevisionForTab(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  async SaveDoc(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  async SaveDocForTab(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  // ── Remote hosts tab ───────────────────────────────────────────────────────

  async RemoteHosts(..._args: unknown[]): Promise<RemoteHostView[]> {
    return [];
  },

  async AddRemoteHost(..._args: unknown[]): Promise<null> {
    return null;
  },

  async UpdateRemoteHost(..._args: unknown[]): Promise<null> {
    return null;
  },

  async RemoveRemoteHost(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  async ConnectRemoteHost(..._args: unknown[]): Promise<null> {
    return null;
  },

  async DisconnectRemoteHost(..._args: unknown[]): Promise<null> {
    return null;
  },

  async RemoteConnectionStatuses(..._args: unknown[]): Promise<RemoteConnectionStatus[]> {
    return [];
  },

  async ScanSSHConfig(..._args: unknown[]): Promise<RemoteHostInput[]> {
    return [];
  },

  async ScanRemoteLegacyWorkbenchData(..._args: unknown[]): Promise<RemoteLegacyWorkbenchData> {
    return { mirrorCount: 0, mirrorBytes: 0, trustFile: false };
  },

  async CleanRemoteLegacyWorkbenchData(..._args: unknown[]): Promise<null> {
    return null;
  },

  // ── Subagents tab ──────────────────────────────────────────────────────────

  async CreateSubagentProfile(..._args: unknown[]): Promise<null> {
    return null;
  },

  async UpdateSubagentProfile(..._args: unknown[]): Promise<null> {
    return null;
  },

  async DeleteSubagentProfile(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  async SetSubagentProfileModel(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  async SetSubagentProfileEffort(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  async TrySubagentProfile(..._args: unknown[]): Promise<null> {
    return null;
  },

  async CancelTrySubagentProfile(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  async AvailableSubagentTools(..._args: unknown[]): Promise<never[]> {
    return [];
  },

  // ── Theme packs (appearance) ───────────────────────────────────────────────

  async SaveThemePack(..._args: unknown[]): Promise<ThemePackView> {
    const [name = ""] = _args as [string?];
    return {
      id: String(name).toLowerCase().replace(/[^a-z0-9-]/g, "-").slice(0, 48),
      name: String(name),
      baseStyle: "graphite",
      builtin: false,
      kind: "user",
      active: false,
      hasBackground: false,
      tokens: {},
      recipes: {},
    };
  },

  async ListThemePacks(..._args: unknown[]): Promise<ThemePackView[]> {
    return [];
  },

  async DeleteThemePack(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  async ImportThemePack(..._args: unknown[]): Promise<{ pack: ThemePackView; needsReplace?: boolean } | null> {
    return null;
  },

  async ExportThemePack(..._args: unknown[]): Promise<string> {
    return "";
  },

  async CopyThemePack(..._args: unknown[]): Promise<ThemePackView> {
    const [id = "", , name = ""] = _args as [string?, string?, string?];
    return {
      id: String(id),
      name: String(name),
      baseStyle: "graphite",
      builtin: false,
      kind: "user",
      active: false,
      hasBackground: false,
      tokens: {},
      recipes: {},
    };
  },

  async GetActiveThemePack(..._args: unknown[]): Promise<{ pack: ThemePackView | null; activeThemeId: string }> {
    return { pack: null, activeThemeId: "" };
  },

  async ActivateThemePack(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  async ResetThemePack(..._args: unknown[]): Promise<void> {
    /* no runtime yet */
  },

  async PickThemeBackground(..._args: unknown[]): Promise<string> {
    return "";
  },

  // ── Storage tab ────────────────────────────────────────────────────────────

  async StorageSettings(..._args: unknown[]): Promise<{ defaultWorkspace: string; statePath: string; cachePath: string; extensionsPath: string }> {
    return { defaultWorkspace: "", statePath: "", cachePath: "", extensionsPath: "" };
  },

  async UsageStats(..._args: unknown[]): Promise<UsageStatsRange> {
    return {
      from: "",
      to: "",
      tokens: 0,
      requests: 0,
      turns: 0,
      cacheHit: 0,
      cacheMiss: 0,
      activeDays: 0,
      topModel: "",
      topProvider: "",
      daily: [],
      models: [],
      providers: [],
    };
  },

  // ── Updater (Tauri updater plugin; pubkey/endpoints stay in tauri.conf.json) ──

  async CheckUpdate(channel: string): Promise<UpdateInfo | null> {
    return updaterCheckUpdate(channel);
  },

  async ApplyUpdateRequest(channel: string, version: string, requestId: string): Promise<void> {
    await updaterApplyUpdateRequest(channel, version, requestId);
  },

  async AbandonPendingUpdate(..._args: unknown[]): Promise<void> {
    await updaterAbandonPendingUpdate();
  },

  async OpenDownloadPage(..._args: unknown[]): Promise<void> {
    updaterOpenDownloadPage();
  },
} as const;

/** Opens an external URL (browser fallback; the Tauri opener plugin is absent). */
export function openExternal(url: string): void {
  try {
    window.open(url, "_blank", "noopener,noreferrer");
  } catch {
    /* ignore */
  }
}

// ── Updater adaptation (Tauri updater plugin instead of Wails updater.go) ───
//
// The Tauri updater plugin (tauri-plugin-updater) is already configured in
// tauri.conf.json (pubkey + release endpoints + createUpdaterArtifacts). The
// plugin's native commands are invoked directly through the core invoke
// bridge, and its global events (tauri://update-status,
// tauri://update-download-progress) are re-shaped into the Reasonix
// UpdateProgress stream that lib/useUpdater.ts consumes.

type UpdaterStatusEvent = {
  status?: "PENDING" | "DONE" | "ERROR" | "UPTODATE" | string;
  error?: string;
};

type UpdaterProgressEvent = {
  chunkLength: number;
  contentLength?: number;
};

const RELEASES_PAGE = "https://github.com/1234567mm/codex-SpiroSerach/releases/latest";

let activeUpdateRequestId: string | null = null;
let activeUpdateVersion = "";
let downloadReceived = 0;
let downloadTotal = 0;
const updaterProgressListeners = new Set<(p: {
  requestId: string;
  version: string;
  channel: string;
  phase: string;
  received: number;
  total: number;
  err?: string;
}) => void>();
let updaterListening = false;

async function tauriEventListen(event: string, handler: (payload: unknown) => void): Promise<() => void> {
  const tauri = (globalThis as {
    __TAURI__?: { event?: { listen?: (event: string, handler: (event: { payload: unknown }) => void) => Promise<() => void> } };
  }).__TAURI__;
  if (tauri?.event?.listen) return tauri.event.listen(event, handler);
  return () => undefined;
}

function publishUpdaterProgress(phase: string, extra: Partial<{ received: number; total: number; err: string }> = {}) {
  if (!activeUpdateRequestId) return;
  const event = {
    requestId: activeUpdateRequestId,
    version: activeUpdateVersion,
    channel: "stable",
    phase,
    received: extra.received ?? downloadReceived,
    total: extra.total ?? downloadTotal,
    err: extra.err,
  };
  for (const listener of updaterProgressListeners) listener(event);
}

function ensureUpdaterListeners() {
  if (updaterListening) return;
  updaterListening = true;
  void tauriEventListen("tauri://update-status", (payload) => {
    const status = (payload as UpdaterStatusEvent | undefined)?.status ?? "";
    switch (status) {
      case "PENDING":
        downloadReceived = 0;
        publishUpdaterProgress("downloading", { received: 0 });
        break;
      case "DONE":
        publishUpdaterProgress("installing");
        break;
      case "ERROR":
        publishUpdaterProgress("error", { err: (payload as UpdaterStatusEvent).error ?? "update failed" });
        break;
      default:
        break;
    }
  });
  void tauriEventListen("tauri://update-download-progress", (payload) => {
    const progress = payload as UpdaterProgressEvent | undefined;
    if (!progress) return;
    downloadReceived += progress.chunkLength;
    if (typeof progress.contentLength === "number" && progress.contentLength > 0) {
      downloadTotal = progress.contentLength;
    }
    publishUpdaterProgress("downloading");
  });
}

function resetUpdaterState() {
  activeUpdateRequestId = null;
  activeUpdateVersion = "";
  downloadReceived = 0;
  downloadTotal = 0;
}

export function onUpdaterProgress(
  listener: (p: {
    requestId: string;
    version: string;
    channel: string;
    phase: string;
    received: number;
    total: number;
    err?: string;
  }) => void,
): () => void {
  ensureUpdaterListeners();
  updaterProgressListeners.add(listener);
  return () => updaterProgressListeners.delete(listener);
}

async function updaterCheckUpdate(channel: string): Promise<UpdateInfo | null> {
  const invoke = (globalThis as {
    __TAURI__?: { core?: { invoke?: <T>(command: string, args?: Record<string, unknown>) => Promise<T> } };
  }).__TAURI__?.core?.invoke;
  if (typeof invoke !== "function") {
    throw new Error("Tauri updater transport is unavailable");
  }
  const version = await app.Version();
  try {
    const result = (await invoke<unknown>("plugin:updater|check")) as {
      shouldUpdate?: boolean;
      manifest?: { version?: string; body?: string; date?: string };
      error?: string;
    } | null;
    if (!result || typeof result !== "object") {
      return null;
    }
    if (result.error) {
      return {
        available: false,
        current: version,
        latest: "",
        notes: "",
        channel: channel || "stable",
        canSelfUpdate: false,
        downloaded: false,
        downloadUrl: RELEASES_PAGE,
        assetSize: 0,
        err: result.error,
      };
    }
    const manifest = result.manifest ?? {};
    return {
      available: result.shouldUpdate === true && Boolean(manifest.version),
      current: version,
      latest: manifest.version ?? "",
      notes: manifest.body ?? "",
      channel: channel || "stable",
      canSelfUpdate: true,
      installMode: "passive",
      downloaded: false,
      downloadUrl: RELEASES_PAGE,
      assetSize: 0,
    };
  } catch (error) {
    return {
      available: false,
      current: version,
      latest: "",
      notes: "",
      channel: channel || "stable",
      canSelfUpdate: false,
      downloaded: false,
      downloadUrl: RELEASES_PAGE,
      assetSize: 0,
      err: error instanceof Error ? error.message : String(error),
    };
  }
}

async function updaterApplyUpdateRequest(channel: string, version: string, requestId: string): Promise<void> {
  const invoke = (globalThis as {
    __TAURI__?: { core?: { invoke?: <T>(command: string, args?: Record<string, unknown>) => Promise<T> } };
  }).__TAURI__?.core?.invoke;
  if (typeof invoke !== "function") {
    throw new Error("Tauri updater transport is unavailable");
  }
  if (channel !== "stable") {
    throw new Error(`update channel ${channel} is not supported`);
  }
  activeUpdateRequestId = requestId;
  activeUpdateVersion = version;
  downloadReceived = 0;
  downloadTotal = 0;
  await invoke<void>("plugin:updater|download_and_install", {});
}

async function updaterAbandonPendingUpdate(..._args: unknown[]): Promise<void> {
  resetUpdaterState();
}

function updaterOpenDownloadPage(): void {
  openExternal(RELEASES_PAGE);
}
