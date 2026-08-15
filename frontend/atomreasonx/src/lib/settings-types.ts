// Settings centre types, extracted and trimmed from the Reasonix desktop
// lib/types.ts (https://github.com/esengine/DeepSeek-Reasonix, MIT) to the
// tabs AtomReasonX ships. Wire/event types unrelated to the settings centre
// are intentionally NOT ported.

// The four tabs with no AtomReasonX backend (bots, remote, diagnostics) and
// the desktop shortcut rebinding (shortcuts) are excluded from the port.
export type SettingsTab =
  | "general"
  | "models"
  | "providers" // legacy alias mapped to "models" at open time
  | "data-sources" // AtomReasonX-specific: data source providers & credentials
  | "mcp"
  | "skills"
  | "subagents"
  | "plugins"
  | "memory"
  | "hooks"
  | "permissions"
  | "sandbox"
  | "network"
  | "appearance"
  | "storage"
  | "updates";

export type ToolApprovalMode = "ask" | "auto" | "yolo";

/** Normalizes a stored tool approval mode ("full"/"full-access"/"bypass" → yolo). */
export function normalizeToolApprovalMode(mode: string): ToolApprovalMode {
  switch (mode) {
    case "auto":
      return "auto";
    case "yolo":
    case "full":
    case "full-access":
    case "bypass":
      return "yolo";
    default:
      return "ask";
  }
}

export interface ProviderModelOverrideView {
  model: string;
  reasoningProtocol: string;
  supportedEfforts: string[];
  defaultEffort: string;
  vision?: boolean | null;
  contextWindow?: number;
  maxOutputTokens?: number;
}

export interface ProviderView {
  name: string;
  builtIn: boolean;
  added: boolean;
  kind: string;
  baseUrl: string;
  chatUrl?: string; // legacy OpenAI chat endpoint override; preserved for old-config compatibility
  requestUrl?: string; // exact provider request URL written by the current settings UI
  models: string[];
  visionModels: string[]; // subset of models that accepts image input
  visionModelsConfigured: boolean; // true when an empty list is an explicit choice
  visionCapability?: "configurable" | "unsupported"; // backend authority; absent on older payloads
  modelsUrl: string; // optional override for model discovery; empty derives from baseUrl
  default: string;
  apiKeyEnv: string;
  headers?: Record<string, string> | null; // optional extra request headers for compatible gateways
  extraBody?: Record<string, unknown> | null; // optional extra top-level request body fields for compatible gateways
  authHeader?: boolean; // Anthropic-compatible: send Authorization: Bearer instead of x-api-key
  keySet: boolean; // the env var currently resolves to a value
  requiresKey?: boolean; // false for explicit no-auth providers
  configured?: boolean; // selectable: key is set or no key is required
  keySource?: string;
  keySourcePath?: string;
  balanceUrl: string; // optional wallet-balance endpoint; "" disables the readout
  contextWindow: number;
  reasoningProtocol: string; // auto|deepseek|glm|kimi-k3|openai|none; empty = auto/model registry
  thinking: string; // provider-specific thinking override: ""|enabled|disabled|adaptive
  webSearch?: boolean; // expose a provider-executed web search tool when supported
  serverWebSearchCapability?: boolean; // backend-verified provider capability; absent on older payloads
  supportedEfforts: string[]; // custom /effort levels; empty = use built-in default
  defaultEffort: string; // /effort level when user picks "auto" or unset; "" = supportedEfforts[0]
  modelOverrides?: ProviderModelOverrideView[] | null;
  recommendedUpgradeAvailable?: boolean;
  modelCatalogFingerprint?: string; // opaque compare-and-apply token for background model discovery
}

export interface ProviderModelCatalogUpdate {
  name: string;
  expectedFingerprint: string;
  models: string[];
  default: string;
  visionModels: string[];
}

export interface ProviderPresetView {
  id: string;
  label: string;
  description: string;
  keyEnv: string;
  providerNames: string[];
  models: string[];
  added: boolean;
  status?: "available" | "installed" | "installed_modified" | "name_conflict" | "similar_existing";
  statusProviderNames?: string[];
  keySet: boolean;
  requiresKey?: boolean;
  configured?: boolean;
  keySource?: string;
  keySourcePath?: string;
}

// BalanceInfo is the wallet-balance readout. `available` is false when the
// provider declares no balanceUrl or a fetch failed.
export interface BalanceInfo {
  available: boolean;
  display: string;
  detail?: string;
  complete?: boolean;
  rateDate?: string;
  approx?: boolean;
  currencies?: string[];
  primaryCurrency?: string;
  costDisplayCurrency?: string;
  multiCurrency?: boolean;
  err?: string;
}

