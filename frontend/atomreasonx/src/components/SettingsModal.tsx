import React from "react";
import {
  Box,
  Database,
  Palette,
  Search,
  Settings2,
  X,
  type LucideIcon,
} from "lucide-react";
import type { WorkbenchCommandDispatcher } from "../adapters/command-adapter";
import {
  isModelCommandResult,
  isModelListArtifact,
  modelCommandErrorMessage,
  submitModelListRefresh,
} from "../adapters/chat-adapter";
import {
  normalizeReadonlyRunOutputDir,
  type ReadonlyRunRecentOutputDir,
  type ReadonlyRunOperatorConfig,
} from "../adapters/readonly-run-operator-config";
import type {
  AtomReasonXProviderStatus,
  AtomReasonXSettingsState,
  AtomReasonXSourceSettingsState,
  ProviderConfigStatusEntry,
  SourceConfigStatusEntry,
} from "../contracts/types";
import {
  contextWindowForProvider,
  defaultModelForProvider,
  registryForProvider,
  resolveProviderEndpoint,
} from "../lib/providerEndpoints";
import { formatTokensCompact } from "../lib/telemetry";
import {
  applyTheme,
  getResolvedTheme,
  getTheme,
  getThemeStyle,
  readThemePreference,
  THEME_STYLES,
  THEME_STYLE_DESCRIPTIONS,
  THEME_STYLE_LABELS,
  THEME_STYLE_SWATCHES,
  type Theme,
  type ThemeStyle,
} from "../lib/theme";
import { buildBackupPayload, downloadBackup } from "../lib/backup";
import { useSessions } from "../stores/session-store";

export const SOURCE_PROVIDER_CONNECTION_PROBE_SCHEMA_VERSION = "v35.source_provider_connection_probe.v1";
export const DEFAULT_MATERIALS_PROJECT_PROBE_FORMULA = "CsPbI3";

export const buildSourceSettingsCommandPayload = (
  source: SourceConfigStatusEntry,
  extra: Record<string, unknown> = {},
): Record<string, unknown> => ({
  ...extra,
  provider: source.provider_id,
  provider_scope: "source",
});

export const withoutSourceProviderProbeSecrets = (
  extra: Record<string, unknown>,
): Record<string, unknown> => {
  const formula = typeof extra.formula === "string" ? extra.formula.trim() : "";
  return formula ? { formula } : {};
};

export const buildSourceProviderTestConnectionPayload = (
  source: SourceConfigStatusEntry,
  extra: Record<string, unknown> = {},
): Record<string, unknown> => {
  if (source.provider_id !== "materials_project") {
    return buildSourceSettingsCommandPayload(source);
  }
  return buildSourceSettingsCommandPayload(source, {
    probe_contract: SOURCE_PROVIDER_CONNECTION_PROBE_SCHEMA_VERSION,
    formula: DEFAULT_MATERIALS_PROJECT_PROBE_FORMULA,
    ...withoutSourceProviderProbeSecrets(extra),
  });
};

export const submitSourceSettingsCommand = (
  commandDispatcher: WorkbenchCommandDispatcher,
  actionType: string,
  source: SourceConfigStatusEntry,
  extra: Record<string, unknown> = {},
): Promise<unknown> => commandDispatcher.submitAction(
  actionType,
  buildSourceSettingsCommandPayload(source, extra),
);

export const submitSourceProviderTestConnectionCommand = (
  commandDispatcher: WorkbenchCommandDispatcher,
  source: SourceConfigStatusEntry,
  extra: Record<string, unknown> = {},
): Promise<unknown> => commandDispatcher.submitAction(
  "test_connection",
  buildSourceProviderTestConnectionPayload(source, extra),
);

export const buildModelSettingsCommandPayload = (
  model: ProviderConfigStatusEntry,
  extra: Record<string, unknown> = {},
): Record<string, unknown> => ({
  ...extra,
  provider: model.provider,
  provider_scope: "model",
});

export const buildModelConfigWritePayload = (
  model: ProviderConfigStatusEntry,
  config: Record<string, unknown>,
): Record<string, unknown> => buildModelSettingsCommandPayload(model, { config });

export const submitModelConfigWriteCommand = (
  commandDispatcher: WorkbenchCommandDispatcher,
  model: ProviderConfigStatusEntry,
  config: Record<string, unknown>,
): Promise<unknown> => commandDispatcher.submitAction(
  "config_write",
  buildModelConfigWritePayload(model, config),
);

export const submitModelKeyRotateCommand = (
  commandDispatcher: WorkbenchCommandDispatcher,
  model: ProviderConfigStatusEntry,
  apiKey: string,
): Promise<unknown> => commandDispatcher.submitAction(
  "key_rotate",
  buildModelSettingsCommandPayload(model, { api_key: apiKey }),
);

