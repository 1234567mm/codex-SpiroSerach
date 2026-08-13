import React from "react";
import type { WorkbenchCommandDispatcher } from "../adapters/command-adapter";
import {
  normalizeReadonlyRunOutputDir,
  type ReadonlyRunRecentOutputDir,
  type ReadonlyRunOperatorConfig,
} from "../adapters/readonly-run-operator-config";
import type {
  AtomReasonXSettingsState,
  AtomReasonXSourceSettingsState,
  ProviderConfigStatusEntry,
  SourceConfigStatusEntry,
} from "../contracts/types";

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
): Promise<unknown> => commandDispatcher.submitAction(
  "test_connection",
  buildModelSettingsCommandPayload(model),
);

export interface ModelConfigDraft {
  enabled: boolean;
  base_url: string;
  default_model: string;
}

export const SettingsModal: React.FC<{
  categories: string[];
  sourceSettings?: AtomReasonXSourceSettingsState;
  modelSettings?: AtomReasonXSettingsState;
  readonlyRunConfig?: ReadonlyRunOperatorConfig;
  readonlyRecentOutputDirs?: ReadonlyRunRecentOutputDir[];
  onApplyReadonlyRunOutputDir?: (outputDir: string | null) => void;
  commandDispatcher?: WorkbenchCommandDispatcher;
  onClose?: () => void;
}> = ({
  categories,
  sourceSettings,
  modelSettings,
  readonlyRunConfig,
  readonlyRecentOutputDirs = [],
  onApplyReadonlyRunOutputDir,
  commandDispatcher,
  onClose,
}) => {
  const [selected, setSelected] = React.useState(categories[0] ?? "General");
  const [sourceKeys, setSourceKeys] = React.useState<Record<string, string>>({});
  const [modelKeys, setModelKeys] = React.useState<Record<string, string>>({});
  const [modelConfigDrafts, setModelConfigDrafts] = React.useState<Record<string, ModelConfigDraft>>({});
  const [readonlyOutputDirDraft, setReadonlyOutputDirDraft] = React.useState(
    readonlyRunConfig?.outputDir ?? "",
  );
  const isDataSources = selected === "Data Sources";
  const isModels = selected === "Models";
  const readonlyOutputDir = readonlyRunConfig?.outputDir ?? null;
  const normalizedReadonlyOutputDirDraft = normalizeReadonlyRunOutputDir(readonlyOutputDirDraft);
  const readonlyOutputDirChanged = normalizedReadonlyOutputDirDraft !== readonlyOutputDir;
  const canConfigureReadonlyRun = Boolean(onApplyReadonlyRunOutputDir);

  React.useEffect(() => {
    setReadonlyOutputDirDraft(readonlyRunConfig?.outputDir ?? "");
  }, [readonlyRunConfig?.outputDir]);

  React.useEffect(() => {
    const drafts: Record<string, ModelConfigDraft> = {};
    for (const model of modelSettings?.providers ?? []) {
      drafts[model.provider] = {
        enabled: model.enabled,
        base_url: model.base_url ?? "",
        default_model: model.default_model ?? "",
      };
    }
    setModelConfigDrafts(drafts);
  }, [modelSettings]);

  return (
    <div className="settings-overlay" style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)",
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <div className="settings-modal" style={{
        width: "72%", height: "86%", background: "#1a1a2e",
        display: "flex", flexDirection: "row", borderRadius: "8px", overflow: "hidden",
      }}>
        <nav className="settings-nav" style={{ width: "200px", padding: "8px 0" }}>
          {categories.map((cat) => (
            <button key={cat} className={`settings-nav-item ${cat === selected ? "selected" : ""}`}
              onClick={() => setSelected(cat)}
              style={{
                width: "100%", padding: "6px 12px", fontSize: "13px", textAlign: "left",
                background: cat === selected ? "rgba(100,200,200,0.15)" : "transparent",
                border: 0,
                borderLeft: cat === selected ? "3px solid teal" : "3px solid transparent",
                color: "#eef",
              }}>
              {cat}
            </button>
          ))}
        </nav>
        <div className="settings-content" style={{ flex: 1, padding: "16px", overflowY: "auto" }}>
          <h3>{selected}</h3>
          {isDataSources ? (
            <div style={{ display: "grid", gap: "8px" }}>
              {readonlyRunConfig && (
                <section
                  aria-label="Readonly run output directory"
                  style={{
                    display: "grid",
                    gridTemplateColumns: "minmax(140px, 0.8fr) minmax(220px, 1.3fr) minmax(160px, 0.9fr) 72px 72px",
                    gap: "8px",
                    alignItems: "center",
                    padding: "8px",
                    border: "1px solid rgba(255,255,255,0.16)",
                    borderRadius: "6px",
                    fontSize: "12px",
                  }}
                >
                  <span>
                    <strong>Readonly Run</strong>
                    <span style={{ marginLeft: "8px", color: "#9fb" }}>
                      {readonlyRunConfig.readOnly ? "readonly_run" : "fixture"}
                    </span>
                  </span>
                  <input
                    aria-label="Readonly run output directory"
                    type="text"
                    value={readonlyOutputDirDraft}
                    disabled={!canConfigureReadonlyRun}
                    onChange={(event) => setReadonlyOutputDirDraft(event.currentTarget.value)}
                    style={{ minWidth: 0, width: "100%" }}
                  />
                  <select
                    aria-label="Recent readonly run output directories"
                    value=""
                    disabled={!canConfigureReadonlyRun || readonlyRecentOutputDirs.length === 0}
                    onChange={(event) => {
                      if (event.currentTarget.value) {
                        setReadonlyOutputDirDraft(event.currentTarget.value);
                      }
                    }}
                    style={{ minWidth: 0, width: "100%" }}
                  >
                    <option value="">Recent</option>
                    {readonlyRecentOutputDirs.map(item => (
                      <option key={`${item.source}:${item.outputDir}`} value={item.outputDir}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                  <button
                    type="button"
                    disabled={!canConfigureReadonlyRun || !readonlyOutputDirChanged}
                    onClick={() => onApplyReadonlyRunOutputDir?.(normalizedReadonlyOutputDirDraft)}
                  >
                    Apply
                  </button>
                  <button
                    type="button"
                    disabled={!canConfigureReadonlyRun || (!readonlyOutputDir && readonlyOutputDirDraft.trim() === "")}
                    onClick={() => {
                      setReadonlyOutputDirDraft("");
                      onApplyReadonlyRunOutputDir?.(null);
                    }}
                  >
                    Clear
                  </button>
                </section>
              )}
              {(sourceSettings?.sources ?? []).map((source) => (
                <div key={source.provider_id} style={{
                  display: "grid",
                  gridTemplateColumns: "minmax(120px, 1fr) 96px 96px minmax(160px, 1.5fr) minmax(220px, 1.5fr)",
                  gap: "8px",
                  alignItems: "center",
                  padding: "8px",
                  border: "1px solid rgba(255,255,255,0.1)",
                  borderRadius: "6px",
                  fontSize: "12px",
                }}>
                  <strong>{source.provider_id}</strong>
                  <span>{source.validation_state}</span>
                  <span>{source.key_requirement}</span>
                  <span>{source.data_library_path ?? ""}</span>
                  <span style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                    {source.requires_api_key && (
                      <>
                        <input
                          aria-label={`${source.provider_id} API key`}
                          type="password"
                          value={sourceKeys[source.provider_id] ?? ""}
                          onChange={(event) => setSourceKeys({
                            ...sourceKeys,
                            [source.provider_id]: event.currentTarget.value,
                          })}
                          style={{ minWidth: 0, width: "96px" }}
                        />
                        <button
                          type="button"
                          disabled={!commandDispatcher || !(sourceKeys[source.provider_id] ?? "").trim()}
                          onClick={() => {
                            if (commandDispatcher) {
                              void submitSourceSettingsCommand(commandDispatcher, "key_rotate", source, {
                                api_key: sourceKeys[source.provider_id] ?? "",
                              });
                            }
                            setSourceKeys({
                              ...sourceKeys,
                              [source.provider_id]: "",
                            });
                          }}
                        >
                          Set
                        </button>
                        <button
                          type="button"
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
                      disabled={!commandDispatcher}
                      onClick={() => {
                        if (commandDispatcher) {
                          void submitSourceProviderTestConnectionCommand(commandDispatcher, source);
                        }
                      }}
                    >
                      Test
                    </button>
                  </span>
                </div>
              ))}
            </div>
          ) : isModels ? (
            <div style={{ display: "grid", gap: "8px" }}>
              {!commandDispatcher && (
                <p style={{ fontSize: "12px", color: "#fb7" }}>
                  Model configuration backend unavailable: controls are disabled until a
                  command dispatcher is wired.
                </p>
              )}
              {(modelSettings?.providers ?? []).map((model) => {
                const draft = modelConfigDrafts[model.provider] ?? {
                  enabled: model.enabled,
                  base_url: model.base_url ?? "",
                  default_model: model.default_model ?? "",
                };
                return (
                  <div key={model.provider} style={{
                    display: "grid",
                    gridTemplateColumns: "minmax(140px, 1fr) 96px 110px minmax(180px, 1.4fr) minmax(160px, 1.2fr) minmax(180px, 1fr)",
                    gap: "8px",
                    alignItems: "center",
                    padding: "8px",
                    border: "1px solid rgba(255,255,255,0.1)",
                    borderRadius: "6px",
                    fontSize: "12px",
                  }}>
                    <span>
                      <strong>{model.provider}</strong>
                      {model.brand ? <span style={{ marginLeft: "6px", color: "#9cf" }}>{model.brand}</span> : null}
                      <span style={{ marginLeft: "6px", color: "#889" }}>{model.provider_kind}</span>
                    </span>
                    <span>{model.validation_state}</span>
                    <span>{model.has_api_key ? `key ${model.key_fingerprint ?? ""}` : "no key"}</span>
                    <input
                      aria-label={`${model.provider} base url`}
                      type="text"
                      placeholder="base_url (third-party endpoint)"
                      value={draft.base_url}
                      disabled={!commandDispatcher}
                      onChange={(event) => setModelConfigDrafts({
                        ...modelConfigDrafts,
                        [model.provider]: { ...draft, base_url: event.currentTarget.value },
                      })}
                      style={{ minWidth: 0, width: "100%" }}
                    />
                    <input
                      aria-label={`${model.provider} default model`}
                      type="text"
                      placeholder="model id"
                      value={draft.default_model}
                      disabled={!commandDispatcher}
                      onChange={(event) => setModelConfigDrafts({
                        ...modelConfigDrafts,
                        [model.provider]: { ...draft, default_model: event.currentTarget.value },
                      })}
                      style={{ minWidth: 0, width: "100%" }}
                    />
                    <span style={{ display: "flex", gap: "6px", alignItems: "center" }}>
                      {model.requires_api_key && (
                        <>
                          <input
                            aria-label={`${model.provider} API key`}
                            type="password"
                            placeholder="API key"
                            value={modelKeys[model.provider] ?? ""}
                            disabled={!commandDispatcher}
                            onChange={(event) => setModelKeys({
                              ...modelKeys,
                              [model.provider]: event.currentTarget.value,
                            })}
                            style={{ minWidth: 0, width: "110px" }}
                          />
                          <button
                            type="button"
                            disabled={!commandDispatcher || !(modelKeys[model.provider] ?? "").trim()}
                            onClick={() => {
                              if (commandDispatcher) {
                                void submitModelKeyRotateCommand(
                                  commandDispatcher,
                                  model,
                                  modelKeys[model.provider] ?? "",
                                );
                              }
                              setModelKeys({ ...modelKeys, [model.provider]: "" });
                            }}
                          >
                            Set
                          </button>
                        </>
                      )}
                      <button
                        type="button"
                        disabled={!commandDispatcher}
                        onClick={() => {
                          if (commandDispatcher) {
                            void submitModelConfigWriteCommand(commandDispatcher, model, {
                              enabled: draft.enabled,
                              base_url: draft.base_url,
                              default_model: draft.default_model,
                            });
                          }
                        }}
                      >
                        Save
                      </button>
                      <button
                        type="button"
                        disabled={!commandDispatcher || !model.has_api_key}
                        onClick={() => {
                          if (commandDispatcher) {
                            void submitModelTestConnectionCommand(commandDispatcher, model);
                          }
                        }}
                      >
                        Test
                      </button>
                    </span>
                  </div>
                );
              })}
            </div>
          ) : (
            <div style={{ fontSize: "13px", color: "#cfd3ff" }}>{selected}</div>
          )}
          <button onClick={onClose} className="close-btn">Close</button>
        </div>
      </div>
    </div>
  );
};