export interface PermissionsView {
  mode: string; // "ask" | "allow" | "deny"
  allow: string[];
  ask: string[];
  deny: string[];
}

export interface SandboxView {
  bash: string; // "enforce" | "off"
  network: boolean;
  workspaceRoot: string;
  allowWrite: string[];
  effectiveWorkspaceRoot: string;
  effectiveWriteRoots: string[];
  shell: string; // "auto" | "bash" | "powershell" | "pwsh"
  effectiveShell?: string; // "bash" | "git-bash" | "powershell" | "pwsh"
}

export interface NetworkProxyView {
  type: string;
  server: string;
  port: number;
  username: string;
  password: string;
}

export interface NetworkView {
  proxyMode: string; // "auto" | "custom" | "off" (backend may still return legacy "env")
  proxyUrl: string;
  noProxy: string;
  proxy: NetworkProxyView;
}

export interface AgentView {
  temperature: number;
  maxSteps: number;
  plannerMaxSteps: number;
  maxSubagentDepth: number;
  maxSubagentConcurrency: number;
  maxParallelWriters: number;
  systemPrompt: string;
  reasoningLanguage: string; // "auto" | "zh" | "en"
  compactRatio?: number; // Advanced global default; older backends omit it.
  effectiveCompactRatio?: number; // Active local session after project overrides.
  compactRatioOverridden?: boolean;
}

export interface HookConfigView {
  event: string;
  match?: string;
  command: string;
  description?: string;
  timeout?: number;
  cwd?: string;
}

export interface HooksSettingsView {
  scope: string;
  path: string;
  projectRoot: string;
  trusted: boolean;
  hooks: HookConfigView[];
  events: string[];
}

export interface SettingsView {
  defaultModel: string;
  plannerModel: string;
  subagentModel: string;
  subagentEffort: string;
  autoPlan: string;
  providers: ProviderView[];
  officialProviders: ProviderView[];
  providerPresets: ProviderPresetView[];
  permissions: PermissionsView;
  sandbox: SandboxView;
  network: NetworkView;
  agent: AgentView;
  desktopLanguage: string; // "" | "en" | "zh"; empty = auto
  desktopCurrency?: string; // "" | "CNY" | "USD"; absent/empty = follow language
  desktopLayoutStyle: string; // "classic" | "workbench" | "creation"
  desktopTheme: string; // "auto" | "dark" | "light"
  desktopThemeStyle: string;
  desktopTerminalTheme: string; // "auto" follows app | "dark" | "light"
  closeBehavior: string; // "background" | "quit"
  displayMode: string; reasoningDisplayMode: string; reasoningDisplayModeExplicit?: boolean;
  statusBarStyle: string; // "icon" | "text"
  statusBarItems: string[]; // ordered visible status bar item ids
  defaultToolApprovalMode: ToolApprovalMode | string; // default for newly-created sessions
  checkUpdates: boolean; // check for new versions on startup
  updateChannel: string; // compatibility field; always "stable"
  telemetry: boolean; // anonymous launch ping + scrubbed next-launch native crash diagnostics
  metrics: boolean; // aggregate quality/lifecycle metrics (anonymous signal/bucket counts)
  configPath: string;
  shadowedByPath?: string; // workspace config that outranks configPath, when one exists
  providerKinds: string[]; // provider implementations the kernel registered (for the kind picker)
  autoApproveTools: boolean;
  bypass: boolean; // legacy JSON key for live YOLO/full-access tool auto-approval
  conversationWidth?: string; // "standard" | "full"; absent from older payloads
}

export interface DesktopStartupSettingsView {
  desktopLanguage: string; // "" | "en" | "zh"; empty = auto
  desktopLayoutStyle: string; // "classic" | "workbench"
  desktopTheme: string; // "auto" | "dark" | "light"
  desktopThemeStyle: string;
  desktopTerminalTheme: string; // "auto" follows app | "dark" | "light"
  displayMode: string; reasoningDisplayMode: string; reasoningDisplayModeExplicit?: boolean;
  statusBarStyle: string; // "icon" | "text"
  statusBarItems: string[]; // ordered visible status bar item ids
  checkUpdates: boolean; // check for new versions on startup
  updateChannel: string; // compatibility field; always "stable"
  conversationWidth?: string; // "standard" | "full"; absent from older payloads
  configWarnings?: string[]; configWarningsRevision?: number; // load recovery notices and async delivery barrier
  configPath?: string;
}