export const submitModelTestConnectionCommand = (
  commandDispatcher: WorkbenchCommandDispatcher,
  model: ProviderConfigStatusEntry,
  extra: Record<string, unknown> = {},
): Promise<unknown> => commandDispatcher.submitAction(
  "test_connection",
  buildModelSettingsCommandPayload(model, extra),
);

export const submitModelKeyRemoveCommand = (
  commandDispatcher: WorkbenchCommandDispatcher,
  model: ProviderConfigStatusEntry,
): Promise<unknown> => commandDispatcher.submitAction(
  "key_remove",
  buildModelSettingsCommandPayload(model),
);

export interface ModelConfigDraft {
  enabled: boolean;
  base_url: string;
  default_model: string;
}

type SettingsTabId = "general" | "models" | "data-sources" | "appearance";

interface SettingsTab {
  id: SettingsTabId;
  label: string;
  group: "preferences" | "connections" | "application";
  icon: LucideIcon;
  meta?: string;
  searchTerms?: string;
}

const TAB_GROUPS: { id: SettingsTab["group"]; label: string }[] = [
  { id: "preferences", label: "Preferences" },
  { id: "connections", label: "Connections" },
  { id: "application", label: "Application" },
];

const requestedTabIds = (categories: string[]): SettingsTabId[] => {
  const requested = new Set(categories);
  const tabs: SettingsTabId[] = [];
  if (requested.size === 0 || requested.has("General")) tabs.push("general");
  if (requested.has("Models")) tabs.push("models");
  if (requested.has("Data Sources")) tabs.push("data-sources");
  tabs.push("appearance");
  return tabs;
};

const PAGE_DESCRIPTIONS: Partial<Record<SettingsTabId, string>> = {
  general: "Workspace and run behaviour for the AtomReasonX workbench.",
  models: "Configure model providers, endpoints, default models and API keys.",
  "data-sources": "Manage data source providers, credentials and connection checks.",
  appearance: "Theme direction and light/dark mode for the whole workbench.",
};

