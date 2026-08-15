// Data Sources settings page for the settings centre. This is the AtomReasonX
// data-source provider configuration surface extracted from the legacy
// SettingsModal and re-hosted inside the Reasonix-style settings centre. Keys
// are stored by the Python backend, never in the browser.

import React from "react";
import type { WorkbenchCommandDispatcher } from "../adapters/command-adapter";
import { normalizeReadonlyRunOutputDir } from "../adapters/readonly-run-operator-config";
import { getWorkspaceSettingsSlice } from "../lib/bridge";
import { useT } from "../lib/i18n";
import type {
  AtomReasonXSourceSettingsState,
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

export const DataSourcesSettingsPage: React.FC = () => {
  const t = useT();
  const [sourceKeys, setSourceKeys] = React.useState<Record<string, string>>({});
  const slice = getWorkspaceSettingsSlice();
  const sourceSettings = slice?.sourceSettings as AtomReasonXSourceSettingsState | undefined;
  const commandDispatcher = slice?.commandDispatcher;
  const sources = sourceSettings?.sources ?? [];
  const onSourceKeysChange = (keys: Record<string, string>) => setSourceKeys(keys);

  const readonlyRunConfig = slice?.readonlyRunConfig;
  const readonlyRecentOutputDirs = slice?.readonlyRecentOutputDirs ?? [];
  const onApplyReadonlyRunOutputDir = slice?.onApplyReadonlyRunOutputDir;
  const [readonlyOutputDirDraft, setReadonlyOutputDirDraft] = React.useState(
    readonlyRunConfig?.outputDir ?? "",
  );
  React.useEffect(() => {
    setReadonlyOutputDirDraft(readonlyRunConfig?.outputDir ?? "");
  }, [readonlyRunConfig?.outputDir]);
  const readonlyOutputDir = readonlyRunConfig?.outputDir ?? null;
  const normalizedReadonlyOutputDirDraft = normalizeReadonlyRunOutputDir(readonlyOutputDirDraft);
  const readonlyOutputDirChanged = normalizedReadonlyOutputDirDraft !== readonlyOutputDir;
  const canConfigureReadonlyRun = Boolean(onApplyReadonlyRunOutputDir);
  const modeLabel = readonlyRunConfig?.readOnly ? "readonly_run" : "fixture";

  return (
    <div className="settings-page settings-page--form settings-page--data-sources">
      <div className="settings-page__header">
        <h2 className="settings-page__title">{t("settings.tab.dataSources")}</h2>
        <p className="settings-page__desc">
          Credentials and connectivity for each data source provider. Keys are stored by the backend, never in the browser.
        </p>
      </div>
      <section className="settings-section" aria-label="Data source providers">
        <div className="settings-section__head">
          <div>
            <div className="settings-section__title">Providers</div>
            <div className="settings-section__desc">
              Credentials and connectivity for each data source provider.
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
                  placeholder="D:\path\to\run\output"
                  disabled={!canConfigureReadonlyRun}
                  onChange={(event) => setReadonlyOutputDirDraft(event.currentTarget.value)}
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
                    setReadonlyOutputDirDraft("");
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
    </div>
  );
};