// Auto-updater payloads. UpdateInfo drives the update banner; UpdateProgress
// streams during download/install.
export interface UpdateInfo {
  available: boolean;
  current: string;
  latest: string;
  notes: string;
  channel: string;
  canSelfUpdate: boolean; // macOS true only for signed/notarized builds
  manualOnly?: boolean;
  manualReason?: string;
  installMode?: "portable" | "deb" | "manual" | string;
  requiresElevation?: boolean;
  downloaded: boolean;
  downloadUrl: string; // human-facing releases page (macOS path / fallback link)
  assetSize: number; // running platform's artifact size, for the progress bar
  err?: string; // set when the check itself failed (both endpoints down)
}

export interface UpdateDownloadResult {
  requestId: string;
  version: string;
  channel: string;
  path: string;
  size: number;
  sha256: string;
}

export interface UpdateProgress {
  requestId: string;
  version: string;
  channel: "stable" | "preview" | string;
  phase: "downloading" | "verifying" | "downloaded" | "authorizing" | "recovering" | "installing" | "relaunching" | "done" | "error";
  received: number;
  total: number;
  err?: string;
}

// ── Usage statistics (storage tab) ──────────────────────────────────────────

export interface UsageStatsRequest {
  range: string;
  from?: string;
  to?: string;
  source?: string;
}
export interface DailyTokenUsage {
  day: string; // "2006-01-02"
  total: number;
  byModel: Record<string, number>;
  byProvider: Record<string, number>;
  requests: number;
  turns: number;
  cacheHit: number;
  cacheMiss: number;
}

export interface ModelTokenUsage {
  model: string; // canonical "provider/model"
  provider: string;
  tokens: number;
  percent: number; // 0..100
}

export interface ProviderTokenUsage {
  provider: string;
  tokens: number;
  percent: number;
}

export interface UsageStatsRange {
  from: string;
  to: string;
  tokens: number;
  requests: number;
  turns: number;
  cacheHit: number;
  cacheMiss: number;
  activeDays: number;
  topModel: string;
  topProvider: string;
  daily: DailyTokenUsage[];
  models: ModelTokenUsage[];
  providers: ProviderTokenUsage[];
}

// ── MCP & Skills (CapabilitiesPanel) — ported from Reasonix lib/types.ts ────

export interface MCPToolView {
  name: string;
  description: string;
  readOnlyHint?: boolean;
  destructiveHint?: boolean;
  schemaError?: string;
}

export interface ServerView {
  name: string;
  transport: string;
  status: "connected" | "deferred" | "failed" | "initializing" | "disabled";
  startIntent?: "off" | "automatic" | string;
  runtimeState?: "idle" | "connecting" | "ready" | "issue" | string;
  availability?: string;
  enabled?: boolean;
  installed?: boolean;
  action?: "none" | "authenticate" | "authorize" | "retry" | string;
  source?: "project" | "user" | "plugin" | "builtin" | string;
  configSource?: string;
  builtIn?: boolean;
  configured?: boolean;
  autoStart: boolean;
  tier?: "background" | "eager" | string;
  command?: string;
  args?: string[];
  url?: string;
  envKeys?: string[];
  headerKeys?: string[];
  tools: number;
  toolCount?: number;
  prompts: number;
  resources: number;
  hasTools?: boolean;
  error?: string;
  toolList?: MCPToolView[];
  callTimeoutSeconds?: number;
  toolTimeoutSeconds?: Record<string, number>;
  requiresLaunchApproval?: boolean;
  authStatus?: "none" | "possible" | "required" | string;
  authUrl?: string;
  authConfigured?: boolean;
  managedByPlugin?: string;
}

export interface SkillView {
  name: string;
  description: string;
  scope: string;
  sourceDir?: string;
  runAs: string;
  enabled: boolean;
  plugin?: string;
  model?: string;
  effort?: string;
  allowedTools?: string[];
  readOnly?: boolean;
  color?: string;
  invocation?: string;
  invocationMode?: string;
  body?: string;
  configuredModel?: string;
  configuredEffort?: string;
}

export interface SkillRootSkillView {
  name: string;
  description: string;
  scope: string;
  runAs: string;
  plugin?: string;
  model?: string;
  effort?: string;
  allowedTools?: string[];
  color?: string;
  invocation?: string;
}

export interface SkillRootView {
  dir: string;
  scope: string;
  priority: number;
  status: string;
  enabled: boolean;
  configured: boolean;
  removable: boolean;
  skills: number;
  skillItems?: SkillRootSkillView[];
  warning?: string;
}