export const SettingsModal: React.FC<{
  categories: string[];
  sourceSettings?: AtomReasonXSourceSettingsState;
  modelSettings?: AtomReasonXSettingsState;
  providerRegistry?: AtomReasonXProviderStatus;
  readonlyRunConfig?: ReadonlyRunOperatorConfig;
  readonlyRecentOutputDirs?: ReadonlyRunRecentOutputDir[];
  onApplyReadonlyRunOutputDir?: (outputDir: string | null) => void;
  commandDispatcher?: WorkbenchCommandDispatcher;
  onClose?: () => void;
}> = ({
  categories,
  sourceSettings,
  modelSettings,
  providerRegistry,
  readonlyRunConfig,
  readonlyRecentOutputDirs = [],
  onApplyReadonlyRunOutputDir,
  commandDispatcher,
  onClose,
}) => {
  const [theme, setTheme] = React.useState<Theme>(() => getTheme());
  const [themeStyle, setThemeStyle] = React.useState<ThemeStyle>(() => getThemeStyle());
  const [selected, setSelected] = React.useState<SettingsTabId>(() => requestedTabIds(categories)[0]);
  const [query, setQuery] = React.useState("");
  const [sourceKeys, setSourceKeys] = React.useState<Record<string, string>>({});
  const [modelKeys, setModelKeys] = React.useState<Record<string, string>>({});
  const [readonlyOutputDirDraft, setReadonlyOutputDirDraft] = React.useState(
    readonlyRunConfig?.outputDir ?? "",
  );
  const readonlyOutputDir = readonlyRunConfig?.outputDir ?? null;
  const normalizedReadonlyOutputDirDraft = normalizeReadonlyRunOutputDir(readonlyOutputDirDraft);
  const readonlyOutputDirChanged = normalizedReadonlyOutputDirDraft !== readonlyOutputDir;
  const canConfigureReadonlyRun = Boolean(onApplyReadonlyRunOutputDir);

  const tabs: SettingsTab[] = React.useMemo(() => {
    const ids = requestedTabIds(categories);
    const providers = modelSettings?.providers ?? [];
    const sources = sourceSettings?.sources ?? [];
    const keyMissing = providers.filter((item) => item.requires_api_key && !item.has_api_key).length;
    const keyConfigured = providers.filter((item) => item.has_api_key).length;
    const modelsMeta = providers.length === 0
      ? "no providers"
      : keyMissing > 0
        ? `${keyConfigured} key · ${keyMissing} missing`
        : `${keyConfigured} key`;
    const all: SettingsTab[] = [
      { id: "general", label: "General", group: "preferences", icon: Settings2 },
      { id: "models", label: "Models", group: "preferences", icon: Box, meta: modelsMeta, searchTerms: "model provider base url api key default model" },
      { id: "data-sources", label: "Data Sources", group: "connections", icon: Database, meta: `${sources.length} sources`, searchTerms: "source provider api key materials project readonly run output directory" },
      { id: "appearance", label: "Appearance", group: "application", icon: Palette, searchTerms: "theme dark light auto graphite aurora slate carbon nocturne amber" },
    ];
    return all.filter((tab) => ids.includes(tab.id));
  }, [categories, modelSettings, sourceSettings]);

  React.useEffect(() => {
    setReadonlyOutputDirDraft(readonlyRunConfig?.outputDir ?? "");
  }, [readonlyRunConfig?.outputDir]);

  const filteredTabs = React.useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase();
    if (!normalized) return tabs;
    return tabs.filter((tab) => (
      `${tab.label} ${tab.meta ?? ""} ${tab.searchTerms ?? ""}`.toLocaleLowerCase().includes(normalized)
    ));
  }, [query, tabs]);

  const selectedTab = tabs.find((tab) => tab.id === selected) ?? tabs[0];
  const selectedTabId = selectedTab?.id ?? "general";

  const applyThemePreference = (nextTheme: Theme, nextStyle: ThemeStyle) => {
    setTheme(nextTheme);
    setThemeStyle(nextStyle);
    applyTheme(nextTheme, nextStyle);
  };

  return (
    <div
      className="settings-modal-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose?.();
      }}
    >
      <div className="management-modal settings-modal">
        <header className="management-modal__head settings-modal__head">
          <div className="management-modal__title">Settings</div>
          <div className="management-modal__actions">
            <button type="button" className="modal-close-btn" onClick={onClose} aria-label="Close settings">
              <X size={18} aria-hidden="true" />
            </button>
          </div>
        </header>

        <div className="settings-center">
          <nav className="settings-center__nav" aria-label="Settings">
            <label className="settings-center__search">
              <Search size={15} aria-hidden="true" />
              <input
                value={query}
                onChange={(event) => setQuery(event.currentTarget.value)}
                placeholder="Search settings"
                aria-label="Search settings"
              />
              {query && (
                <button type="button" onClick={() => setQuery("")} aria-label="Clear settings search">
                  <X size={14} aria-hidden="true" />
                </button>
              )}
            </label>
            <div className="settings-center__navgroups">
              {TAB_GROUPS.map((group) => {
                const groupTabs = filteredTabs.filter((tab) => tab.group === group.id);
                if (groupTabs.length === 0) return null;
                return (
                  <section className="settings-center__navgroup" key={group.id}>
                    <div className="settings-center__navgroup-label">{group.label}</div>
                    <div className="settings-center__navitems">
                      {groupTabs.map((tab) => {
                        const Icon = tab.icon;
                        const active = selectedTabId === tab.id;
                        return (
                          <button
                            key={tab.id}
                            type="button"
                            className={`settings-center__navitem${active ? " settings-center__navitem--active" : ""}`}
                            aria-current={active ? "page" : undefined}
                            onClick={() => setSelected(tab.id)}
                          >
                            <span className="settings-center__navitem-main">
                              <Icon size={17} strokeWidth={1.8} aria-hidden="true" />
                              <span>{tab.label}</span>
                            </span>
                            {tab.meta && (active || query.trim()) && <small>{tab.meta}</small>}
                          </button>
                        );
                      })}
                    </div>
                  </section>
                );
              })}
              {filteredTabs.length === 0 && (
                <div className="settings-center__navempty" role="status">No settings match “{query}”.</div>
              )}
            </div>
          </nav>

          <main className="settings-center__content">
            {selectedTabId === "general" && (
              <GeneralPage
                readonlyRunConfig={readonlyRunConfig}
                readonlyRecentOutputDirs={readonlyRecentOutputDirs}
                readonlyOutputDirDraft={readonlyOutputDirDraft}
                readonlyOutputDirChanged={readonlyOutputDirChanged}
                canConfigureReadonlyRun={canConfigureReadonlyRun}
                onReadonlyOutputDirDraftChange={setReadonlyOutputDirDraft}
                onApplyReadonlyRunOutputDir={onApplyReadonlyRunOutputDir}
              />
            )}
            {selectedTabId === "models" && (
              <ModelsPage
                modelSettings={modelSettings}
                providerRegistry={providerRegistry}
                commandDispatcher={commandDispatcher}
                modelKeys={modelKeys}
                onModelKeysChange={setModelKeys}
              />
            )}
            {selectedTabId === "data-sources" && (
              <DataSourcesPage
                sourceSettings={sourceSettings}
                commandDispatcher={commandDispatcher}
                sourceKeys={sourceKeys}
                onSourceKeysChange={setSourceKeys}
              />
            )}
            {selectedTabId === "appearance" && (
              <AppearancePage
                theme={theme}
                themeStyle={themeStyle}
                onApplyTheme={applyThemePreference}
              />
            )}
          </main>
        </div>
      </div>
    </div>
  );
};

const PageShell: React.FC<{
  tabId: SettingsTabId;
  title: string;
  description?: string;
  children: React.ReactNode;
}> = ({ tabId, title, description, children }) => (
  <div className={`settings-page settings-page--form settings-page--${tabId}`}>
    <div className="settings-page__header">
      <h2 className="settings-page__title">{title}</h2>
      {description && <p className="settings-page__desc">{description}</p>}
    </div>
    {children}
  </div>
);

/* ── General: readonly run output directory ─────────────────────────────────── */

const GeneralPage: React.FC<{
  readonlyRunConfig?: ReadonlyRunOperatorConfig;
  readonlyRecentOutputDirs: ReadonlyRunRecentOutputDir[];
  readonlyOutputDirDraft: string;
  readonlyOutputDirChanged: boolean;
  canConfigureReadonlyRun: boolean;
  onReadonlyOutputDirDraftChange: (value: string) => void;
  onApplyReadonlyRunOutputDir?: (outputDir: string | null) => void;
}> = ({
  readonlyRunConfig,
  readonlyRecentOutputDirs,
  readonlyOutputDirDraft,
  readonlyOutputDirChanged,
  canConfigureReadonlyRun,
  onReadonlyOutputDirDraftChange,
  onApplyReadonlyRunOutputDir,
}) => {
  const modeLabel = readonlyRunConfig?.readOnly ? "readonly_run" : "fixture";
  const sessions = useSessions();
  return (
    <PageShell tabId="general" title="General" description={PAGE_DESCRIPTIONS.general}>
      {readonlyRunConfig && (
        <section className="settings-section" aria-label="Readonly run output directory">
          <div className="settings-section__head">
            <div>
              <div className="settings-section__title">Readonly Run</div>
              <div className="settings-section__desc">
                Workbench reads a readonly run workspace from this output directory. Empty uses the bundled demo fixture.
              </div>
            </div>
            <div className="settings-section__actions">
              <span className="settings-row__status">{modeLabel}</span>
            </div>
          </div>
          <div className="settings-section__body">
            <div className="settings-field">
              <div className="settings-field__copy">
                <div className="settings-field__label">Output directory</div>
                <div className="settings-field__hint">Absolute path produced by a previous SpiroSearch run.</div>
              </div>
              <div className="settings-field__control">
                <input
                  aria-label="Readonly run output directory"
                  type="text"
                  value={readonlyOutputDirDraft}
                  placeholder="D:\\path\\to\\run\\output"
                  disabled={!canConfigureReadonlyRun}
                  onChange={(event) => onReadonlyOutputDirDraftChange(event.currentTarget.value)}
                />
                <select
                  aria-label="Recent readonly run output directories"
                  value=""
                  disabled={!canConfigureReadonlyRun || readonlyRecentOutputDirs.length === 0}
                  onChange={(event) => {
                    if (event.currentTarget.value) {
                      onReadonlyOutputDirDraftChange(event.currentTarget.value);
                    }
                  }}
                >
                  <option value="">Recent</option>
                  {readonlyRecentOutputDirs.map((item) => (
                    <option key={`${item.source}:${item.outputDir}`} value={item.outputDir}>
                      {item.label}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="btn btn--primary"
                  disabled={!canConfigureReadonlyRun || !readonlyOutputDirChanged}
                  onClick={() => onApplyReadonlyRunOutputDir?.(normalizeReadonlyRunOutputDir(readonlyOutputDirDraft))}
                >
                  Apply
                </button>
                <button
                  type="button"
                  className="btn"
                  disabled={!canConfigureReadonlyRun || (!readonlyRunConfig.outputDir && readonlyOutputDirDraft.trim() === "")}
                  onClick={() => {
                    onReadonlyOutputDirDraftChange("");
                    onApplyReadonlyRunOutputDir?.(null);
                  }}
                >
                  Clear
                </button>
              </div>
            </div>
          </div>
        </section>
      )}
      <section className="settings-section" aria-label="Backup and data">
        <div className="settings-section__head">
          <div>
            <div className="settings-section__title">Data & backup</div>
            <div className="settings-section__desc">
              Export local data (sessions and knowledge imports) as a portable JSON backup.
            </div>
          </div>
        </div>
        <div className="settings-section__body">
          <div className="settings-field">
            <div className="settings-field__copy">
              <div className="settings-field__label">Local backup</div>
              <div className="settings-field__hint">{sessions.length} sessions · JSON download</div>
            </div>
            <div className="settings-field__control">
              <button
                type="button"
                className="btn"
                onClick={() => downloadBackup(buildBackupPayload(sessions))}
              >
                Export backup
              </button>
            </div>
          </div>
        </div>
      </section>
    </PageShell>
  );
};

interface ModelLiveProbe {
  schema_version: string;
  provider: string;
  provider_scope: string;
  status: string;
  validation_state: string;
  error_message?: string | null;
}

const MODEL_PROBE_STATUS_LABELS: Record<string, string> = {
  validated: "Connected",
  auth_failed: "Auth failed (401/403)",
  endpoint_not_found: "Endpoint not found (404/405)",
  timeout: "Timeout",
  rate_limited: "Rate limited",
  http_error: "HTTP error",
  provider_error: "Provider error",
};

const extractModelProbeStatus = (
  result: { output_artifacts: unknown[] },
): { status: string; message: string } | null => {
  const effect = result.output_artifacts.find(
    (artifact) => typeof artifact === "object" && artifact !== null
      && (artifact as { kind?: unknown }).kind === "config_command_effect",
  ) as { provider_probe?: unknown } | undefined;
  const probe = effect?.provider_probe as ModelLiveProbe | undefined;
  if (!probe || probe.schema_version !== "v35.model_live_probe.v1") return null;
  return {
    status: probe.status,
    message: probe.error_message ?? "",
  };
};

/* ── Data Sources ────────────────────────────────────────────────────────────── */

const DataSourcesPage: React.FC<{
  sourceSettings?: AtomReasonXSourceSettingsState;
  commandDispatcher?: WorkbenchCommandDispatcher;
  sourceKeys: Record<string, string>;
  onSourceKeysChange: (keys: Record<string, string>) => void;
}> = ({ sourceSettings, commandDispatcher, sourceKeys, onSourceKeysChange }) => {
  const sources = sourceSettings?.sources ?? [];
  return (
    <PageShell tabId="data-sources" title="Data Sources" description={PAGE_DESCRIPTIONS["data-sources"]}>
      <section className="settings-section" aria-label="Data source providers">
        <div className="settings-section__head">
          <div>
            <div className="settings-section__title">Providers</div>
            <div className="settings-section__desc">
              Credentials and connectivity for each data source provider. Keys are stored by the backend, never in the browser.
            </div>
          </div>
        </div>
        <div className="settings-section__body">
          {sources.length === 0 ? (
            <div className="empty-state">No data source providers configured.</div>
          ) : (
            <div className="settings-row-list">
              {sources.map((source) => (
                <div key={source.provider_id} className="settings-row">
                  <div className="settings-row__meta">
                    <strong>{source.provider_id}</strong>
                    <span className={`settings-row__status ${source.validation_state === "missing" ? "settings-row__status--missing" : "settings-row__status--ok"}`}>
                      {source.validation_state}
                    </span>
                    <span className="settings-row__status">{source.key_requirement}</span>
                    {source.data_library_path ? <code>{source.data_library_path}</code> : null}
                  </div>
                  <div className="settings-row__actions">
                    {source.requires_api_key && (
                      <>
                        <input
                          aria-label={`${source.provider_id} API key`}
                          type="password"
                          placeholder="API key"
                          value={sourceKeys[source.provider_id] ?? ""}
                          onChange={(event) => onSourceKeysChange({
                            ...sourceKeys,
                            [source.provider_id]: event.currentTarget.value,
                          })}
                        />
                        <button
                          type="button"
                          className="btn btn--primary"
                          disabled={!commandDispatcher || !(sourceKeys[source.provider_id] ?? "").trim()}
                          onClick={() => {
                            if (commandDispatcher) {
                              void submitSourceSettingsCommand(commandDispatcher, "key_rotate", source, {
                                api_key: sourceKeys[source.provider_id] ?? "",
                              });
                            }
                            onSourceKeysChange({ ...sourceKeys, [source.provider_id]: "" });
                          }}
                        >
                          Set
                        </button>
                        <button
                          type="button"
                          className="btn"
                          disabled={!commandDispatcher || !source.has_api_key}
                          onClick={() => {
                            if (commandDispatcher) {
                              void submitSourceSettingsCommand(commandDispatcher, "key_remove", source);
                            }
                          }}
                        >
                          Remove
                        </button>
                      </>
                    )}
                    <button
                      type="button"
                      className="btn"
                      disabled={!commandDispatcher}
                      onClick={() => {
                        if (commandDispatcher) {
                          void submitSourceProviderTestConnectionCommand(commandDispatcher, source);
                        }
                      }}
                    >
                      Test
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </PageShell>
  );
};

/* ── Models ─────────────────────────────────────────────────────────────────── */

const ModelsPage: React.FC<{
  modelSettings?: AtomReasonXSettingsState;
  providerRegistry?: AtomReasonXProviderStatus;
  commandDispatcher?: WorkbenchCommandDispatcher;
  modelKeys: Record<string, string>;
  onModelKeysChange: (keys: Record<string, string>) => void;
}> = ({
  modelSettings,
  providerRegistry,
  commandDispatcher,
  modelKeys,
  onModelKeysChange,
}) => {
  const providers = modelSettings?.providers ?? [];
  const registry = providerRegistry?.providers ?? [];
  const [fetchedModels, setFetchedModels] = React.useState<Record<string, string[]>>({});
  const [fetchingProvider, setFetchingProvider] = React.useState<string | null>(null);
  const [fetchStatus, setFetchStatus] = React.useState<string | null>(null);
  const [testingProvider, setTestingProvider] = React.useState<string | null>(null);
  const [testResults, setTestResults] = React.useState<Record<string, { status: string; message: string }>>({});

  const testConnection = React.useCallback(async (model: ProviderConfigStatusEntry) => {
    if (!commandDispatcher) return;
    setTestingProvider(model.provider);
    try {
      const result = await submitModelTestConnectionCommand(commandDispatcher, model, { live_probe: true });
      if (isModelCommandResult(result) && result.status === "accepted") {
        const probe = extractModelProbeStatus(result);
        setTestResults((previous) => ({
          ...previous,
          [model.provider]: probe ?? { status: "validated", message: "" },
        }));
      } else if (isModelCommandResult(result)) {
        setTestResults((previous) => ({
          ...previous,
          [model.provider]: { status: result.reason_code, message: result.message },
        }));
      }
    } catch (error) {
      setTestResults((previous) => ({
        ...previous,
        [model.provider]: {
          status: "provider_error",
          message: error instanceof Error ? error.message : String(error),
        },
      }));
    } finally {
      setTestingProvider(null);
    }
  }, [commandDispatcher]);

  const fetchModels = React.useCallback(async (providerId: string) => {
    if (!commandDispatcher) return;
    setFetchingProvider(providerId);
    setFetchStatus(null);
    try {
      const result = await submitModelListRefresh(commandDispatcher, providerId);
      if (isModelCommandResult(result) && result.status === "accepted") {
        const artifact = result.output_artifacts.find(isModelListArtifact);
        if (artifact) {
          setFetchedModels((previous) => ({ ...previous, [providerId]: artifact.models }));
          setFetchStatus(`Fetched ${artifact.models.length} models from the provider.`);
        } else {
          setFetchStatus("The provider returned no model list.");
        }
      } else {
        setFetchStatus(
          isModelCommandResult(result)
            ? modelCommandErrorMessage(result)
            : "The model command did not return a result.",
        );
      }
    } catch (error) {
      setFetchStatus(error instanceof Error ? error.message : String(error));
    } finally {
      setFetchingProvider(null);
    }
  }, [commandDispatcher]);

  return (
    <PageShell tabId="models" title="Models" description={PAGE_DESCRIPTIONS.models}>
      {!commandDispatcher && (
        <p className="settings-inline-hint" style={{ color: "var(--warn)" }}>
          Model configuration backend unavailable: controls are disabled until a
          command dispatcher is wired.
        </p>
      )}
      <section className="settings-section" aria-label="Model providers">
        <div className="settings-section__head">
          <div>
            <div className="settings-section__title">Providers</div>
            <div className="settings-section__desc">
              Official providers ship with built-in endpoints and model lists — you only supply the API key.
            </div>
          </div>
        </div>
        <div className="settings-section__body">
          {providers.length === 0 ? (
            <div className="empty-state">No model providers configured.</div>
          ) : (
            <div className="provider-access-grid">
              {providers.map((model) => {
                const registryEntry = registryForProvider(model.provider, registry);
                const endpoint = resolveProviderEndpoint(registryEntry, model);
                const defaultModels = registryEntry?.default_models ?? [];
                const defaultModel = defaultModelForProvider(registryEntry);
                const effectiveBaseUrl = model.base_url || endpoint.url || "";
                const effectiveDefaultModel = model.default_model || defaultModel || "";
                const fetched = fetchedModels[model.provider];
                const modelList = fetched ?? defaultModels;
                const isFetching = fetchingProvider === model.provider;
                const isTesting = testingProvider === model.provider;
                const contextWindow = contextWindowForProvider(model.provider)
                  ?? registryEntry?.context_window_tokens
                  ?? null;
                const testResult = testResults[model.provider];
                const keyLabel = model.has_api_key
                  ? `key ${model.key_fingerprint ?? ""}`
                  : model.requires_api_key
                    ? "key missing"
                    : "no key needed";
                return (
                  <article className="provider-access-card" key={model.provider}>
                    <div className="provider-access-card__head">
                      <div className="provider-access-card__identity">
                        <div className="provider-access-card__title">
                          {model.brand ?? model.provider}
                          {model.brand && model.brand !== model.provider ? (
                            <span style={{ color: "var(--fg-dim)", fontSize: "12px", fontWeight: 550 }}>{model.provider}</span>
                          ) : null}
                          <span className={`badge ${endpoint.builtin ? "badge--project" : "badge--neutral"}`}>
                            {endpoint.builtin ? "Built-in" : "Custom"}
                          </span>
                          <span className={`badge ${model.has_api_key ? "badge--project" : model.requires_api_key ? "badge--feedback" : "badge--neutral"}`}>
                            {keyLabel}
                          </span>
                        </div>
                      </div>
                      <div className="provider-access-card__actions">
                        <button
                          type="button"
                          className="btn btn--small"
                          disabled={!commandDispatcher || !model.has_api_key || isFetching}
                          onClick={() => void fetchModels(model.provider)}
                        >
                          {isFetching ? "Fetching…" : "Fetch models"}
                        </button>
                        <button
                          type="button"
                          className="btn btn--small btn--primary"
                          disabled={!commandDispatcher}
                          onClick={() => {
                            if (commandDispatcher) {
                              void submitModelConfigWriteCommand(commandDispatcher, model, {
                                enabled: model.enabled,
                                base_url: effectiveBaseUrl,
                                default_model: effectiveDefaultModel,
                              });
                            }
                          }}
                        >
                          Save
                        </button>
                        <button
                          type="button"
                          className="btn btn--small"
                          disabled={!commandDispatcher || !model.has_api_key || isTesting}
                          onClick={() => void testConnection(model)}
                          title="Live connectivity test (sends a minimal request to the provider)"
                        >
                          {isTesting ? "Testing…" : "Test"}
                        </button>
                      </div>
                    </div>

                    {testResult && (
                      <div className={`provider-card-status ${testResult.status === "validated" ? "provider-card-status--ok" : "provider-card-status--warn"}`}>
                        {MODEL_PROBE_STATUS_LABELS[testResult.status] ?? testResult.status}
                        {testResult.message ? ` — ${testResult.message}` : ""}
                      </div>
                    )}

                    <div className="provider-card-block">
                      <div className="provider-card-block__label">Models{contextWindow ? ` · context ${formatTokensCompact(contextWindow)}` : ""}</div>
                      <div className="provider-model-chips">
                        {modelList.length > 0 ? (
                          modelList.map((entry) => (
                            <button
                              type="button"
                              key={entry}
                              className={`provider-model-chip provider-model-chip--selectable${entry === effectiveDefaultModel ? " provider-model-chip--default" : ""}`}
                              title={entry === effectiveDefaultModel ? "Default model" : "Set as default model"}
                              disabled={!commandDispatcher || entry === effectiveDefaultModel}
                              onClick={() => {
                                if (commandDispatcher) {
                                  void submitModelConfigWriteCommand(commandDispatcher, model, {
                                    enabled: model.enabled,
                                    base_url: effectiveBaseUrl,
                                    default_model: entry,
                                  });
                                }
                              }}
                            >
                              {entry}
                              {entry === effectiveDefaultModel ? " · default" : ""}
                            </button>
                          ))
                        ) : (
                          <span className="provider-model-chip provider-model-chip--empty">
                            {effectiveDefaultModel || "no models — fetch from provider"}
                          </span>
                        )}
                      </div>
                      {fetchStatus && <div className="provider-card-status provider-card-status--ok">{fetchStatus}</div>}
                    </div>

                    <div className="provider-endpoint-row">
                      <span className="provider-card-block__label">Endpoint</span>
                      {endpoint.url ? (
                        <code className="provider-endpoint-row__url">{endpoint.url}</code>
                      ) : (
                        <span className="provider-model-chip provider-model-chip--empty">
                          {endpoint.hint ?? (effectiveBaseUrl || "no endpoint configured")}
                        </span>
                      )}
                    </div>

                    <div className="provider-key-status">
                      <span>API key</span>
                      {model.requires_api_key ? (
                        <>
                          <input
                            aria-label={`${model.provider} API key`}
                            type="password"
                            placeholder="Paste API key"
                            value={modelKeys[model.provider] ?? ""}
                            disabled={!commandDispatcher}
                            onChange={(event) => onModelKeysChange({
                              ...modelKeys,
                              [model.provider]: event.currentTarget.value,
                            })}
                          />
                          <div className="provider-key-status__actions">
                            <button
                              type="button"
                              className="btn btn--small btn--primary"
                              disabled={!commandDispatcher || !(modelKeys[model.provider] ?? "").trim()}
                              onClick={() => {
                                if (commandDispatcher) {
                                  void submitModelKeyRotateCommand(
                                    commandDispatcher,
                                    model,
                                    modelKeys[model.provider] ?? "",
                                  );
                                }
                                onModelKeysChange({ ...modelKeys, [model.provider]: "" });
                              }}
                            >
                              Set
                            </button>
                            <button
                              type="button"
                              className="btn btn--small"
                              disabled={!commandDispatcher || !model.has_api_key}
                              onClick={() => {
                                if (commandDispatcher) {
                                  void submitModelKeyRemoveCommand(commandDispatcher, model);
                                }
                              }}
                            >
                              Remove
                            </button>
                          </div>
                        </>
                      ) : (
                        <span className="provider-model-chip provider-model-chip--empty">No API key required</span>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </div>
      </section>
    </PageShell>
  );
};

/* ── Appearance: theme direction + light/dark ───────────────────────────────── */

const THEME_MODES: { id: Theme; label: string }[] = [
  { id: "auto", label: "Auto" },
  { id: "light", label: "Light" },
  { id: "dark", label: "Dark" },
];

const AppearancePage: React.FC<{
  theme: Theme;
  themeStyle: ThemeStyle;
  onApplyTheme: (theme: Theme, style: ThemeStyle) => void;
}> = ({ theme, themeStyle, onApplyTheme }) => {
  const resolvedTheme = getResolvedTheme(theme);
  return (
    <PageShell tabId="appearance" title="Appearance" description={PAGE_DESCRIPTIONS.appearance}>
      <section className="settings-section" aria-label="Theme mode">
        <div className="settings-section__head">
          <div>
            <div className="settings-section__title">Theme</div>
            <div className="settings-section__desc">
              {resolvedTheme === "light" ? "Light" : "Dark"} mode — Auto follows the operating system.
            </div>
          </div>
        </div>
        <div className="settings-section__body">
          <div className="settings-field">
            <div className="settings-field__copy">
              <div className="settings-field__label">Mode</div>
              <div className="settings-field__hint">Follow the OS, or force light/dark regardless of system settings.</div>
            </div>
            <div className="settings-field__control">
              <div className="theme-mode-picker" role="group" aria-label="Theme mode">
                {THEME_MODES.map((mode) => (
                  <button
                    key={mode.id}
                    type="button"
                    className={theme === mode.id ? "theme-mode-picker__on" : undefined}
                    aria-pressed={theme === mode.id}
                    onClick={() => onApplyTheme(mode.id, themeStyle)}
                  >
                    {mode.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="settings-section" aria-label="Theme direction">
        <div className="settings-section__head">
          <div>
            <div className="settings-section__title">Direction</div>
            <div className="settings-section__desc">
              Every direction works in both light and dark. This mirrors the Reasonix theme system.
            </div>
          </div>
        </div>
        <div className="settings-section__body">
          <div className="theme-style-grid">
            {THEME_STYLES.map((style) => {
              const swatch = THEME_STYLE_SWATCHES[style];
              const active = themeStyle === style;
              return (
                <button
                  key={style}
                  type="button"
                  className={`theme-style-card${active ? " theme-style-card--active" : ""}`}
                  aria-pressed={active}
                  onClick={() => onApplyTheme(theme, style)}
                >
                  <span className="theme-style-swatch" aria-hidden="true">
                    <i style={{ background: swatch.bg }} />
                    <i style={{ background: swatch.fg }} />
                    <i style={{ background: swatch.accent }} />
                  </span>
                  <span className="theme-style-card__name">{THEME_STYLE_LABELS[style]}</span>
                  <span className="theme-style-card__desc">{THEME_STYLE_DESCRIPTIONS[style]}</span>
                </button>
              );
            })}
          </div>
        </div>
      </section>
    </PageShell>
  );
};

export const getInitialThemePreference = readThemePreference;
export { applyTheme as applySettingsTheme } from "../lib/theme";