export interface CapabilitiesView {
  servers: ServerView[];
  skills: SkillView[];
  skillRoots: SkillRootView[];
  plugins: PluginView[];
  allowImplicitInvocation?: boolean;
}

export interface SkillsSettingsView {
  skills: SkillView[];
  skillRoots: SkillRootView[];
  allowImplicitInvocation?: boolean;
}

export interface SubagentProfileInput {
  name: string;
  description: string;
  systemPrompt: string;
  color?: string;
  model?: string;
  effort?: string;
  allowedTools?: string[];
  readOnly?: boolean;
  scope?: "project" | "global";
}

export interface PluginView {
  name: string;
  version?: string;
  description?: string;
  source?: string;
  root: string;
  manifestKind?: string;
  enabled: boolean;
  skills: number;
  commands?: number;
  hooks: number;
  mcpServers: number;
  agents?: number;
  compatibility?: "full" | "partial" | "none" | string;
  mappedCapabilities?: string[];
  skippedCapabilities?: PluginCompatibilityIssue[];
  skillDetails?: PluginSkillView[];
  agentDetails?: PluginAgentView[];
  commandDetails?: PluginCommandView[];
  hookDetails?: PluginHookView[];
  mcpServerDetails?: PluginMCPServerView[];
  warnings?: string[];
  error?: string;
}

export interface PluginCompatibilityIssue {
  capability: string;
  path?: string;
  reason: string;
}

export interface PluginAgentView {
  name: string;
  description?: string;
  path?: string;
  invocation?: string;
  model?: string;
  allowedTools?: string[];
}

export interface PluginSkillView {
  name: string;
  description?: string;
  path?: string;
  invocation?: string;
  runAs?: string;
}

export interface PluginCommandView {
  name: string;
  description?: string;
  argHint?: string;
  path?: string;
  invocation?: string;
  shadowed?: boolean;
  shadowedByPlugin?: string;
}

export interface PluginHookView {
  event: string;
  match?: string;
  command?: string;
  contextFile?: string;
  description?: string;
}

export interface PluginMCPServerView {
  name: string;
  displayName?: string;
  description?: string;
  transport?: string;
  command?: string;
  url?: string;
  autoStart?: boolean;
}

export interface PluginInstallOptions {
  dryRun?: boolean;
  link?: boolean;
  replace?: boolean;
  name?: string;
}

export interface MCPServerInput {
  name: string;
  transport: string; // stdio | http | sse
  command: string;
  args: string[];
  url: string;
  env?: Record<string, string> | null;
  headers?: Record<string, string> | null;
  autoStart?: boolean | null;
  callTimeoutSeconds?: number | null;
  toolTimeoutSeconds?: Record<string, number> | null;
}

export interface MCPInstallResult {
  name: string;
  state: "ready" | "action_required" | "issue";
  toolCount: number;
  action: "none" | "authenticate" | "authorize" | "retry";
  message: string;
}

export interface MCPMarketplaceEntry {
  name: string;
  suggestedName: string;
  title?: string;
  description?: string;
  version?: string;
  repositoryUrl?: string;
  installable: boolean;
  unavailableReason?: string;
  transport?: "stdio" | "http" | "sse" | string;
  command?: string;
  args: string[];
  url?: string;
}

export interface MCPMarketplaceView {
  servers: MCPMarketplaceEntry[];
  cached: boolean;
  warning?: string;
}

// ── Tab management (topbar surface) ─────────────────────────────────────────

export interface TabMeta {
  id: string;
  tabType?: "session" | "file";
  active?: boolean;
  cwd?: string;
  eventChannel?: string;
  scope: string;
  workspaceRoot: string;
  workspaceName: string;
  workspacePath?: string;
  gitBranch?: string;
  isolatedWorktree?: boolean;
  topicId: string;
  topicTitle: string;
  sessionPath?: string;
  sessionRevision?: number;
  sessionDigest?: string;
  sessionGeneration?: number;
  readOnly?: boolean;
  filePath?: string;
  projectColor?: string;
  label: string;
  ready: boolean;
}
// ── Memory panel payloads (ported from Reasonix lib/types.ts) ───────────────

export interface MemoryDoc {
  path: string;
  scope: string; // "user" | "ancestor" | "project" | "local"
  directory?: string;
  body: string;
  imports: Array<{ path: string; sourcePath: string }>;
  depth: number;
  order: number;
  precedence: number;
}

export interface InstructionDiagnostic {
  code: string;
  path: string;
  sourcePath?: string;
  line?: number;
  message: string;
}

export interface MemoryFact {
  id?: string;
  revision?: number;
  createdAt?: string;
  updatedAt?: string;
  name: string;
  title?: string;
  description: string;
  type: string; // "user" | "feedback" | "project" | "reference"
  scope: string; // "project" | "global"
  body: string;
  freshness: string; // "fresh" | "current" | "stale"
}

export interface MemoryConflict {
  key: string;
  projectId: string;
  projectName: string;
  globalId: string;
  globalName: string;
  resolution: "project_over_global";
}

export interface MemoryRecallHit {
  id: string;
  revision: number;
  name: string;
  title?: string;
  type: string;
  scope: string;
  score: number;
  freshness: string;
  reason: string;
  snippet: string;
}

export interface MemoryRecallTrace {
  query: string;
  hits: MemoryRecallHit[];
  omitted: number;
  charBudget: number;
  usedChars: number;
  suppressed?: string;
}

export interface MemoryArchive extends MemoryFact {
  path: string;
  archivedAt?: string;
}

export interface MemoryScope {
  scope: string; // "user" | "project" | "local"
  path: string;
}

export interface MemorySuggestion {
  id: string;
  name: string;
  title: string;
  description: string;
  type: string;
  scope: string; // "project" | "global"
  body: string;
  reason: string;
  evidence: string[];
}

export interface SkillSuggestion {
  id: string;
  name: string;
  description: string;
  scope: string;
  body: string;
  reason: string;
  evidence: string[];
}

export interface MemorySuggestionsView {
  memories: MemorySuggestion[];
  skills: SkillSuggestion[];
  generatedAt: string;
  available: boolean;
  source: string;
}

export interface MemoryView {
  docs: MemoryDoc[];
  facts: MemoryFact[];
  archives: MemoryArchive[];
  scopes: MemoryScope[];
  instructionDiagnostics: InstructionDiagnostic[];
  conflicts: MemoryConflict[];
  lastRecall: MemoryRecallTrace;
  storeDir: string;
  storeGlobalDir?: string;
  available: boolean;
}

// ── Remote hosts (port of the Reasonix remote module view shapes) ────────────

export type RemoteConnState =
  | "connecting"
  | "connected"
  | "reconnecting"
  | "degraded"
  | "pending_hostkey"
  | "pending_secret"
  | "stopped";

export interface RemoteHostView {
  id: string;
  label: string;
  host: string;
  port: number;
  user: string;
  identityFile: string;
  proxyJump: string;
  defaultWorkspace: string;
  serveInstall: string;
  useSSHConfig: boolean;
  passwordSet?: boolean;
  keyPassphraseSet?: boolean;
}

export interface RemoteHostInput {
  label: string;
  host: string;
  port: number;
  user: string;
  identityFile: string;
  proxyJump: string;
  defaultWorkspace: string;
  serveInstall: string;
  useSSHConfig: boolean;
  password?: string;
  keyPassphrase?: string;
  clearPassword?: boolean;
  clearPassphrase?: boolean;
  preserveExistingSettings?: boolean;
}

export interface RemoteFingerprintView {
  hostId: string;
  address: string;
  keyType: string;
  sha256: string;
}

export interface RemoteSecretPromptView {
  promptId: string;
  hostId: string;
  host: string;
  kind: "password" | "passphrase";
  identity?: string;
}

export interface RemoteKnownHostLocation {
  path: string;
  line: number;
}

export interface RemoteConnectionErrorDetails {
  code: "connection_failed" | "auth_failed" | "host_key_rejected" | "host_key_mismatch";
  presentedSha256?: string;
  knownHostRecords?: RemoteKnownHostLocation[];
}

export interface RemoteConnectionStatus {
  hostId: string;
  state: RemoteConnState;
  error?: string;
  errorDetails?: RemoteConnectionErrorDetails;
  fingerprint?: RemoteFingerprintView;
  secretPrompt?: RemoteSecretPromptView;
  attempt?: number;
}

/** Path-free summary of files left behind by the removed Remote Workbench. */
export interface RemoteLegacyWorkbenchData {
  mirrorCount: number;
  mirrorBytes: number;
  trustFile: boolean;
}

export type RemoteServerState =
  | "starting"
  | "detect"
  | "install"
  | "waiting_lock"
  | "launch"
  | "health_check"
  | "ready"
  | "error"
  | "stopped";

export interface RemoteForwardView {
  id: string;
  hostId: string;
  localPort: number;
  remoteHost: string;
  remotePort: number;
  label: string;
  state: string;
  error?: string;
}

export interface RemoteServerView {
  hostId: string;
  workspace: string;
  state: RemoteServerState;
  message?: string;
  localUrl?: string;
  error?: string;
}