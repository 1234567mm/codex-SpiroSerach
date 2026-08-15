import { lazy, memo, Suspense, startTransition, useCallback, useDeferredValue, useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import { ArrowRight, BrainCircuit, Check, CheckCircle2, ChevronDown, ChevronUp, CircleDollarSign, ExternalLink, Languages, ListChecks, Loader2, Monitor, MoreHorizontal, PanelBottom, Play, Power, RefreshCw, ShieldCheck, SlidersHorizontal, Trash2, Volume2 } from "lucide-react";
import { asArray } from "../lib/array";
import { useDeferredClose } from "../lib/useMountTransition";
import { app, openExternal } from "../lib/bridge";
import { normalizeLangPref, useI18n, useT, type DictKey, type LangPref } from "../lib/i18n";
import { apiKeyEnvFromProviderName, createLatestRequestGate, inferredVisionModels, mergedFetchedProviderModels, mergeProviderModelContextWindows, providerApiKeyEnvForSave, providerDefaultModel, providerIsConfigured, providerModelCandidates, providerModelContextWindowDrafts, providerModelContextWindowIsSmall, providerRequiresKey } from "../lib/providerModels";
import { cachedFetchProviderModels, invalidateProviderCacheByAPIKeyEnv, shouldSkipAutoRefresh } from "../lib/providerModelCache";
import { providerBaseURLForSave, providerRequestURLFromConfig, trimmedBaseURL } from "../lib/providerEndpoint";
import { opencodeGoPresetDescriptionKeys } from "../lib/providerPresetDescriptions";
import { useUpdater } from "../lib/useUpdater";
import {
  applyTheme,
  getTheme,
  getThemeStyle,
  normalizeThemePreference,
  normalizeThemeStyleForTheme,
  type Theme,
  type ThemeStyle,
} from "../lib/theme";
import {
  applyTerminalThemePreference,
  createTerminalThemeSaveQueue,
  getTerminalThemePreference,
  normalizeTerminalThemePreference,
  type TerminalThemePreference,
} from "../lib/terminalTheme";
import {
  applyConversationWidth,
  getCachedConversationWidth,
  normalizeConversationWidth,
  type ConversationWidth,
} from "../lib/conversationWidth";
import { applyTextSize, getTextSize, type TextSize } from "../lib/textSize";
import { snapZoom, zoomToPercent, saveRestartZoom, getRestartZoom, type ZoomLevel } from "../lib/dpiScale";
import {
  applyFontFamily,
  applyMonoFontFamily,
  getFontFamily,
  getMonoFontFamily,
  getCustomFontName,
  getCustomMonoFontName,
  setCustomFontName,
  setCustomMonoFontName,
  type FontFamily,
  type MonoFontFamily,
} from "../lib/fontFamily";
import { getDisplayMode, onDisplayModeChange, setDisplayMode as setLocalDisplayMode } from "../lib/displayMode";
import { getProcessFoldPreference, onProcessFoldPreferenceChange, setProcessFoldPreference, type ProcessFoldPreference } from "../lib/processFoldPreference";
import { applyReasoningDisplayMode, useReasoningDisplayMode, type ReasoningDisplayMode } from "../lib/reasoningDisplayPreference";
import { normalizeStatusBarItems, type StatusBarItemId } from "../lib/statusBarItems";
import { normalizeToolApprovalMode } from "../lib/settings-types";
import type { HookConfigView, HooksSettingsView, NetworkView, ProviderModelCatalogUpdate, ProviderPresetView, ProviderView, SettingsTab, SettingsView } from "../lib/settings-types";
import { AppearanceOverview } from "./AppearanceOverview";
import { applyConfiguredBaseAppearance, setBaseAppearance } from "../lib/themePack";
import { InlineConfirmButton } from "./InlineConfirmButton";
import { Tooltip } from "./Tooltip";
import { AnchoredPopover } from "./AnchoredPopover";
import { getGenerativePreset, setGenerativePreset, generativeMusic, type GenerativePreset } from "../lib/generative-music";
import { SoundSelect } from "./SoundSelect";
import { getSuccessPreference, setSuccessPreference, getAttentionPreference, setAttentionPreference, playSuccessChime, playAttentionChime, type SoundWavPref } from "../lib/sound";
import { ModalCloseButton } from "./ModalCloseButton";
import { SettingsNavigation, SETTINGS_NAV_TABS } from "./SettingsNavigation";
import { StatusBarItemsEditor } from "./StatusBarItemsEditor";
export type SettingsInitialFocus =
  | { target: "model-access"; requestId?: number }
  | { target: "model-stats"; requestId: number };
type DesktopPlatform = "darwin" | "windows" | "linux";

const MCPServersSettingsPage = lazy(() => import("./CapabilitiesPanel").then((module) => ({ default: module.MCPServersSettingsPage })));
const DataSourcesSettingsPage = lazy(() => import("./DataSourcesSettingsPage").then((module) => ({ default: module.DataSourcesSettingsPage })));
// RemoteHostsPage and DiagnosticsSettingsPage are excluded from the port.
const SkillsSettingsPage = lazy(() => import("./CapabilitiesPanel").then((module) => ({ default: module.SkillsSettingsPage })));
const PluginsSettingsPage = lazy(() => import("./CapabilitiesPanel").then((module) => ({ default: module.PluginsSettingsPage })));
const MemorySettingsPage = lazy(() => import("./MemoryPanel").then((module) => ({ default: module.MemorySettingsPage })));
const SubagentsSettingsPage = lazy(() => import("./SubagentsPanel").then((module) => ({ default: module.SubagentsSettingsPage })));
// DiagnosticsSettingsPage excluded from the AtomReasonX port.
const StorageSettingsPage = lazy(() => import("./StorageSettingsPage").then((module) => ({ default: module.StorageSettingsPage })));
const UsageStatsPanel = lazy(() => import("./UsageStatsPanel").then((module) => ({ default: module.UsageStatsPanel })));
// QRCodeSVG import removed from the AtomReasonX port (bot tab excluded).

// SettingsPanel is the desktop settings centre: a modal hosting settings pages and capability management.
export function SettingsPanel({
  onClose,
  onChanged,
  initialTab,
  initialFocus,
  agentRunning = false,
  desktopPlatform,
  onUseSubagent,
  activeWorkspaceKey = "",
}: {
  onClose: () => void;
  onChanged: (settings?: SettingsView | null) => void;
  initialTab?: SettingsTab;
  initialFocus?: SettingsInitialFocus;
  agentRunning?: boolean;
  desktopPlatform: DesktopPlatform;
  onUseSubagent: (command: string) => void;
  activeWorkspaceKey?: string;
}) {
  const t = useT();
  const [s, setS] = useState<SettingsView | null>(null);
  const [loadingSettings, setLoadingSettings] = useState(true);
  const [settingsLoadFailed, setSettingsLoadFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [theme, setThemeState] = useState<Theme>(getTheme());
  const [themeStyle, setThemeStyleState] = useState<ThemeStyle>(() => getThemeStyle(getTheme()));
  const [terminalTheme, setTerminalThemeState] = useState<TerminalThemePreference>(getTerminalThemePreference());
  const [conversationWidth, setConversationWidth] = useState<ConversationWidth>(() => getCachedConversationWidth());
  const [textSize, setTextSizeState] = useState<TextSize>(getTextSize());
  const [zoomPct, setZoomPct] = useState<number>(zoomToPercent(getRestartZoom()));
  const [fontFamily, setFontFamilyState] = useState<FontFamily>(getFontFamily());
  const [monoFontFamily, setMonoFontFamilyState] = useState<MonoFontFamily>(getMonoFontFamily());
  const [customFontName, setCustomFontNameState] = useState<string>(getCustomFontName());
  const [customMonoFontName, setCustomMonoFontNameState] = useState<string>(getCustomMonoFontName());
  const [tab, setTab] = useState<SettingsTab>(initialTab === "providers" ? "models" : initialTab ?? "general");
  const settingsContentRef = useRef<HTMLElement>(null);
  const pendingSubagentCommandRef = useRef<string | null>(null);
  // Play the modal exit animation, then let the parent unmount us and focus
  // the composer with the selected slash command.
  const { status, requestClose } = useDeferredClose(() => {
    const command = pendingSubagentCommandRef.current;
    pendingSubagentCommandRef.current = null;
    onClose();
    if (command) onUseSubagent(command);
  }, 240);
  const zoomSaveSeq = useRef(0);
  const terminalThemeSaveSeq = useRef(0);
  const terminalThemeSavePending = useRef(false);
  const terminalThemeSaveQueue = useRef<ReturnType<typeof createTerminalThemeSaveQueue> | null>(null);
  if (!terminalThemeSaveQueue.current) {
    terminalThemeSaveQueue.current = createTerminalThemeSaveQueue((next) => app.SetDesktopTerminalTheme(next));
  }

  const reload = useCallback(async () => {
    setLoadingSettings(true);
    setSettingsLoadFailed(false);
    try {
      const next = normalizeSettingsView(await app.Settings());
      setS(next);
      return next;
    } catch {
      setS(null);
      setSettingsLoadFailed(true);
      return null;
    } finally {
      setLoadingSettings(false);
    }
  }, []);
  useEffect(() => {
    void reload();
    if (initialTab) setTab(initialTab === "providers" ? "models" : initialTab);
  }, [initialTab, reload]);
  useEffect(() => {
    const content = settingsContentRef.current;
    if (!content) return;
    content.scrollTop = 0;
    content.scrollLeft = 0;
  }, [tab]);
  useEffect(() => {
    if (!s) return;
    const nextTheme = normalizeThemePreference(s.desktopTheme);
    const nextStyle = normalizeThemeStyleForTheme(s.desktopThemeStyle, nextTheme);
    setThemeState(nextTheme);
    setThemeStyleState(nextStyle);
    if (!terminalThemeSavePending.current) {
      setTerminalThemeState(applyTerminalThemePreference(s.desktopTerminalTheme));
    }
    setConversationWidth(applyConversationWidth(s.conversationWidth));
  }, [s?.conversationWidth, s?.desktopTheme, s?.desktopThemeStyle, s?.desktopTerminalTheme]);
  useEffect(() => {
    if (desktopPlatform !== "windows") return;
    let cancelled = false;
    void (async () => {
      try {
        const persisted = await app.GetDesktopZoomFactor();
        if (cancelled || typeof persisted !== "number" || !Number.isFinite(persisted)) return;
        const snapped = snapZoom(persisted);
        saveRestartZoom(snapped);
        setZoomPct(zoomToPercent(snapped));
      } catch {
        // Older mocks or startup races can lack the binding; keep the local fallback.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [desktopPlatform]);

  // apply runs a mutation, re-reads settings, and refreshes the topbar/model.
  const apply = useCallback(async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setErr(null);
    setWarning(null);
    try {
      const result = await fn();
      const next = await reload();
      onChanged(next);
      window.dispatchEvent(new Event("reasonix:model-catalog-changed"));
      if (typeof result === "string" && result.trim()) {
        setWarning(result.trim());
      }
      return true;
    } catch (e) {
      // Settings writes can be two-phase: persistence may succeed before a
      // runtime refresh reports a real boot error. Re-read the authoritative
      // state even on failure so the UI never offers an action that already
      // committed (for example, a DeepSeek protocol upgrade).
      try {
        const next = await reload();
        onChanged(next);
        window.dispatchEvent(new Event("reasonix:model-catalog-changed"));
      } catch {
        // Keep the original mutation error; it is the actionable failure.
      }
      setErr(formatSettingsError(e, t));
      return false;
    } finally {
      setBusy(false);
    }
  }, [reload, onChanged, t]);
  const backgroundApply = useCallback(async (fn: () => Promise<void>) => {
    setErr(null);
    setWarning(null);
    try {
      await fn();
      const next = await reload();
      onChanged(next);
      window.dispatchEvent(new Event("reasonix:model-catalog-changed"));
    } catch (e) {
      setErr(formatSettingsError(e, t));
    }
  }, [reload, onChanged, t]);
  const setTerminalThemePreference = useCallback((next: TerminalThemePreference) => {
    const seq = ++terminalThemeSaveSeq.current;
    const previous = getTerminalThemePreference();
    terminalThemeSavePending.current = true;
    setErr(null);
    setWarning(null);
    applyTerminalThemePreference(next);
    setTerminalThemeState(next);

    void terminalThemeSaveQueue.current!(next)
      .then(async () => {
        if (seq !== terminalThemeSaveSeq.current) return;
        const refreshed = await reload();
        if (seq !== terminalThemeSaveSeq.current) return;
        terminalThemeSavePending.current = false;
        onChanged(refreshed);
      })
      .catch(async (error) => {
        if (seq !== terminalThemeSaveSeq.current) return;
        const refreshed = await reload();
        if (seq !== terminalThemeSaveSeq.current) return;
        const restored = normalizeTerminalThemePreference(refreshed?.desktopTerminalTheme ?? previous);
        applyTerminalThemePreference(restored);
        setTerminalThemeState(restored);
        terminalThemeSavePending.current = false;
        setErr(formatSettingsError(error, t));
        onChanged(refreshed);
      });
  }, [onChanged, reload, t]);
  const setRestartZoom = useCallback(async (zoom: ZoomLevel) => {
    const snapped = snapZoom(zoom);
    const seq = ++zoomSaveSeq.current;
    setErr(null);
    setWarning(null);
    setZoomPct(zoomToPercent(snapped));
    try {
      await app.SetDesktopZoomFactor(snapped);
      if (seq === zoomSaveSeq.current) saveRestartZoom(snapped);
    } catch (e) {
      if (seq !== zoomSaveSeq.current) return;
      setErr(formatSettingsError(e, t));
      setZoomPct(zoomToPercent(getRestartZoom()));
    }
  }, [t]);

  // Close on Esc
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape" && !document.querySelector("[data-anchored-popover='active']")) requestClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [requestClose]);

  // These pages need SettingsView; capability pages load their own data.
  const needsSettings = tab === "general" || tab === "models" || tab === "subagents" || tab === "network" || tab === "permissions" || tab === "sandbox" || tab === "appearance" || tab === "updates";
  const lazySettingsPageFallback = <div className="empty">{t("settings.loading")}</div>;
  const settingsNavigationItems = useMemo(() => SETTINGS_NAV_TABS.map((id) => ({
    id,
    label: settingsTabLabel(id, t),
    meta: s ? settingsTabMeta(id, s, t) : "",
    searchTerms: id === "general" ? [
      "settings.desktopLayoutStyle", "settings.language", "settings.currency", "settings.displayMode",
      "settings.reasoningDisplay", "settings.processFold", "settings.closeBehavior",
      "settings.defaultToolApprovalMode", "settings.sound", "settings.statusBarStyle", "settings.statusBarItems",
    ].map((key) => t(key as DictKey)).join(" ") : "",
  })), [s, t]);

  return (
    <div className="management-modal-backdrop settings-modal-backdrop" data-state={status} onMouseDown={(e) => { if (e.target === e.currentTarget) requestClose(); }}>
      <div className="management-modal settings-modal" data-state={status}>
        <header className="management-modal__head settings-modal__head">
          <div className="management-modal__title settings-modal__title">{t("settings.title")}</div>
          <ModalCloseButton label={t("common.close")} onClick={requestClose} />
        </header>

        <div className="settings-center">
          <SettingsNavigation items={settingsNavigationItems} activeTab={tab} onSelect={setTab} />
          <main ref={settingsContentRef} className="settings-center__content">
            {needsSettings && settingsLoadFailed && (
              <div className="banner banner--error settings-load-error" role="alert">
                <span>{t("settings.loadFailed")}</span>
                <button className="btn btn--small" type="button" onClick={() => void reload()}>{t("common.retry")}</button>
              </div>
            )}
            {needsSettings && err && <div className="banner banner--error">{err}</div>}
            {needsSettings && warning && <div className="banner banner--warning">{warning}</div>}
            {needsSettings && !s ? (
              loadingSettings ? <div className="empty">{t("settings.loading")}</div> : null
            ) : (
              <>
                {tab === "general" && s && <SettingsPageShell key={tab} s={s} tab={tab} busy={busy} apply={apply}><GeneralSection s={s} busy={busy} apply={apply} agentRunning={agentRunning} /></SettingsPageShell>}
                {tab === "models" && s && <SettingsPageShell key={tab} s={s} tab={tab} busy={busy} apply={apply}><ModelsSection s={s} busy={busy} apply={apply} backgroundApply={backgroundApply} initialFocus={initialFocus} /></SettingsPageShell>}
                {tab === "mcp" && <SettingsPageShell key={tab} s={s} tab={tab} busy={false} apply={apply}><Suspense fallback={lazySettingsPageFallback}><MCPServersSettingsPage /></Suspense></SettingsPageShell>}
                {tab === "data-sources" && <SettingsPageShell key={tab} s={s} tab={tab} busy={false} apply={apply}><Suspense fallback={lazySettingsPageFallback}><DataSourcesSettingsPage /></Suspense></SettingsPageShell>}
                {tab === "skills" && <SettingsPageShell key={tab} s={s} tab={tab} busy={false} apply={apply}><Suspense fallback={lazySettingsPageFallback}><SkillsSettingsPage activeWorkspaceKey={activeWorkspaceKey} /></Suspense></SettingsPageShell>}
                {tab === "subagents" && s && <SettingsPageShell key={tab} s={s} tab={tab} busy={busy} apply={apply}><Suspense fallback={lazySettingsPageFallback}><SubagentsSettingsPage s={s} onUseInChat={(command) => {
                  pendingSubagentCommandRef.current = command;
                  requestClose();
                }} /></Suspense></SettingsPageShell>}
                {tab === "plugins" && <SettingsPageShell key={tab} s={s} tab={tab} busy={false} apply={apply}><Suspense fallback={lazySettingsPageFallback}><PluginsSettingsPage /></Suspense></SettingsPageShell>}
                {tab === "memory" && <SettingsPageShell key={tab} s={s} tab={tab} busy={false} apply={apply}><Suspense fallback={lazySettingsPageFallback}><MemorySettingsPage /></Suspense></SettingsPageShell>}
                {tab === "hooks" && <SettingsPageShell key={tab} s={s} tab={tab} busy={false} apply={apply}><HooksSection onChanged={onChanged} /></SettingsPageShell>}
                {tab === "permissions" && s && <SettingsPageShell key={tab} s={s} tab={tab} busy={busy} apply={apply}><PermissionsSection s={s} busy={busy} apply={apply} /></SettingsPageShell>}
                {tab === "sandbox" && s && <SettingsPageShell key={tab} s={s} tab={tab} busy={busy} apply={apply}><SandboxSection s={s} busy={busy} apply={apply} windows={desktopPlatform === "windows"} /></SettingsPageShell>}
                {tab === "network" && s && <SettingsPageShell key={tab} s={s} tab={tab} busy={busy} apply={apply}><NetworkSection s={s} busy={busy} apply={apply} /></SettingsPageShell>}
                {tab === "appearance" && s && (
                  <SettingsPageShell key={tab} s={s} tab={tab} busy={busy} apply={apply}>
                    <AppearanceOverview
                      theme={theme}
                      themeStyle={themeStyle}
                      terminalTheme={terminalTheme}
                      conversationWidth={conversationWidth}
                      textSize={textSize}
                      showDisplayZoom={desktopPlatform === "windows"}
                      zoomPct={zoomPct}
                      fontFamily={fontFamily}
                      monoFontFamily={monoFontFamily}
                      customFontName={customFontName}
                      customMonoFontName={customMonoFontName}
                      onTheme={(nextTheme) => {
                        applyConfiguredBaseAppearance(nextTheme, themeStyle);
                        setThemeState(nextTheme);
                        void apply(() => app.SetDesktopAppearance(nextTheme, themeStyle));
                      }}
                      onConversationWidth={(width) => {
                        applyConversationWidth(width);
                        setConversationWidth(width);
                        void apply(() => app.SetDesktopConversationWidth(width));
                      }}
                      onThemeStyle={(style) => {
                        // AppearanceOverview already persists via ActivateBaseStyle /
                        // experience APIs. Parent only mirrors React + DOM state.
                        applyTheme(getTheme(), style, { persist: false });
                        setThemeStyleState(style);
                        setBaseAppearance(getTheme(), style);
                      }}
                      onTerminalTheme={setTerminalThemePreference}
                      onTextSize={(size) => {
                        applyTextSize(size);
                        setTextSizeState(size);
                      }}
                      onRestartZoom={setRestartZoom}
                      onFontFamily={(font) => {
                        applyFontFamily(font);
                        setFontFamilyState(font);
                      }}
                      onMonoFontFamily={(font) => {
                        applyMonoFontFamily(font);
                        setMonoFontFamilyState(font);
                      }}
                      onCustomFontNameChange={(name) => {
                        setCustomFontNameState(name);
                        setCustomFontName(name);
                        applyFontFamily("custom");
                      }}
                      onCustomMonoFontNameChange={(name) => {
                        setCustomMonoFontNameState(name);
                        setCustomMonoFontName(name);
                        applyMonoFontFamily("custom");
                      }}
                    />
                  </SettingsPageShell>
                )}
                {tab === "storage" && <SettingsPageShell key={tab} s={s} tab={tab} busy={false} apply={apply}><Suspense fallback={lazySettingsPageFallback}><StorageSettingsPage /></Suspense></SettingsPageShell>}
                {tab === "updates" && s && (
                  <SettingsPageShell key={tab} s={s} tab={tab} busy={busy} apply={apply}>
                    <UpdatesSection
                      configPath={s.configPath}
                      shadowedByPath={s.shadowedByPath}
                      checkUpdates={s.checkUpdates}
                      telemetry={s.telemetry !== false}
                      metrics={s.metrics !== false}
                      settingsBusy={busy}
                      applySettings={apply}
                    />
                  </SettingsPageShell>
                )}
              </>
            )}
          </main>
        </div>
      </div>
    </div>
  );
}

function SettingsPageShell({ s: _s, tab, children }: { s: SettingsView | null; tab: SettingsTab; busy: boolean; apply: (fn: () => Promise<unknown>) => Promise<boolean>; children: ReactNode }) {
  const t = useT();
  const descKey = `settings.pageDesc.${tab}` as keyof typeof import("../locales/en").en;
  const desc = t(descKey as any);
  return (
    <div className={`settings-page settings-page--${settingsPageKind(tab)} settings-page--${tab}`}>
      {tab !== "appearance" ? (
        <div className="settings-page__header">
          <h2 className="settings-page__title">{settingsTabPageTitle(tab, t)}</h2>
          {typeof desc === "string" && desc !== `settings.pageDesc.${tab}` && <p className="settings-page__desc">{desc}</p>}
        </div>
      ) : null}
      {children}
    </div>
  );
}

function settingsPageKind(tab: SettingsTab): "form" | "manager" {
  switch (tab) {
    case "models":
    case "mcp":
    case "skills":
    case "subagents":
    case "plugins":
    case "memory":
    case "appearance":
      return "manager";
    default:
      return "form";
  }
}

function SettingsSection({
  title,
  description,
  actions,
  children,
}: {
  title?: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
}) {
  const hasHead = Boolean(title || description || actions);
  return (
    <section className="settings-section">
      {hasHead && (
        <div className="settings-section__head">
          <div>
            {title && <div className="settings-section__title">{title}</div>}
            {description && (
              <div className="settings-section__desc">
                <SettingsHint hint={description} />
              </div>
            )}
          </div>
          {actions && <div className="settings-section__actions">{actions}</div>}
        </div>
      )}
      <div className="settings-section__body">{children}</div>
    </section>
  );
}

function SettingsField({
  label,
  hint,
  icon,
  children,
  className,
  stacked = false,
}: {
  label: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  children: ReactNode;
  className?: string;
  stacked?: boolean;
}) {
  return (
    <div className={`settings-field${stacked ? " settings-field--stacked" : ""}${className ? ` ${className}` : ""}`}>
      <div className={`settings-field__copy${icon ? " settings-field__copy--icon" : ""}`}>
        {icon && <span className="settings-field__icon" aria-hidden="true">{icon}</span>}
        <div className="settings-field__copy-body">
          <div className="settings-field__label">{label}</div>
          {hint && (
            <div className="settings-field__hint">
              <SettingsHint hint={hint} />
            </div>
          )}
        </div>
      </div>
      <div className="settings-field__control">{children}</div>
    </div>
  );
}

function SettingsHint({ hint }: { hint: ReactNode }) {
  if (typeof hint === "string" || typeof hint === "number") {
    const label = String(hint);
    return (
      <Tooltip label={label} fill block className="settings-field__hint-tooltip">
        <span className="settings-field__hint-line">{label}</span>
      </Tooltip>
    );
  }
  return hint;
}

function settingsTabPageTitle(id: SettingsTab, t: ReturnType<typeof useT>): string {
  switch (id) {
    case "mcp": return t("settings.tab.mcp");
    case "skills": return t("settings.tab.skills");
    case "plugins": return t("settings.tab.plugins");
    case "memory": return t("settings.tab.memory");
    default: return settingsTabLabel(id, t);
  }
}

type SectionProps = {
  s: SettingsView;
  busy: boolean;
  apply: (fn: () => Promise<unknown>) => Promise<boolean>;
};

type ModelsSectionProps = SectionProps & {
  backgroundApply: (fn: () => Promise<void>) => Promise<void>;
  initialFocus?: SettingsInitialFocus;
};

function settingsTabLabel(id: SettingsTab, t: ReturnType<typeof useT>): string {
  switch (id) {
    case "general":
      return t("settings.tab.general");
    case "models":
      return t("settings.tab.models");
    case "providers":
      return t("settings.tab.providers");
    case "data-sources":
      return t("settings.tab.dataSources");
    case "mcp":
      return t("settings.tab.mcp");
      return t("settings.tab.remote");
    case "skills":
      return t("settings.tab.skills");
    case "subagents":
      return t("settings.tab.subagents");
    case "plugins":
      return t("settings.tab.plugins");
    case "memory":
      return t("settings.tab.memory");
    case "hooks":
      return t("settings.tab.hooks");
    case "network":
      return t("settings.tab.network");
    case "permissions":
      return t("settings.tab.permissions");
    case "sandbox":
      return t("settings.tab.sandbox");
    case "appearance": return t("settings.tab.appearance");
    case "storage": return t("settings.tab.storage");
    case "updates":
      return t("settings.tab.updates");
  }
}

function settingsTabMeta(id: SettingsTab, s: SettingsView, t: ReturnType<typeof useT>): string {
  switch (id) {
    case "models":
      return settingsModelMeta(s, t);
    case "general":
      return `${desktopLayoutStyleLabel(normalizeDesktopLayoutStyle(s.desktopLayoutStyle), t)} · ${closeBehaviorLabel(normalizeCloseBehavior(s.closeBehavior), t)}`;
    case "providers":
      return t("settings.providerCount", { n: s.providers.length });
    case "data-sources":
      return t("settings.tabSub.dataSources");
    case "mcp":
      return t("caps.connectorsTab");
      return t("remote.tabHint");
    case "skills":
      return t("settings.tabSub.skills");
    case "subagents":
      return t("subagents.tabHint");
    case "plugins":
      return t("settings.tabSub.plugins");
    case "memory":
      return t("settings.tabSub.memory");
    case "hooks":
      return t("settings.tabSub.hooks");
    case "network":
      return proxyModeLabel(normalizeProxyMode(s.network.proxyMode), t);
    case "permissions":
      return permissionModeLabel(s.permissions.mode, t);
    case "sandbox":
      return sandboxModeLabel(s.sandbox.bash, t);
    case "appearance": return t("settings.appearanceMeta");
    case "storage": return t("settings.storageMeta");
    case "updates":
      return t("settings.updatesMeta");
  }
}

function settingsModelMeta(s: SettingsView, t: ReturnType<typeof useT>): string {
  const ref = toRef(s.defaultModel, s);
  if (!ref) return t("common.none");
  if (!ref.includes("/")) return ref;
  const [provider, ...modelParts] = ref.split("/");
  const model = modelParts.join("/") || ref;
  const providerView = s.providers.find((p) => p.name === provider);
  return `${modelProviderLabel(provider, providerView, t)} · ${model}`;
}

// allRefs flattens providers into "provider/model" refs for the model selectors.
export function allRefs(s: SettingsView): string[] {
  const out: string[] = [];
  for (const p of s.providers) {
    if (!p.added || !providerIsConfigured(p)) continue;
    for (const m of p.models) out.push(`${p.name}/${m}`);
  }
  return out;
}

// toRef normalises a stored model id (a provider name, a bare model, or a ref) to
// a "provider/model" ref so a <select> of refs can show it selected.
export function toRef(model: string, s: SettingsView): string {
  if (!model) return "";
  if (model.includes("/")) return model;
  const byName = s.providers.find((p) => p.name === model);
  if (byName) return `${byName.name}/${byName.default || byName.models[0] || ""}`;
  const byModel = s.providers.find((p) => p.models.includes(model));
  if (byModel) return `${byModel.name}/${model}`;
  return model;
}

const PROXY_MODES = ["auto", "custom", "off"] as const;

// EFFORT_PRESETS is the canonical union of /effort levels the kernel recognises.
// The settings UI uses it for subagent defaults; provider-specific levels are
// inferred by the backend or edited in TOML for rare gateways.
export const EFFORT_PRESETS: readonly string[] = ["low", "medium", "high", "xhigh", "max"];
const COMPACT_RATIO_PRESETS = [
  [0.7, "settings.compactRatioPreset.70"],
  [0.8, "settings.compactRatioPreset.80"],
  [0.85, "settings.compactRatioPreset.85"],
] as const;
const REASONING_PROTOCOLS: readonly string[] = ["", "deepseek", "glm", "kimi-k3", "openai", "none"];
const THINKING_MODES: readonly string[] = ["", "enabled", "disabled", "adaptive"];
const PROXY_TYPES = ["http", "https", "socks5", "socks5h"] as const;
const LANGUAGE_PREFS: LangPref[] = ["", "zh", "en"];
const TOOL_APPROVAL_MODES = ["ask", "auto", "yolo"] as const;

type ProxyMode = (typeof PROXY_MODES)[number];

function normalizeProxyMode(mode: string): ProxyMode {
  switch (mode) {
    case "custom":
      return "custom";
    case "off":
      return "off";
    default:
      return "auto";
  }
}

function normalizeNetworkView(network: NetworkView): NetworkView {
  return { ...network, proxyMode: normalizeProxyMode(network.proxyMode) };
}

function normalizeReasoningProtocol(protocol: string | undefined): string {
  return REASONING_PROTOCOLS.includes(protocol ?? "") ? protocol ?? "" : "";
}

function normalizeThinkingMode(thinking: string | undefined): string {
  const v = String(thinking ?? "").trim().toLowerCase();
  return THINKING_MODES.includes(v) ? v : "";
}

export function providerEditorEffectiveKind(isNewCustomProvider: boolean, kind: string, kinds: string[]): string {
  void isNewCustomProvider;
  const selected = kind.trim();
  return selected || kinds[0] || "openai";
}

function formatProviderHeaders(headers: Record<string, string> | null | undefined): string {
  const entries = Object.entries(headers ?? {})
    .map(([key, value]) => [key.trim(), String(value ?? "").trim()] as const)
    .filter(([key, value]) => key && value)
    .sort(([a], [b]) => a.localeCompare(b));
  return entries.map(([key, value]) => `${key}: ${value}`).join("\n");
}

function parseProviderHeaders(raw: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const colon = trimmed.indexOf(":");
    const eq = trimmed.indexOf("=");
    const cut = colon >= 0 && (eq < 0 || colon < eq) ? colon : eq;
    if (cut <= 0) continue;
    const key = trimmed.slice(0, cut).trim();
    const value = trimmed.slice(cut + 1).trim();
    if (key && value) out[key] = value;
  }
  return out;
}

function sortedJSONValue(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(sortedJSONValue);
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const key of Object.keys(value as Record<string, unknown>).sort((a, b) => a.localeCompare(b))) {
      out[key] = sortedJSONValue((value as Record<string, unknown>)[key]);
    }
    return out;
  }
  return value;
}

function formatSettingsError(error: unknown, t: ReturnType<typeof useT>): string {
  const msg = String((error as Error)?.message ?? error ?? "").trim();
  const unknownModel = /^unknown model (.+)$/i.exec(msg);
  if (unknownModel) return t("settings.errorUnknownModel", { model: unknownModel[1] });
  const providerNotAdded = /^model (.+) is not available because provider (.+) is not added$/i.exec(msg);
  if (providerNotAdded) return t("settings.errorModelProviderMissing", { model: providerNotAdded[1], provider: providerNotAdded[2] });
  const providerNoKey = /^model (.+) is not available because provider (.+) has no key$/i.exec(msg);
  if (providerNoKey) return t("settings.errorModelProviderNoKey", { model: providerNoKey[1], provider: providerNoKey[2] });
  if (/^background session is still open; reopen or close it before upgrading the DeepSeek provider protocol$/i.test(msg)) {
    return t("settings.errorProviderDetached");
  }
  const removeAccessBusy = /^finish or cancel active work using (.+) before removing the provider access$/i.exec(msg);
  if (removeAccessBusy) return t("settings.errorRemoveAccessBusy", { provider: removeAccessBusy[1] });
  const removeAccessDetached = /^background session is still using (.+); reopen or close it before removing the provider access$/i.exec(msg);
  if (removeAccessDetached) return t("settings.errorProviderDetached");
  const removeAccessNoFallback = /^remove provider access: (.+) is in use and no other configured provider exists$/i.exec(msg);
  if (removeAccessNoFallback) return t("settings.errorRemoveProviderNoFallback", { provider: removeAccessNoFallback[1] });
  const deleteProviderNoFallback = /^remove provider: (.+) is in use and no other configured provider exists$/i.exec(msg);
  if (deleteProviderNoFallback) return t("settings.errorRemoveProviderNoFallback", { provider: deleteProviderNoFallback[1] });
  const deleteProviderBusy = /^finish or cancel active work using (.+) before deleting the provider$/i.exec(msg);
  if (deleteProviderBusy) return t("settings.errorDeleteProviderBusy", { provider: deleteProviderBusy[1] });
  const deleteProviderDetached = /^background session is still using (.+); reopen or close it before deleting the provider$/i.exec(msg);
  if (deleteProviderDetached) return t("settings.errorProviderDetached");
  const saveBeforeRemoveAccess = /^save current session before removing provider access: (.+)$/is.exec(msg);
  if (saveBeforeRemoveAccess) return t("settings.errorSaveBeforeRemoveAccess", { err: saveBeforeRemoveAccess[1] });
  const saveBeforeDeleteProvider = /^save current session before deleting provider: (.+)$/is.exec(msg);
  if (saveBeforeDeleteProvider) return t("settings.errorSaveBeforeDeleteProvider", { err: saveBeforeDeleteProvider[1] });
  const removeProviderUsed = /^remove provider: (.+) is used by open tabs and no other configured provider exists$/i.exec(msg);
  if (removeProviderUsed) return t("settings.errorRemoveProviderNoFallback", { provider: removeProviderUsed[1] });
  return msg || t("settings.errorUnknown");
}

function validateProviderExtraBodyValue(value: unknown, path = "extra_body", t?: ReturnType<typeof useT>): void {
  if (value === null) {
    throw new Error(t ? t("settings.providerExtraBodyNull", { path }) : `${path} cannot contain null`);
  }
  if (Array.isArray(value)) {
    value.forEach((item, index) => validateProviderExtraBodyValue(item, `${path}[${index}]`, t));
    return;
  }
  if (typeof value === "object") {
    for (const [key, child] of Object.entries(value as Record<string, unknown>)) {
      validateProviderExtraBodyValue(child, `${path}.${key}`, t);
    }
  }
}

export function formatProviderExtraBody(extraBody: Record<string, unknown> | null | undefined): string {
  const cleaned: Record<string, unknown> = {};
  for (const [rawKey, value] of Object.entries(extraBody ?? {})) {
    const key = rawKey.trim();
    if (!key || value === undefined) continue;
    cleaned[key] = value;
  }
  if (Object.keys(cleaned).length === 0) return "";
  return JSON.stringify(sortedJSONValue(cleaned), null, 2);
}

export function parseProviderExtraBody(raw: string, t?: ReturnType<typeof useT>): Record<string, unknown> {
  const trimmed = raw.trim();
  if (!trimmed) return {};
  const parsed = JSON.parse(trimmed) as unknown;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(t ? t("settings.providerExtraBodyObjectRequired") : "extra body must be a JSON object");
  }
  validateProviderExtraBodyValue(parsed, "extra_body", t);
  const out: Record<string, unknown> = {};
  for (const [rawKey, value] of Object.entries(parsed as Record<string, unknown>)) {
    const key = rawKey.trim();
    if (key) out[key] = value;
  }
  return out;
}

export function providerExtraBodyParseError(error: unknown, t: ReturnType<typeof useT>): string {
  if (error instanceof SyntaxError) return t("settings.providerExtraBodyError");
  const message = String((error as Error)?.message ?? error ?? "").trim();
  return message || t("settings.providerExtraBodyError");
}

function providerModelFetchFallbackMessage(error: unknown, t: ReturnType<typeof useT>): string {
  const message = String((error as Error)?.message ?? error);
  if (/\bstatus\s+(401|403)\b/i.test(message)) {
    return t("settings.fetchModelsManualFallbackAuth");
  }
  if (/\bstatus\s+(404|405)\b/i.test(message)) {
    return t("settings.fetchModelsManualFallbackUnsupported");
  }
  if (/\b(status\s+5\d\d|request failed|network|timeout|timed out|connection|deadline|fetch failed)\b/i.test(message)) {
    return t("settings.fetchModelsManualFallbackNetwork");
  }
  if (/\b(decode response|invalid character|unexpected end|unexpected format)\b/i.test(message)) {
    return t("settings.fetchModelsManualFallbackDecode");
  }
  return t("settings.fetchModelsManualFallbackGeneric", { err: message });
}

function normalizeReasoningLanguage(lang: string | undefined): string {
  const v = String(lang ?? "").trim().toLowerCase();
  return v === "zh" || v === "en" ? v : "auto";
}

function normalizeStringMap(value: unknown): Record<string, string> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const out: Record<string, string> = {};
  for (const [rawKey, rawValue] of Object.entries(value as Record<string, unknown>)) {
    const key = rawKey.trim();
    const val = String(rawValue ?? "").trim();
    if (key && val) out[key] = val;
  }
  return out;
}

function normalizeExtraBodyMap(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) return {};
  const out: Record<string, unknown> = {};
  for (const [rawKey, rawValue] of Object.entries(value as Record<string, unknown>)) {
    const key = rawKey.trim();
    if (key && rawValue !== undefined) out[key] = rawValue;
  }
  return out;
}

export function normalizeProviderView(p: ProviderView): ProviderView {
  const visionModels = asArray(p.visionModels);
  const requiresKey = providerRequiresKey(p);
  return {
    ...p,
    name: String(p.name ?? ""),
    baseUrl: String(p.baseUrl ?? ""),
    builtIn: Boolean(p.builtIn),
    added: Boolean(p.added),
    chatUrl: p.chatUrl ?? "",
    requestUrl: p.requestUrl ?? "",
    models: asArray(p.models),
    visionModels,
    visionModelsConfigured: Boolean(p.visionModelsConfigured ?? visionModels.length > 0),
    visionCapability: p.visionCapability === "unsupported" || p.visionCapability === "configurable"
      ? p.visionCapability
      : undefined,
    modelsUrl: p.modelsUrl ?? "",
    headers: normalizeStringMap(p.headers),
    extraBody: normalizeExtraBodyMap(p.extraBody),
    authHeader: Boolean(p.authHeader),
    reasoningProtocol: normalizeReasoningProtocol(p.reasoningProtocol),
    thinking: normalizeThinkingMode(p.thinking),
    webSearch: Boolean(p.webSearch),
    serverWebSearchCapability: typeof p.serverWebSearchCapability === "boolean"
      ? p.serverWebSearchCapability
      : undefined,
    supportedEfforts: asArray(p.supportedEfforts),
    modelOverrides: asArray(p.modelOverrides),
    recommendedUpgradeAvailable: Boolean(p.recommendedUpgradeAvailable),
    requiresKey,
    configured: providerIsConfigured({ ...p, requiresKey }),
    keySource: p.keySource ?? "",
    keySourcePath: p.keySourcePath ?? "",
    modelCatalogFingerprint: p.modelCatalogFingerprint ?? "",
  };
}

type ProviderPresetStatus = NonNullable<ProviderPresetView["status"]>;

function normalizeProviderPresetStatus(status: ProviderPresetView["status"] | undefined, added: boolean): ProviderPresetStatus {
  if (status === "installed" || status === "installed_modified" || status === "name_conflict" || status === "similar_existing") return status;
  return added ? "installed" : "available";
}

function normalizeProviderPresetView(p: ProviderPresetView): ProviderPresetView {
  const requiresKey = Boolean(p.requiresKey ?? p.keyEnv);
  const configured = Boolean(p.configured ?? (!requiresKey || p.keySet));
  const status = normalizeProviderPresetStatus(p.status, Boolean(p.added));
  return {
    ...p,
    id: String(p.id ?? "").trim(),
    label: String(p.label ?? "").trim(),
    description: String(p.description ?? "").trim(),
    keyEnv: String(p.keyEnv ?? "").trim(),
    providerNames: asArray(p.providerNames),
    models: asArray(p.models),
    added: Boolean(p.added || status === "installed" || status === "installed_modified" || status === "name_conflict"),
    status,
    statusProviderNames: asArray(p.statusProviderNames),
    keySet: Boolean(p.keySet),
    requiresKey,
    configured,
    keySource: p.keySource ?? "",
    keySourcePath: p.keySourcePath ?? "",
  };
}

function normalizeSettingsView(view: SettingsView | null | undefined): SettingsView | null {
  if (!view) return null;
  const permissions = view.permissions ?? { mode: "ask", allow: [], ask: [], deny: [] };
  const sandbox = view.sandbox ?? { bash: "enforce", network: false, workspaceRoot: "", allowWrite: [], effectiveWorkspaceRoot: "", effectiveWriteRoots: [], shell: "auto", effectiveShell: "" };
  const network = view.network ?? {
    proxyMode: "auto",
    proxyUrl: "",
    noProxy: "",
    proxy: { type: "socks5", server: "", port: 0, username: "", password: "" },
  };
  const agent = view.agent ?? { temperature: 0, maxSteps: 0, plannerMaxSteps: 0, maxSubagentDepth: 2, maxSubagentConcurrency: 6, maxParallelWriters: 3, systemPrompt: "", reasoningLanguage: "auto", compactRatio: 0.85 };
  agent.plannerMaxSteps = Number.isFinite(agent.plannerMaxSteps) ? Math.max(0, Math.trunc(agent.plannerMaxSteps)) : 0;
  agent.maxSteps = Number.isFinite(agent.maxSteps) ? Math.max(0, Math.trunc(agent.maxSteps)) : 0;
  agent.maxSubagentDepth = Number.isFinite(agent.maxSubagentDepth) && agent.maxSubagentDepth <= 1 ? 1 : 2;
  agent.reasoningLanguage = normalizeReasoningLanguage(agent.reasoningLanguage);
  agent.compactRatio = Number.isFinite(agent.compactRatio) && Number(agent.compactRatio) > 0 ? Number(agent.compactRatio) : 0.85;
  agent.effectiveCompactRatio = Number.isFinite(agent.effectiveCompactRatio) && Number(agent.effectiveCompactRatio) > 0
    ? Number(agent.effectiveCompactRatio)
    : agent.compactRatio;
  agent.compactRatioOverridden = Boolean(agent.compactRatioOverridden);
  return {
    ...view,
    providers: asArray(view.providers).map(normalizeProviderView),
    officialProviders: asArray(view.officialProviders).map(normalizeProviderView),
    providerPresets: asArray(view.providerPresets).map(normalizeProviderPresetView).filter((p) => p.id),
    providerKinds: asArray(view.providerKinds),
    permissions: {
      ...permissions,
      allow: asArray(permissions.allow),
      ask: asArray(permissions.ask),
      deny: asArray(permissions.deny),
    },
    sandbox: {
      ...sandbox,
      allowWrite: asArray(sandbox.allowWrite),
      effectiveWorkspaceRoot: String(sandbox.effectiveWorkspaceRoot ?? ""),
      effectiveWriteRoots: asArray(sandbox.effectiveWriteRoots),
      effectiveShell: String(sandbox.effectiveShell ?? sandbox.shell ?? ""),
    },
    network: {
      ...network,
      proxy: network.proxy ?? { type: "socks5", server: "", port: 0, username: "", password: "" },
    },
    agent,
    autoPlan: "off",
    defaultToolApprovalMode: normalizeToolApprovalMode(view.defaultToolApprovalMode),
    autoApproveTools: Boolean(view.autoApproveTools ?? view.bypass),
    bypass: Boolean(view.autoApproveTools ?? view.bypass),
    desktopLanguage: normalizeLangPref(view.desktopLanguage),
    desktopCurrency: normalizeDesktopCurrency(view.desktopCurrency),
    desktopLayoutStyle: normalizeDesktopLayoutStyle(view.desktopLayoutStyle),
    desktopTheme: normalizeThemePreference(view.desktopTheme),
    desktopThemeStyle: normalizeThemeStyleForTheme(view.desktopThemeStyle, normalizeThemePreference(view.desktopTheme)),
    desktopTerminalTheme: normalizeTerminalThemePreference(view.desktopTerminalTheme),
    closeBehavior: normalizeCloseBehavior(view.closeBehavior),
    displayMode: normalizeDisplayMode(view.displayMode),
    statusBarStyle: normalizeStatusBarStyle(view.statusBarStyle),
    statusBarItems: normalizeStatusBarItems(view.statusBarItems),
    conversationWidth: normalizeConversationWidth(view.conversationWidth),
    checkUpdates: view.checkUpdates !== false,
    updateChannel: "stable",
  };
}

type DesktopCurrency = "" | "CNY" | "USD";

function normalizeDesktopCurrency(currency: string | undefined): DesktopCurrency {
  return currency === "CNY" || currency === "USD" ? currency : "";
}

type CloseBehavior = "background" | "quit";

function normalizeCloseBehavior(mode: string | undefined): CloseBehavior {
  return mode === "quit" ? "quit" : "background";
}

type DisplayMode = "standard" | "compact";

function normalizeDisplayMode(mode: string | undefined): DisplayMode {
  return mode === "standard" || mode === "compact" ? mode : "standard";
}

type DesktopLayoutStyle = "classic" | "workbench" | "creation";

function normalizeDesktopLayoutStyle(style: string | undefined): DesktopLayoutStyle {
  if (style === "classic") return "classic";
  if (style === "creation") return "creation";
  return "workbench";
}

function desktopLayoutStyleLabel(style: DesktopLayoutStyle, t: ReturnType<typeof useT>): string {
  return t(`settings.desktopLayoutStyle.${style}`);
}

type StatusBarStyle = "icon" | "text";
function normalizeStatusBarStyle(style: string | undefined): StatusBarStyle {
  return style === "icon" ? "icon" : "text";
}

function statusBarItemLabel(id: StatusBarItemId, t: ReturnType<typeof useT>): string {
  switch (id) {
    case "model":
      return t("settings.statusBarItem.model");
    case "workspace":
      return t("settings.statusBarItem.workspace");
    case "git_branch":
      return t("settings.statusBarItem.gitBranch");
    case "cache":
      return t("status.cacheLabel");
    case "cache_avg":
      return t("status.cacheAvgLabel");
    case "session_tokens":
      return t("status.sessionTokensLabel");
    case "turn_tokens":
      return t("status.turnTokensLabel");
    case "turn_tps":
      return t("status.tpsLabel");
    case "turn_output_tokens":
      return t("status.outputTokensLabel");
    case "turn_cache_tokens":
      return t("status.cacheTokensLabel");
    case "turn_cost":
      return t("status.turnCostLabel");
    case "session_turns":
      return t("status.sessionTurnsLabel");
    case "context":
      return t("status.ctxLabel");
    case "compact":
      return t("status.compactLabel");
    case "cost":
      return t("status.costLabel");
    case "balance":
      return t("status.balanceLabel");
  }
}

function closeBehaviorLabel(mode: CloseBehavior, t: ReturnType<typeof useT>): string {
  return mode === "quit" ? t("settings.closeBehavior.quit") : t("settings.closeBehavior.background");
}

function permissionModeLabel(mode: string, t: ReturnType<typeof useT>): string {
  switch (mode) {
    case "allow":
      return t("settings.modeAllowShort");
    case "deny":
      return t("settings.modeDenyShort");
    default:
      return t("settings.modeAskShort");
  }
}

function sandboxModeLabel(mode: string, t: ReturnType<typeof useT>): string {
  return mode === "off" ? t("settings.bashOffShort") : t("settings.bashEnforceShort");
}

function providerKindLabel(kind: string, t: ReturnType<typeof useT>): string {
  switch (kind) {
    case "anthropic":
      return t("settings.providerProtocolAnthropic");
    case "openai":
      return t("settings.providerProtocolOpenAI");
    default:
      return kind;
  }
}

function providerKindHint(kind: string, t: ReturnType<typeof useT>): string {
  return kind === "anthropic" ? t("settings.providerProtocolAnthropicHint") : t("settings.providerProtocolOpenAIHint");
}

function reasoningProtocolLabel(protocol: string, t: ReturnType<typeof useT>): string {
  switch (protocol) {
    case "deepseek":
      return t("settings.reasoningProtocol.deepseek");
    case "glm": return t("settings.reasoningProtocol.glm");
    case "kimi-k3": return t("settings.reasoningProtocol.kimiK3");
    case "openai":
      return t("settings.reasoningProtocol.openai");
    case "none":
      return t("settings.reasoningProtocol.none");
    default:
      return t("settings.reasoningProtocol.auto");
  }
}

function thinkingModeLabel(mode: string, t: ReturnType<typeof useT>): string {
  switch (mode) {
    case "enabled":
      return t("settings.thinkingMode.enabled");
    case "disabled":
      return t("settings.thinkingMode.disabled");
    case "adaptive":
      return t("settings.thinkingMode.adaptive");
    default:
      return t("settings.thinkingMode.auto");
  }
}

function GeneralSection({ s, busy, apply, agentRunning }: SectionProps & { agentRunning: boolean }) {
  const { t, setPref } = useI18n();
  const closeBehavior = normalizeCloseBehavior(s.closeBehavior);
  const [displayMode, setDisplayMode] = useState<DisplayMode>(() => normalizeDisplayMode(getDisplayMode()));
  const [processFold, setProcessFold] = useState<ProcessFoldPreference>(getProcessFoldPreference);
  const reasoningDisplayMode = useReasoningDisplayMode();
  const soundPanelId = useId();
  useEffect(() => onDisplayModeChange((mode) => setDisplayMode(mode)), []);
  useEffect(() => onProcessFoldPreferenceChange((pref) => setProcessFold(pref)), []);
  const defaultToolApprovalMode = normalizeToolApprovalMode(s.defaultToolApprovalMode);
  const saveReasoningDisplayMode = useCallback(async (mode: ReasoningDisplayMode) => {
    const ok = await apply(() => app.SetReasoningDisplayMode(mode));
    if (ok) applyReasoningDisplayMode(mode);
  }, [apply]);
  const languagePref = normalizeLangPref(s.desktopLanguage);
  const desktopCurrency = normalizeDesktopCurrency(s.desktopCurrency);
  const desktopLayoutStyle = normalizeDesktopLayoutStyle(s.desktopLayoutStyle);
  const [genMusicPreset, setGenMusicPreset] = useState<GenerativePreset>(getGenerativePreset());
  const [soundPref, setSoundPref] = useState<SoundWavPref>(getSuccessPreference());
  const [attentionPref, setAttentionPref] = useState<SoundWavPref>(getAttentionPreference());
  const [soundExpanded, setSoundExpanded] = useState(false);
  const statusBarStyle = normalizeStatusBarStyle(s.statusBarStyle);
  const statusBarItems = normalizeStatusBarItems(s.statusBarItems);
  const soundStatus = summarizeSoundStatus(genMusicPreset, soundPref, attentionPref);
  const applyStatusBarItems = (items: StatusBarItemId[]) => {
    const contentScrollTop = document.querySelector<HTMLElement>(".settings-center__content")?.scrollTop ?? 0;
    const navScrollTop = document.querySelector<HTMLElement>(".settings-center__nav")?.scrollTop ?? 0;
    const active = document.activeElement;
    if (active instanceof HTMLElement && active.closest(".status-bar-items-editor")) active.blur();
    void apply(() => app.SetStatusBarItems(items)).finally(() => {
      window.scrollTo(0, 0);
      requestAnimationFrame(() => {
        window.scrollTo(0, 0);
        const content = document.querySelector<HTMLElement>(".settings-center__content");
        const nav = document.querySelector<HTMLElement>(".settings-center__nav");
        if (content) content.scrollTop = Math.min(contentScrollTop, Math.max(0, content.scrollHeight - content.clientHeight));
        if (nav) nav.scrollTop = navScrollTop;
      });
    });
  };
  const setLanguage = (next: LangPref) => {
    setPref(next);
    void apply(() => app.SetDesktopLanguage(next));
  };
  return (
    <>
      <SettingsSection title={t("settings.general.sectionAppearance")} description={t("settings.general.sectionAppearanceHint")}>
      <SettingsField label={t("settings.desktopLayoutStyle")} hint={t("settings.desktopLayoutStyleHint")} icon={<Monitor size={18} />}>
        <div className="set-seg">
          {(["workbench", "classic", "creation"] as const).map((style) => (
            <button
              key={style}
              className={`set-seg__btn${desktopLayoutStyle === style ? " set-seg__btn--on" : ""}`}
              disabled={busy}
              onClick={() => void apply(() => app.SetDesktopLayoutStyle(style))}
            >
              {desktopLayoutStyleLabel(style, t)}
            </button>
          ))}
        </div>
      </SettingsField>
      <SettingsField label={t("settings.language")} hint={t("settings.languageHint")} icon={<Languages size={18} />}>
        <div className="set-seg">
          {LANGUAGE_PREFS.map((pref) => (
            <button
              key={pref || "auto"}
              className={`set-seg__btn${languagePref === pref ? " set-seg__btn--on" : ""}`}
              disabled={busy}
              onClick={() => setLanguage(pref)}
            >
              {pref === "" ? t("settings.langAuto") : pref === "zh" ? "中文" : "English"}
            </button>
          ))}
        </div>
      </SettingsField>
      <SettingsField label={t("settings.currency")} hint={t("settings.currencyHint")} icon={<CircleDollarSign size={18} />}>
        <div className="set-seg">
          {(["", "CNY", "USD"] as DesktopCurrency[]).map((currency) => (
            <button
              key={currency || "auto"}
              className={`set-seg__btn${desktopCurrency === currency ? " set-seg__btn--on" : ""}`}
              disabled={busy || agentRunning}
              onClick={() => void apply(() => app.SetDesktopCurrency(currency))}
            >
              {currency === "" ? t("settings.currencyAuto") : currency}
            </button>
          ))}
        </div>
      </SettingsField>
      </SettingsSection>

      <SettingsSection title={t("settings.general.sectionConversation")} description={t("settings.sessionContentDisplayHint")}>
        <SettingsField label={t("settings.displayMode")} hint={t("settings.displayModeHint")} icon={<SlidersHorizontal size={18} />}>
          <div className="set-seg" role="radiogroup" aria-label={t("settings.displayMode")}>
            {(["standard", "compact"] as const).map((mode) => (
              <button key={mode} type="button"
                className={`set-seg__btn${displayMode === mode ? " set-seg__btn--on" : ""}`}
                aria-pressed={displayMode === mode}
                disabled={busy}
                onClick={() => {
                  setLocalDisplayMode(mode);
                  void apply(() => app.SetDisplayMode(mode));
                }}
              >
                {t(`settings.displayMode.${mode}`)}
              </button>
            ))}
          </div>
        </SettingsField>
        <SettingsField label={t("settings.reasoningDisplay")} hint={t("settings.reasoningDisplayHint")} icon={<BrainCircuit size={18} />}>
          <div>
            <div className="set-seg" role="radiogroup" aria-label={t("settings.reasoningDisplay")}>
              {(["hidden", "summary", "auto", "expanded"] as const).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  className={`set-seg__btn${reasoningDisplayMode === mode ? " set-seg__btn--on" : ""}`}
                  aria-pressed={reasoningDisplayMode === mode}
                  disabled={busy}
                  onClick={() => void saveReasoningDisplayMode(mode)}
                >
                  {t(`settings.reasoningDisplay.${mode}`)}
                </button>
              ))}
            </div>
            {reasoningDisplayMode === "legacy-collapsed" && <div className="settings-inline-hint" role="status">{t("settings.reasoningDisplay.legacy")}</div>}
          </div>
        </SettingsField>
        <SettingsField label={t("settings.processFold")} hint={t("settings.processFoldHint")} icon={<ListChecks size={18} />}>
          <div className="set-seg" role="radiogroup" aria-label={t("settings.processFold")}>
            {(["auto", "expanded"] as const).map((pref) => (
              <button
                key={pref}
                type="button"
                className={`set-seg__btn${processFold === pref ? " set-seg__btn--on" : ""}`}
                aria-pressed={processFold === pref}
                onClick={() => setProcessFoldPreference(pref)}
              >
                {t(`settings.processFold.${pref}`)}
              </button>
            ))}
          </div>
        </SettingsField>
      </SettingsSection>

      <SettingsSection title={t("settings.general.sectionSystem")} description={t("settings.general.sectionSystemHint")}>
      <SettingsField label={t("settings.closeBehavior")} hint={t("settings.closeBehaviorHint")} icon={<Power size={18} />}>
        <div className="set-seg">
          {(["background", "quit"] as const).map((mode) => (
            <button
              key={mode}
              className={`set-seg__btn${closeBehavior === mode ? " set-seg__btn--on" : ""}`}
              disabled={busy}
              onClick={() => void apply(() => app.SetCloseBehavior(mode))}
            >
              {closeBehaviorLabel(mode, t)}
            </button>
          ))}
        </div>
      </SettingsField>
      <SettingsField label={t("settings.defaultToolApprovalMode")} hint={t("settings.defaultToolApprovalModeHint")} icon={<ShieldCheck size={18} />}>
        <div className="set-seg">
          {TOOL_APPROVAL_MODES.map((mode) => (
            <button
              key={mode}
              className={`set-seg__btn${defaultToolApprovalMode === mode ? " set-seg__btn--on" : ""}`}
              disabled={busy}
              onClick={() => void apply(() => app.SetDefaultToolApprovalMode(mode))}
            >
              {t(`settings.defaultToolApprovalMode.${mode}`)}
            </button>
          ))}
        </div>
      </SettingsField>
      <SettingsField label={t("settings.sound")} hint={t("settings.soundHint")} icon={<Volume2 size={18} />} stacked>
        <div className={`settings-sound-editor${soundExpanded ? " settings-sound-editor--expanded" : ""}`}>
          <div className="settings-sound-editor__summary">
            <span className={`settings-sound-editor__status settings-sound-editor__status--${soundStatus}`}>
              {t(`settings.soundStatus.${soundStatus}`)}
            </span>
            <Tooltip label={t(soundExpanded ? "settings.soundCollapse" : "settings.soundExpand")}>
              <button
                type="button"
                className="settings-sound-editor__toggle"
                aria-expanded={soundExpanded}
                aria-controls={soundPanelId}
                aria-label={t(soundExpanded ? "settings.soundCollapse" : "settings.soundExpand")}
                onClick={() => setSoundExpanded((open) => !open)}
              >
                {soundExpanded ? <ChevronUp size={15} aria-hidden="true" /> : <ChevronDown size={15} aria-hidden="true" />}
              </button>
            </Tooltip>
          </div>
          {soundExpanded && (
            <div className="settings-sound-editor__list" id={soundPanelId}>
              <div className="settings-sound-row">
                <span className="settings-sound-row__label">{t("settings.generativeMusic")}</span>
                <GenMusicSelect
                  value={genMusicPreset}
                  onChange={(next) => {
                    setGenMusicPreset(next);
                    setGenerativePreset(next);
                    if (next === "off") {
                      generativeMusic.stop();
                    } else {
                      if (generativeMusic.isRunning) {
                        generativeMusic.setPreset(next);
                      } else if (agentRunning) {
                        generativeMusic.start(next);
                      }
                      generativeMusic.playPreview(next);
                    }
                  }}
                  onPreview={() => { if (genMusicPreset !== "off") generativeMusic.playPreview(genMusicPreset); }}
                  previewDisabled={genMusicPreset === "off"}
                />
              </div>
              <div className="settings-sound-row">
                <span className="settings-sound-row__label">{t("settings.notificationSoundSuccess")}</span>
                <SoundSelect
                  value={soundPref}
                  onChange={(next) => {
                    setSoundPref(next);
                    setSuccessPreference(next);
                    playSuccessChime();
                  }}
                  onPreview={playSuccessChime}
                  previewDisabled={soundPref === "off"}
                />
              </div>
              <div className="settings-sound-row">
                <span className="settings-sound-row__label">{t("settings.notificationSoundAttention")}</span>
                <SoundSelect
                  value={attentionPref}
                  onChange={(next) => {
                    setAttentionPref(next);
                    setAttentionPreference(next);
                    playAttentionChime();
                  }}
                  onPreview={playAttentionChime}
                  previewDisabled={attentionPref === "off"}
                />
              </div>
            </div>
          )}
        </div>
      </SettingsField>
      <SettingsField label={t("settings.statusBarStyle")} hint={t("settings.statusBarStyleHint")} icon={<PanelBottom size={18} />}>
        <div className="set-seg">
          {(["icon", "text"] as const).map((style) => (
            <button
              key={style}
              className={`set-seg__btn${statusBarStyle === style ? " set-seg__btn--on" : ""}`}
              disabled={busy}
              onClick={() => void apply(() => app.SetStatusBarStyle(style))}
            >
              {t(`settings.statusBarStyle.${style}`)}
            </button>
          ))}
        </div>
      </SettingsField>
      <SettingsField label={t("settings.statusBarItems")} hint={t("settings.statusBarItemsHint")} icon={<ListChecks size={18} />} className="status-bar-items-setting" stacked>
        <StatusBarItemsEditor
          items={statusBarItems}
          busy={busy}
          onChange={applyStatusBarItems}
          itemLabel={(id) => statusBarItemLabel(id, t)}
        />
      </SettingsField>
    </SettingsSection>
    </>
  );
}

const GENRE_OPTIONS: { value: GenerativePreset; labelKey: DictKey }[] = [
  { value: "off", labelKey: "settings.generativeMusic.off" },
  { value: "ethereal", labelKey: "settings.generativeMusic.presets.ethereal" },
  { value: "classic", labelKey: "settings.generativeMusic.presets.classic" },
  { value: "digital", labelKey: "settings.generativeMusic.presets.digital" },
  { value: "retro", labelKey: "settings.generativeMusic.presets.retro" },
];

function summarizeSoundStatus(
  music: GenerativePreset,
  success: SoundWavPref,
  attention: SoundWavPref,
): "allOff" | "enabled" | "custom" {
  const enabledCount = [music !== "off", success !== "off", attention !== "off"].filter(Boolean).length;
  if (enabledCount === 0) return "allOff";
  if (enabledCount === 1) return "enabled";
  return "custom";
}

function GenMusicSelect({
  value,
  onChange,
  onPreview,
  previewDisabled,
}: {
  value: GenerativePreset;
  onChange: (v: GenerativePreset) => void;
  onPreview: () => void;
  previewDisabled?: boolean;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const selected = GENRE_OPTIONS.find((o) => o.value === value) ?? GENRE_OPTIONS[0];

  return (
    <div className="sound-select">
      <button
        ref={triggerRef}
        className="sound-select__trigger"
        type="button"
        onClick={() => setOpen((v) => !v)}
      >
        <span className="sound-select__label">{t(selected.labelKey)}</span>
        <ChevronDown
          size={16}
          className={`sound-select__chev${open ? " sound-select__chev--open" : ""}`}
        />
      </button>
      {!previewDisabled && (
        <button className="chip chip--icon" type="button" title={t("settings.generativeMusicPreview")} aria-label={t("settings.generativeMusicPreview")} onClick={onPreview}>
          <Play size={13} aria-hidden="true" />
        </button>
      )}
      <AnchoredPopover
        open={open}
        anchorRef={triggerRef}
        onClose={() => setOpen(false)}
        className="sound-select__menu"
        placement="bottom"
      >
        <div className="sound-select__list" role="listbox">
          {GENRE_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              className={`sound-select__option${opt.value === value ? " sound-select__option--selected" : ""}`}
              role="option"
              aria-selected={opt.value === value}
              type="button"
              onClick={() => {
                onChange(opt.value);
                setOpen(false);
              }}
            >
              <span>{t(opt.labelKey)}</span>
              {opt.value === value && <Check size={14} className="sound-select__check" />}
            </button>
          ))}
        </div>
      </AnchoredPopover>
    </div>
  );
}

function NetworkSection({ s, busy, apply }: SectionProps) {
  const t = useT();
  const savedNetwork = normalizeNetworkView(s.network);
  const [draft, setDraft] = useState<NetworkView>(savedNetwork);
  useEffect(() => setDraft(normalizeNetworkView(s.network)), [s.network]);
  const dirty = JSON.stringify(draft) !== JSON.stringify(savedNetwork);
  const setProxy = (next: Partial<NetworkView["proxy"]>) => {
    setDraft({ ...draft, proxy: { ...draft.proxy, ...next } });
  };

  return (
    <SettingsSection
      title={t("settings.tab.network")}
      actions={
        <button
          className="btn btn--primary btn--small"
          disabled={busy || !dirty}
          onClick={() => void apply(() => app.SetNetwork(draft))}
        >
          {t("settings.saveNetwork")}
        </button>
      }
    >
      <SettingsField label={t("settings.proxyMode")}>
        <div className="set-seg">
          {PROXY_MODES.map((mode) => (
            <button
              key={mode}
              className={`set-seg__btn${draft.proxyMode === mode ? " set-seg__btn--on" : ""}`}
              disabled={busy}
              onClick={() => setDraft({ ...draft, proxyMode: mode })}
            >
              {proxyModeLabel(mode, t)}
            </button>
          ))}
        </div>
      </SettingsField>

      {draft.proxyMode === "custom" && (
        <>
          <SettingsField label={t("settings.proxyType")}>
            <div className="set-seg">
              {PROXY_TYPES.map((typ) => (
                <button
                  key={typ}
                  className={`set-seg__btn${draft.proxy.type === typ ? " set-seg__btn--on" : ""}`}
                  disabled={busy}
                  onClick={() => setProxy({ type: typ })}
                >
                  {typ.toUpperCase()}
                </button>
              ))}
            </div>
          </SettingsField>
          <SettingsField label={t("settings.proxyServer")}>
            <div className="settings-inline-controls">
            <input
              className="mem-input set-grow"
              placeholder="127.0.0.1"
              value={draft.proxy.server}
              disabled={busy || !!draft.proxyUrl.trim()}
              onChange={(e) => setProxy({ server: e.target.value })}
            />
            <label className="set-label">{t("settings.proxyPort")}</label>
            <input
              className="mem-input set-narrow"
              placeholder="7890"
              value={draft.proxy.port ? String(draft.proxy.port) : ""}
              disabled={busy || !!draft.proxyUrl.trim()}
              inputMode="numeric"
              onChange={(e) => setProxy({ port: Number(e.target.value) || 0 })}
            />
            </div>
          </SettingsField>
          <SettingsField label={t("settings.proxyUsername")}>
            <div className="settings-inline-controls">
            <input
              className="mem-input set-grow"
              value={draft.proxy.username}
              disabled={busy || !!draft.proxyUrl.trim()}
              onChange={(e) => setProxy({ username: e.target.value })}
            />
            <label className="set-label">{t("settings.proxyPassword")}</label>
            <input
              className="mem-input set-grow"
              type="password"
              value={draft.proxy.password}
              disabled={busy || !!draft.proxyUrl.trim()}
              onChange={(e) => setProxy({ password: e.target.value })}
            />
            </div>
          </SettingsField>
          <SettingsField label={t("settings.proxyUrl")} hint={t("settings.proxyUrlHint")}>
              <input
                className="mem-input set-grow"
                placeholder="socks5://127.0.0.1:7890"
                value={draft.proxyUrl}
                disabled={busy}
                onChange={(e) => setDraft({ ...draft, proxyUrl: e.target.value })}
              />
          </SettingsField>
          <SettingsField label={t("settings.noProxy")}>
            <input
              className="mem-input set-grow"
              placeholder="localhost,127.0.0.1,.local"
              value={draft.noProxy}
              disabled={busy}
              onChange={(e) => setDraft({ ...draft, noProxy: e.target.value })}
            />
          </SettingsField>
        </>
      )}
    </SettingsSection>
  );
}

function ModelsSection({ s, busy, apply, backgroundApply, initialFocus }: ModelsSectionProps) {
  const t = useT();
  const [subtab, setSubtab] = useState<"usage" | "access" | "stats">(
    initialFocus?.target === "model-access"
      ? "access"
      : initialFocus?.target === "model-stats"
        ? "stats"
        : "usage",
  );
  // The command palette may re-target this section while the settings panel is
  // already open (the subtab state is not remounted by a tab change). Each
  // freshly allocated focus request runs this effect once, including repeated
  // requests for the same target after the user changes subtabs.
  useEffect(() => {
    if (initialFocus?.target !== "model-access" && initialFocus?.target !== "model-stats") return;
    setSubtab(initialFocus.target === "model-access" ? "access" : "stats");
  }, [initialFocus?.target, initialFocus?.requestId]);
  const autoRefreshKeyRef = useRef("");
  const autoRefreshGenerationRef = useRef(0);
  const refs = useMemo(() => allRefs(s), [s.providers]);
  const defaultRef = toRef(s.defaultModel, s);
  const plannerRef = toRef(s.plannerModel, s);
  const subagentRef = toRef(s.subagentModel, s);
  const plannerSelectRef = plannerRef === defaultRef ? "" : plannerRef;
  const [defaultProvider] = defaultRef.split("/");
  const defaultProviderView = s.providers.find((p) => p.name === defaultProvider);
  const modelIssue = !defaultProviderView
    ? t("settings.modelUnavailable", { ref: defaultRef || t("common.none") })
    : !providerIsConfigured(defaultProviderView)
      ? t("settings.modelNeedsKey", { provider: modelProviderLabel(defaultProvider, defaultProviderView, t) })
      : "";
  const agent = s.agent ?? { temperature: 0, maxSteps: 0, plannerMaxSteps: 0, maxSubagentDepth: 2, maxSubagentConcurrency: 6, maxParallelWriters: 3, systemPrompt: "", reasoningLanguage: "auto", compactRatio: 0.85 };
  const compactRatio = agent.compactRatio ?? 0.85;
  const compactRatioPercent = Math.round(compactRatio * 1000) / 10;
  const [compactRatioDraft, setCompactRatioDraft] = useState(() => String(compactRatioPercent));
  const [compactRatioCustomOpen, setCompactRatioCustomOpen] = useState(false);
  const compactRatioCustomInputRef = useRef<HTMLInputElement>(null);
  const compactRatioPreset = COMPACT_RATIO_PRESETS.find(([ratio]) => Math.abs(compactRatio - ratio) < 0.0001);
  const compactRatioDraftPercent = Number(compactRatioDraft);
  const compactRatioDraftValid = compactRatioDraft !== ""
    && Number.isFinite(compactRatioDraftPercent)
    && compactRatioDraftPercent >= 65
    && compactRatioDraftPercent <= 85;
  const compactRatioDraftDirty = compactRatioDraftValid
    && Math.abs(compactRatioDraftPercent / 100 - compactRatio) > 0.0001;
  const defaultModel = defaultRef.startsWith(`${defaultProvider}/`) ? defaultRef.slice(defaultProvider.length + 1) : "";
  const modelContextWindow = defaultProviderView?.modelOverrides?.find((override) => override.model === defaultModel)?.contextWindow ?? 0;
  const effectiveContextWindow = modelContextWindow > 0 ? modelContextWindow : (defaultProviderView?.contextWindow ?? 0);
  const compactTokens = effectiveContextWindow > 0 ? Math.round(effectiveContextWindow * compactRatio) : 0;
  const compactRatioImpact = compactTokens > 0
    ? t("settings.compactRatioImpactWithTokens", { percent: compactRatioPercent, tokens: compactTokens.toLocaleString() })
    : t("settings.compactRatioImpact", { percent: compactRatioPercent });
  const compactRatioSelection = compactRatioPreset
    ? t(compactRatioPreset[1])
    : t("settings.compactRatioCustomValue", { percent: compactRatioPercent });
  const compactRatioOverrideHint = agent.compactRatioOverridden
    ? t("settings.compactRatioProjectOverride", { percent: Math.round((agent.effectiveCompactRatio ?? compactRatio) * 100) })
    : "";
  const subagentDepth = Number.isFinite(agent.maxSubagentDepth) && agent.maxSubagentDepth <= 1 ? 1 : 2;
  const subagentConcurrency = Number.isFinite(agent.maxSubagentConcurrency) && agent.maxSubagentConcurrency > 0
    ? Math.max(1, Math.min(32, Math.floor(agent.maxSubagentConcurrency)))
    : 6;
  const parallelWriters = Number.isFinite(agent.maxParallelWriters) && agent.maxParallelWriters > 0
    ? Math.max(1, Math.min(subagentConcurrency, Math.floor(agent.maxParallelWriters)))
    : Math.min(3, subagentConcurrency);

  useEffect(() => {
    setCompactRatioDraft(String(compactRatioPercent));
  }, [compactRatioPercent]);

  useEffect(() => {
    if (compactRatioCustomOpen) compactRatioCustomInputRef.current?.focus();
  }, [compactRatioCustomOpen]);

  const persistCompactRatio = async (ratio: number) => {
    if (await apply(() => app.SetCompactRatio(ratio))) setCompactRatioCustomOpen(false);
  };

  const openCompactRatioCustom = () => {
    setCompactRatioDraft(String(compactRatioPercent));
    setCompactRatioCustomOpen(true);
  };

  const closeCompactRatioCustom = () => {
    setCompactRatioDraft(String(compactRatioPercent));
    setCompactRatioCustomOpen(false);
  };

  const selectCompactRatioPreset = async (ratio: number) => {
    if (Math.abs(compactRatio - ratio) < 0.0001) {
      closeCompactRatioCustom();
      return;
    }
    await persistCompactRatio(ratio);
  };

  const saveCompactRatioDraft = async () => {
    if (!compactRatioDraftValid || !compactRatioDraftDirty || busy) return;
    await persistCompactRatio(compactRatioDraftPercent / 100);
  };

  useEffect(() => {
    const generation = ++autoRefreshGenerationRef.current;
    let cancelled = false;
    const stale = () => cancelled || autoRefreshGenerationRef.current !== generation;
    if (subtab !== "usage") return;
    const groups = providerAccessGroups(s.providers.filter((p) => p.added), t);
    const candidates = groups
      .map((group) => {
        const provider = group.providers.find((p) => providerIsConfigured(p) && p.baseUrl);
        return provider ? { group, provider } : null;
      })
      .filter((item): item is { group: ProviderAccessGroup; provider: ProviderView } => Boolean(item));
    // The backend token covers provider identity, current catalog, headers,
    // and credential revision without persisting sensitive header values in
    // sessionStorage. Older payloads without the token simply skip this
    // opportunistic background refresh; manual refresh remains available.
    if (candidates.some(({ provider }) => !provider.modelCatalogFingerprint?.trim())) return;
    const refreshKey = candidates.map(({ group, provider }) => JSON.stringify([
      group.id,
      provider.modelCatalogFingerprint!.trim(),
    ])).join("|");
    if (!refreshKey || autoRefreshKeyRef.current === refreshKey) return;

    // Session-level cooldown per provider set: reopening the panel does not
    // refetch the same providers, while a changed set refreshes immediately.
    const autoRefreshStorageKey = `settings-auto-refresh-at:${refreshKey}`;
    const lastAutoRefresh = sessionStorage.getItem(autoRefreshStorageKey);
    if (lastAutoRefresh && Date.now() - Number(lastAutoRefresh) < 30_000) return;

    // Respect slow network hints; background model-list refresh can wait.
    if (shouldSkipAutoRefresh()) return;

    autoRefreshKeyRef.current = refreshKey;
    sessionStorage.setItem(autoRefreshStorageKey, String(Date.now()));

    void backgroundApply(async () => {
      // Batch-fetch models for all candidates in one round-trip.
      const providersToFetch = candidates.map((c) => c.provider).filter((p) => p.models && p.models.length > 0);
      let batchResults: Record<string, string[]> = {};
      try {
        batchResults = await app.FetchAllProviderModels(providersToFetch) as Record<string, string[]>;
      } catch {
        // Batch failed entirely — fall back to per-provider cached calls below.
      }
      if (stale()) return;

      const updates: ProviderModelCatalogUpdate[] = [];
      for (const { provider } of candidates) {
        if (stale()) return;
        if (!provider.models || provider.models.length === 0) continue;
        try {
          const fetched = batchResults[provider.name]
            ?? await cachedFetchProviderModels((p) => app.FetchProviderModels(p), provider);
          if (stale()) return;
          if (!fetched || fetched.length === 0) continue;
          const models = mergedFetchedProviderModels(provider.models, fetched, { preserveCurated: true });
          const currentDefault = providerDefaultModel(provider.default, models);
          const visionModels = provider.visionModels.filter((model) => models.includes(model));
          if (sameStringList(provider.models, models) && provider.default === currentDefault && sameStringList(provider.visionModels, visionModels)) continue;
          const expectedFingerprint = provider.modelCatalogFingerprint?.trim() ?? "";
          if (!expectedFingerprint) continue;
          updates.push({ name: provider.name, expectedFingerprint, models, default: currentDefault, visionModels });
        } catch {
          // Background discovery is opportunistic; manual refresh shows errors.
        }
      }
      if (updates.length > 0) {
        try {
          if (stale()) return;
          // Compare and apply narrow catalog updates in one transaction.
          await app.SaveProviderModelCatalogs(updates);
        } catch {
          // Background discovery is opportunistic; explicit edits show errors.
        }
      }
    });
    return () => {
      cancelled = true;
      if (autoRefreshGenerationRef.current === generation) autoRefreshGenerationRef.current += 1;
    };
  }, [backgroundApply, s.providers, subtab, t]);

  return (
    <>
      <div className="settings-subtabs">
        <button
          type="button"
          className={`settings-subtab${subtab === "usage" ? " settings-subtab--active" : ""}`}
          aria-selected={subtab === "usage"}
          onClick={() => setSubtab("usage")}
        >
          {t("settings.modelTab.usage")}
        </button>
        <button
          type="button"
          className={`settings-subtab${subtab === "access" ? " settings-subtab--active" : ""}`}
          aria-selected={subtab === "access"}
          onClick={() => setSubtab("access")}
        >
          {t("settings.modelTab.access")}
        </button>
        <button
          type="button"
          className={`settings-subtab${subtab === "stats" ? " settings-subtab--active" : ""}`}
          aria-selected={subtab === "stats"}
          onClick={() => setSubtab("stats")}
        >
          {t("settings.modelTab.stats")}
        </button>
      </div>

      {subtab === "usage" ? (
        <>
          <SettingsSection title={t("settings.modelUsage")}>
            <SettingsField label={t("settings.defaultModel")} hint={t("settings.defaultModelHint")}>
              <ModelPicker
                s={s}
                refs={refs}
                value={toRef(s.defaultModel, s)}
                disabled={busy}
                onPick={(ref) => void apply(() => app.SetDefaultModel(ref))}
              />
            </SettingsField>

            <SettingsField label={t("settings.plannerModel")}>
              <ModelPicker
                s={s}
                refs={refs}
                value={plannerSelectRef}
                disabled={busy}
                includeSameDefault
                onPick={(ref) => void apply(() => app.SetPlannerModel(ref))}
              />
            </SettingsField>

            <SettingsField label={t("settings.subagentModel")}>
              <ModelPicker
                s={s}
                refs={refs}
                value={subagentRef}
                disabled={busy}
                emptyOptionLabel={t("settings.subagentModelDefault")}
                emptyOptionHint={t("common.auto")}
                onPick={(ref) => void apply(() => app.SetSubagentModel(ref))}
              />
            </SettingsField>

            <SettingsField label={t("settings.subagentEffort")} hint={t("settings.subagentHint")}>
              <select
                className="mem-select set-grow"
                value={s.subagentEffort || ""}
                disabled={busy}
                onChange={(e) => void apply(() => app.SetSubagentEffort(e.target.value))}
              >
                <option value="">{t("settings.subagentEffortDefault")}</option>
                {EFFORT_PRESETS.map((level) => (
                  <option key={level} value={level}>
                    {level}
                  </option>
                ))}
              </select>
            </SettingsField>

            <SettingsField label={t("settings.subagentDepth")} hint={t("settings.subagentDepthHint")}>
              <div className="provider-add-segmented" role="group" aria-label={t("settings.subagentDepth")}>
                {[1, 2].map((depth) => (
                  <button
                    key={depth}
                    type="button"
                    className={subagentDepth === depth ? "provider-add-segmented__item provider-add-segmented__item--active" : "provider-add-segmented__item"}
                    disabled={busy}
                    aria-pressed={subagentDepth === depth}
                    onClick={() => void apply(() => app.SetMaxSubagentDepth(depth))}
                  >
                    {depth === 1 ? t("settings.subagentDepthOne") : t("settings.subagentDepthTwo")}
                  </button>
                ))}
              </div>
            </SettingsField>

            <SettingsField label={t("settings.subagentConcurrency")} hint={t("settings.subagentConcurrencyHint")}>
              <input
                className="mem-input"
                type="number"
                min={1}
                max={32}
                value={subagentConcurrency}
                disabled={busy}
                onChange={(e) => {
                  const n = Number(e.target.value);
                  if (!Number.isFinite(n)) return;
                  void apply(() => app.SetMaxSubagentConcurrency(n));
                }}
              />
            </SettingsField>

            <SettingsField label={t("settings.parallelWriters")} hint={t("settings.parallelWritersHint")}>
              <input
                className="mem-input"
                type="number"
                min={1}
                max={subagentConcurrency}
                value={parallelWriters}
                disabled={busy}
                onChange={(e) => {
                  const n = Number(e.target.value);
                  if (!Number.isFinite(n)) return;
                  void apply(() => app.SetMaxParallelWriters(n));
                }}
              />
            </SettingsField>

            {modelIssue && <div className="provider-fetch-banner provider-fetch-banner--warn">{modelIssue}</div>}
          </SettingsSection>
          <SettingsSection title={t("settings.agentRuntime")} description={t("settings.agentRuntimeHint")}>
            <SettingsField label={t("settings.reasoningLanguage")} hint={t("settings.reasoningLanguageHint")}>
              <div className="set-seg">
                {(["auto", "zh", "en"] as const).map((lang) => (
                  <button
                    key={lang}
                    className={`set-seg__btn${agent.reasoningLanguage === lang ? " set-seg__btn--on" : ""}`}
                    disabled={busy}
                    onClick={() => void apply(() => app.SetReasoningLanguage(lang))}
                  >
                    {t(`settings.reasoningLanguage.${lang}`)}
                  </button>
                ))}
              </div>
            </SettingsField>
            <SettingsField label={t("settings.compactRatio")} hint={t("settings.compactRatioHint")} stacked>
              <div className="compact-ratio-controls">
                <div className="set-seg compact-ratio-presets" role="group" aria-label={t("settings.compactRatio")}>
                  {COMPACT_RATIO_PRESETS.map(([ratio, labelKey]) => (
                    <button
                      key={ratio}
                      type="button"
                      className={`set-seg__btn${Math.abs(compactRatio - ratio) < 0.0001 ? " set-seg__btn--on" : ""}`}
                      disabled={busy}
                      aria-label={t(labelKey)}
                      aria-pressed={Math.abs(compactRatio - ratio) < 0.0001}
                      onClick={() => void selectCompactRatioPreset(ratio)}
                    >
                      <span className="compact-ratio-preset__percent" aria-hidden="true">{Math.round(ratio * 100)}%</span>
                      <span className="compact-ratio-preset__caption" aria-hidden="true">{t(labelKey).split(" · ")[1]}</span>
                    </button>
                  ))}
                </div>
                <div className="compact-ratio-summary">
                  <div className="compact-ratio-current">{t("settings.compactRatioCurrent", { value: compactRatioSelection })}</div>
                  <button
                    type="button"
                    className="btn btn--small compact-ratio-custom-toggle"
                    disabled={busy}
                    aria-expanded={compactRatioCustomOpen}
                    aria-controls="settings-compact-ratio-custom-panel"
                    onClick={compactRatioCustomOpen ? closeCompactRatioCustom : openCompactRatioCustom}
                  >
                    {t("settings.compactRatioCustomOption")}
                  </button>
                </div>
                <div className="compact-ratio-impact">{compactRatioImpact}</div>
                {compactRatioCustomOpen && (
                  <div id="settings-compact-ratio-custom-panel" className="compact-ratio-custom-panel">
                    <div className="settings-inline-controls compact-ratio-custom">
                      <label className="set-label" htmlFor="settings-compact-ratio-custom">{t("settings.compactRatioCustom")}</label>
                      <input
                        ref={compactRatioCustomInputRef}
                        id="settings-compact-ratio-custom"
                        className="mem-input set-narrow"
                        type="number"
                        min={65}
                        max={85}
                        step={0.1}
                        inputMode="decimal"
                        value={compactRatioDraft}
                        disabled={busy}
                        aria-label={t("settings.compactRatioCustomAria")}
                        aria-describedby="settings-compact-ratio-custom-hint"
                        aria-invalid={!compactRatioDraftValid}
                        onInput={(event) => setCompactRatioDraft(event.currentTarget.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter") {
                            event.preventDefault();
                            void saveCompactRatioDraft();
                          }
                          if (event.key === "Escape") {
                            event.preventDefault();
                            closeCompactRatioCustom();
                          }
                        }}
                      />
                      <span className="compact-ratio-custom__suffix" aria-hidden="true">%</span>
                      <button
                        type="button"
                        className="btn btn--small"
                        disabled={busy || !compactRatioDraftValid || !compactRatioDraftDirty}
                        onClick={() => void saveCompactRatioDraft()}
                      >
                        {t("settings.compactRatioApply")}
                      </button>
                      <button type="button" className="btn btn--small" disabled={busy} onClick={closeCompactRatioCustom}>
                        {t("common.cancel")}
                      </button>
                    </div>
                    <div
                      id="settings-compact-ratio-custom-hint"
                      className={`compact-ratio-custom__hint${compactRatioDraftValid ? "" : " compact-ratio-custom__hint--invalid"}`}
                    >
                      {t("settings.compactRatioCustomHint")}
                    </div>
                  </div>
                )}
              </div>
            </SettingsField>
            {compactRatioOverrideHint && <div className="provider-fetch-banner provider-fetch-banner--warn">{compactRatioOverrideHint}</div>}
          </SettingsSection>
        </>
      ) : subtab === "access" ? (
        <ProvidersSection s={s} busy={busy} apply={apply} />
      ) : (
        <Suspense fallback={<div className="empty">{t("settings.loading")}</div>}>
          <UsageStatsPanel />
        </Suspense>
      )}
    </>
  );
}

type ModelPickerOption = {
  ref: string;
  provider: string;
  model: string;
  providerView?: ProviderView;
};

export function ModelPicker({
  s,
  refs,
  value,
  disabled,
  includeSameDefault = false,
  ariaLabel,
  emptyOptionLabel,
  emptyOptionHint,
  onPick,
}: {
  s: SettingsView;
  refs: string[];
  value: string;
  disabled: boolean;
  includeSameDefault?: boolean;
  ariaLabel?: string;
  emptyOptionLabel?: string;
  emptyOptionHint?: string;
  onPick: (ref: string) => void;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const triggerRef = useRef<HTMLButtonElement>(null);
  // Debounce search to avoid expensive filtering on every keystroke
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 150);
    return () => clearTimeout(timer);
  }, [query]);
  const q = debouncedQuery.trim().toLowerCase();
  const emptyLabel = includeSameDefault ? t("settings.plannerNone") : emptyOptionLabel;
  const emptyHint = includeSameDefault ? t("settings.plannerNoneHint") : emptyOptionHint;
  const emptyMeta = includeSameDefault ? t("settings.plannerNoneHintShort") : emptyOptionHint;
  const selected = refs.includes(value) ? modelOptionFromRef(value, s) : null;
  const selectedLabel = value === "" && emptyLabel
    ? emptyLabel
    : selected?.model || value || t("common.none");
  const selectedMeta = value === "" && emptyLabel
    ? emptyMeta || ""
    : selected
    ? modelOptionMeta(selected, t)
    : t("settings.noModelsConfigured");
  const emptyOptionVisible = Boolean(emptyLabel) && (!q || `${emptyLabel} ${emptyHint || ""}`.toLowerCase().includes(q));

  const groups = useMemo(() => {
    const providerOrder: string[] = [];
    const providerSeen = new Set<string>();
    for (const p of s.providers) {
      const id = providerGroupID(p);
      if (!providerSeen.has(id)) {
        providerOrder.push(id);
        providerSeen.add(id);
      }
    }
    const options = refs
      .map((ref) => modelOptionFromRef(ref, s))
      .filter((opt): opt is ModelPickerOption => Boolean(opt))
      .filter((opt) => !q || `${opt.ref} ${opt.provider} ${modelProviderLabel(opt.provider, opt.providerView, t)} ${opt.model}`.toLowerCase().includes(q));
    for (const opt of options) {
      const groupID = modelOptionGroupID(opt);
      if (!providerSeen.has(groupID)) {
        providerOrder.push(groupID);
        providerSeen.add(groupID);
      }
    }
    return providerOrder
      .map((groupID) => {
        const providerViews = s.providers.filter((p) => providerGroupID(p) === groupID);
        const firstProvider = providerViews[0];
        return {
          groupID,
          label: firstProvider ? providerGroupLabel(firstProvider, t) : groupID,
          keySet: providerViews.some((p) => p.keySet),
          requiresKey: providerViews.every((p) => providerRequiresKey(p)),
          options: uniqueModelOptions(options.filter((opt) => modelOptionGroupID(opt) === groupID)),
        };
      })
      .filter((group) => group.options.length > 0);
  }, [q, refs, s, t]);

  useEffect(() => {
    if (!open) setQuery("");
  }, [open]);

  const pick = (ref: string) => {
    setOpen(false);
    if (ref !== value) onPick(ref);
  };

  return (
    <div className="settings-model-picker">
      <button
        ref={triggerRef}
        type="button"
        className="settings-model-picker__trigger"
        disabled={disabled || (!includeSameDefault && !emptyOptionLabel && refs.length === 0)}
        aria-label={ariaLabel}
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((next) => !next)}
      >
        <span className="settings-model-picker__selected">
          <span>{selectedLabel}</span>
          <small>{selectedMeta}</small>
        </span>
        <ChevronDown size={16} className={`settings-model-picker__chev${open ? " settings-model-picker__chev--open" : ""}`} />
      </button>
      <AnchoredPopover
        open={open && !disabled}
        anchorRef={triggerRef}
        onClose={() => setOpen(false)}
        className="settings-model-picker__menu"
        placement="bottom"
        style={{ width: triggerRef.current?.getBoundingClientRect().width }}
      >
        <div className="settings-model-picker__search">
          <input
            value={query}
            placeholder={t("settings.searchModels")}
            onChange={(e) => setQuery(e.target.value)}
            autoFocus
          />
        </div>
        <div className="settings-model-picker__list" role="listbox">
          {emptyOptionVisible && (
            <button
              type="button"
              role="option"
              aria-selected={value === ""}
              className={`settings-model-picker__option settings-model-picker__option--pinned${value === "" ? " settings-model-picker__option--selected" : ""}`}
              onClick={() => pick("")}
            >
              <span>
                <strong>{emptyLabel}</strong>
                {emptyHint && <small>{emptyHint}</small>}
              </span>
              {value === "" && <Check size={14} />}
            </button>
          )}
          {groups.map((group) => (
            <div className="settings-model-picker__group" key={group.groupID}>
              <div className="settings-model-picker__group-title">
                <span>{group.label}</span>
                <small>{providerKeyStatusLabel(group, t)}</small>
              </div>
              {group.options.map((opt) => (
                <button
                  key={opt.ref}
                  type="button"
                  role="option"
                  aria-selected={opt.ref === value}
                  className={`settings-model-picker__option${opt.ref === value ? " settings-model-picker__option--selected" : ""}`}
                  onClick={() => pick(opt.ref)}
                >
                  <span>
                    <strong>{opt.model}</strong>
                    <small>{modelOptionMeta(opt, t)}</small>
                  </span>
                  {opt.ref === value && <Check size={14} />}
                </button>
              ))}
            </div>
          ))}
          {!emptyOptionVisible && groups.length === 0 && <div className="settings-model-picker__empty">{t("settings.noMatchingModels")}</div>}
        </div>
      </AnchoredPopover>
    </div>
  );
}

function modelOptionFromRef(ref: string, s: SettingsView): ModelPickerOption | null {
  if (!ref) return null;
  const [provider, ...modelParts] = ref.split("/");
  const model = modelParts.join("/") || ref;
  return {
    ref,
    provider,
    model,
    providerView: s.providers.find((p) => p.name === provider),
  };
}

function modelOptionMeta(option: ModelPickerOption, t: ReturnType<typeof useT>): string {
  const key = option.providerView ? providerKeyStatusLabel(option.providerView, t) : t("settings.noKey");
  return `${modelProviderLabel(option.provider, option.providerView, t)} · ${key}`;
}

function providerKeyStatusLabel(provider: { keySet: boolean; requiresKey?: boolean; apiKeyEnv?: string }, t: ReturnType<typeof useT>): string {
  if (!providerRequiresKey(provider)) return t("settings.noKeyRequired");
  return provider.keySet ? t("settings.keySet") : t("settings.noKey");
}

function modelProviderLabel(provider: string, providerView: ProviderView | undefined, t: ReturnType<typeof useT>): string {
  return providerView ? providerGroupLabel(providerView, t) : provider;
}

function modelOptionGroupID(option: ModelPickerOption): string {
  return option.providerView ? providerGroupID(option.providerView) : `custom:${option.provider}`;
}

function uniqueModelOptions(options: ModelPickerOption[]): ModelPickerOption[] {
  const seen = new Set<string>();
  const out: ModelPickerOption[] = [];
  for (const option of options) {
    if (seen.has(option.model)) continue;
    seen.add(option.model);
    out.push(option);
  }
  return out;
}

function sameStringList(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  return a.every((value, i) => value === b[i]);
}

function proxyModeLabel(mode: ProxyMode, t: ReturnType<typeof useT>): string {
  switch (mode) {
    case "auto":
      return t("settings.proxyMode.auto");
    case "custom":
      return t("settings.proxyMode.custom");
    case "off":
      return t("settings.proxyMode.off");
  }
}

function ProvidersSection({ s, busy, apply }: SectionProps) {
  const t = useT();
  const defaultProvider = toRef(s.defaultModel, s).split("/")[0];
  const [editing, setEditing] = useState<string | null>(null);
  const [adding, setAdding] = useState<AddProviderMode>(null);
  const [revealedProvider, setRevealedProvider] = useState<string | null>(null);
  const [fetchingProviders, setFetchingProviders] = useState<Set<string>>(() => new Set());
  const fetchGate = useMemo(createLatestRequestGate, []);
  const [fetchResults, setFetchResults] = useState<Record<string, ProviderFetchResult>>({});
  const [modelDrafts, setModelDrafts] = useState<Record<string, ProviderModelDraft>>({});
  const visibleProviders = useMemo(() => s.providers.filter((p) => p.added || p.name === revealedProvider), [s.providers, revealedProvider]);
  const groups = useMemo(() => providerAccessGroups(visibleProviders, t), [visibleProviders, t]);

  useEffect(() => {
    if (revealedProvider && !s.providers.some((p) => p.name === revealedProvider)) {
      setRevealedProvider(null);
      if (editing === revealedProvider) setEditing(null);
    }
  }, [editing, revealedProvider, s.providers]);

  const setGroupFetchResult = (groupID: string, result: ProviderFetchResult | null) => {
    setFetchResults((prev) => {
      const next = { ...prev };
      if (result) next[groupID] = result;
      else delete next[groupID];
      return next;
    });
  };

  const setGroupModelDraft = (groupID: string, draft: ProviderModelDraft | null) => {
    setModelDrafts((prev) => {
      const next = { ...prev };
      if (draft) next[groupID] = draft;
      else delete next[groupID];
      return next;
    });
  };

  const beginGroupFetch = (groupID: string): number => {
    const generation = fetchGate.begin(groupID);
    setFetchingProviders((current) => {
      if (current.has(groupID)) return current;
      const next = new Set(current);
      next.add(groupID);
      return next;
    });
    return generation;
  };

  const groupFetchIsCurrent = (groupID: string, generation: number): boolean => (
    fetchGate.isCurrent(groupID, generation)
  );

  const finishGroupFetch = (groupID: string, generation: number) => {
    if (!groupFetchIsCurrent(groupID, generation)) return;
    setFetchingProviders((current) => {
      if (!current.has(groupID)) return current;
      const next = new Set(current);
      next.delete(groupID);
      return next;
    });
  };

  const cancelGroupFetch = (groupID: string) => {
    fetchGate.cancel(groupID);
    setFetchingProviders((current) => {
      if (!current.has(groupID)) return current;
      const next = new Set(current);
      next.delete(groupID);
      return next;
    });
  };

  const modelDraftForFetch = (p: ProviderView, fetched: string[]): ProviderModelDraft => {
    const candidates = providerModelCandidates(p.models, fetched);
    const selected = mergedFetchedProviderModels(p.models, fetched, { preserveCurated: true });
    const visionCapability = providerVisionCapabilityForView(p);
    const visionSource = visionCapability === "unsupported"
      ? []
      : (p.visionModelsConfigured ? p.visionModels : inferredVisionModels(candidates));
    return {
      providerName: p.name,
      candidates,
      selected: candidates.filter((model) => selected.includes(model)),
      visionModels: candidates.filter((model) => visionSource.includes(model)),
      visionCapability,
    };
  };

  const updateModelDraftSelection = (groupID: string, nextSelected: (draft: ProviderModelDraft) => string[]) => {
    setModelDrafts((prev) => {
      const draft = prev[groupID];
      if (!draft) return prev;
      const selectedSet = new Set(nextSelected(draft));
      return {
        ...prev,
        [groupID]: {
          ...draft,
          selected: draft.candidates.filter((model) => selectedSet.has(model)),
        },
      };
    });
  };

  const toggleModelDraftVision = (groupID: string, model: string) => {
    setModelDrafts((prev) => {
      const draft = prev[groupID];
      if (!draft) return prev;
      return {
        ...prev,
        [groupID]: {
          ...draft,
          visionModels: draft.visionModels.includes(model)
            ? draft.visionModels.filter((candidate) => candidate !== model)
            : draft.candidates.filter((candidate) => candidate === model || draft.visionModels.includes(candidate)),
        },
      };
    });
  };

  const refreshModels = async (group: ProviderAccessGroup, p: ProviderView) => {
    const generation = beginGroupFetch(group.id);
    setGroupFetchResult(group.id, null);
    setGroupModelDraft(group.id, null);
    try {
      let fetched: string[];
      try {
        fetched = await cachedFetchProviderModels((provider) => app.FetchProviderModels(provider), p, true);
      } catch (e) {
        if (!groupFetchIsCurrent(group.id, generation)) return;
        setGroupFetchResult(group.id, {
          kind: "warn",
          text: t("settings.fetchModelsFailedForProvider", { provider: group.label, err: String((e as Error)?.message ?? e) }),
        });
        return;
      }
      if (!groupFetchIsCurrent(group.id, generation)) return;
      if (fetched.length === 0) {
        setGroupFetchResult(group.id, {
          kind: "warn",
          text: t("settings.fetchModelsEmptyForProvider", { provider: group.label }),
        });
        return;
      }
      const draft = modelDraftForFetch(p, fetched);
      startTransition(() => {
        setGroupModelDraft(group.id, draft);
        setGroupFetchResult(group.id, {
          kind: "ok",
          text: t("settings.fetchModelsReadyForProvider", { provider: group.label, n: draft.candidates.length }),
        });
      });
    } finally {
      finishGroupFetch(group.id, generation);
    }
  };

  const saveKeyEnvAndAutoRefresh = async (group: ProviderAccessGroup, apiKeyEnv: string, value: string) => {
    const probe = group.providers[0];
    if (!probe || !apiKeyEnv) return;
    const generation = beginGroupFetch(group.id);
    setGroupFetchResult(group.id, null);
    setGroupModelDraft(group.id, null);
    try {
      await apply(async () => {
        await app.SaveProviderKey(apiKeyEnv, value);
        invalidateProviderCacheByAPIKeyEnv(apiKeyEnv);
        try {
          const fetched = await cachedFetchProviderModels((provider) => app.FetchProviderModels(provider), { ...probe, apiKeyEnv });
          if (!groupFetchIsCurrent(group.id, generation)) return;
          if (fetched.length > 0) {
            const draft = modelDraftForFetch({ ...probe, apiKeyEnv }, fetched);
            setGroupModelDraft(group.id, draft);
            setGroupFetchResult(group.id, {
              kind: "ok",
              text: t("settings.fetchModelsReadyForProvider", { provider: group.label, n: draft.candidates.length }),
            });
            return;
          }
          setGroupFetchResult(group.id, {
            kind: "warn",
            text: t("settings.fetchModelsEmptyForProvider", { provider: group.label }),
          });
        } catch (e) {
          if (!groupFetchIsCurrent(group.id, generation)) return;
          setGroupFetchResult(group.id, {
            kind: "warn",
            text: t("settings.fetchModelsAfterKeyFailedForProvider", { provider: group.label, err: String((e as Error)?.message ?? e) }),
          });
        }
      });
    } finally {
      finishGroupFetch(group.id, generation);
    }
  };

  const saveProviderKey = async (group: ProviderAccessGroup, apiKeyEnv: string, value: string) => {
    if (!apiKeyEnv) return;
    cancelGroupFetch(group.id);
    setGroupFetchResult(group.id, null);
    setGroupModelDraft(group.id, null);
    await apply(async () => {
      const warning = await app.SetProviderKey(apiKeyEnv, value);
      invalidateProviderCacheByAPIKeyEnv(apiKeyEnv);
      return warning;
    });
  };

  const clearProviderKey = async (group: ProviderAccessGroup, apiKeyEnv: string) => {
    if (!apiKeyEnv) return;
    cancelGroupFetch(group.id);
    await apply(async () => {
      await app.ClearProviderKey(apiKeyEnv);
      invalidateProviderCacheByAPIKeyEnv(apiKeyEnv);
    });
  };

  const saveProvider = async (provider: ProviderView, key: string) => {
    if (key) {
      const warning = await app.SaveProviderWithKey(provider, key);
      invalidateProviderCacheByAPIKeyEnv(provider.apiKeyEnv);
      return warning;
    }
    await app.SaveProvider(provider);
  };

  const saveModelDraft = async (group: ProviderAccessGroup) => {
    const draft = modelDrafts[group.id];
    const provider = draft ? group.providers.find((p) => p.name === draft.providerName) : null;
    const models = uniqueStrings(draft?.selected ?? []);
    const visionModels = uniqueStrings(draft?.visionModels ?? []).filter((model) => models.includes(model));
    if (!draft || !provider || models.length === 0) return;
    let saved = false;
    await apply(async () => {
      await app.SaveProvider({
        ...provider,
        models,
        visionModels: draft.visionCapability === "unsupported" ? [] : visionModels,
        visionModelsConfigured: true,
        default: providerDefaultModel(provider.default, models),
      });
      saved = true;
    });
    if (!saved) return;
    setGroupModelDraft(group.id, null);
    setGroupFetchResult(group.id, {
      kind: "ok",
      text: t("settings.enabledModelsSavedForProvider", { provider: group.label, n: models.length }),
    });
  };

  return (
    <SettingsSection
      title={t("settings.providerAccess")}
      description={t("settings.providerAccessHint")}
      actions={
        <button className="btn btn--small" disabled={busy || adding !== null} onClick={() => setAdding("official")}>
          {t("settings.addProvider")}
        </button>
      }
    >
      <div className="provider-access-grid">
        {groups.length === 0 && adding === null && (
          <div className="provider-empty">
            <strong>{t("settings.providerAccessEmptyTitle")}</strong>
            <span>{t("settings.providerAccessEmptyHint")}</span>
            <div className="provider-empty__actions">
              <button type="button" className="btn btn--small" disabled={busy} onClick={() => setAdding("official")}>
                {t("settings.addProvider.officialChoice")}
              </button>
              <button type="button" className="btn btn--small" disabled={busy} onClick={() => setAdding("custom")}>
                {t("settings.addProvider.customChoice")}
              </button>
            </div>
          </div>
        )}
        {adding !== null && (
          <AddProviderPanel
            mode={adding}
            kinds={s.providerKinds}
            officialProviders={s.officialProviders}
            providerPresets={s.providerPresets}
            busy={busy}
            onMode={setAdding}
            onCancel={() => setAdding(null)}
            onAddOfficial={(kind, key) => apply(() => app.AddOfficialProviderAccess(kind, key)).then(() => setAdding(null))}
            onAddPreset={(id, key) => apply(() => app.AddProviderPresetAccess(id, key)).then(() => setAdding(null))}
            onViewPresetConflict={(providerName) => {
              setRevealedProvider(providerName);
              setEditing(providerName);
              setAdding(null);
            }}
            onResetPreset={(id) => apply(() => app.ResetProviderPresetAccess(id)).then(() => setAdding(null))}
            onAddCustom={(pv, key) => apply(() => saveProvider(pv, key ?? "")).then(() => setAdding(null))}
          />
        )}
        {adding === null && groups.map((group) => (
          <ProviderAccessCard
            key={group.id}
            group={group}
            busy={busy}
            fetching={fetchingProviders.has(group.id)}
            fetchResult={fetchResults[group.id]}
            modelDraft={modelDrafts[group.id]}
            defaultProvider={defaultProvider}
            editing={editing}
            kinds={s.providerKinds}
            onEdit={setEditing}
            onCancelEdit={() => setEditing(null)}
            onSave={(pv, key) => {
              cancelGroupFetch(group.id);
              return apply(() => saveProvider(pv, key ?? "")).then(() => {
                setEditing(null);
                setGroupModelDraft(group.id, null);
              });
            }}
            onRefresh={(provider) => void refreshModels(group, provider)}
            onToggleDraftModel={(model) => updateModelDraftSelection(group.id, (draft) => (
              draft.selected.includes(model)
                ? draft.selected.filter((candidate) => candidate !== model)
                : [...draft.selected, model]
            ))}
            onToggleDraftVision={(model) => toggleModelDraftVision(group.id, model)}
            onSelectAllDraftModels={() => updateModelDraftSelection(group.id, (draft) => draft.candidates)}
            onClearDraftModels={() => updateModelDraftSelection(group.id, () => [])}
            onCancelDraftModels={() => {
              setGroupModelDraft(group.id, null);
              setGroupFetchResult(group.id, null);
            }}
            onSaveDraftModels={() => void saveModelDraft(group)}
            onToggleWebSearch={(enabled) => {
              const providerNames = group.providers.map((provider) => provider.name);
              if (providerNames.length === 0) return;
              void apply(() => app.SetProviderWebSearch(providerNames, enabled));
            }}
            onUpgradeRecommended={(name) => {
              cancelGroupFetch(group.id);
              return apply(() => app.UpgradeDeepSeekProviderAccess(name)).then((upgraded) => {
                if (upgraded) {
                  setEditing(null);
                  setGroupModelDraft(group.id, null);
                }
              });
            }}
            onSaveEditorKey={(env, value) => group.builtIn ? saveProviderKey(group, env, value) : saveKeyEnvAndAutoRefresh(group, env, value)}
            onClearEditorKey={(env) => clearProviderKey(group, env)}
            onDelete={(providers) => {
              cancelGroupFetch(group.id);
              const providerNames = providers.map(({ name }) => name);
              return apply(() => app.RemoveProviderAccesses(providerNames)).then(() => {
                if (revealedProvider && providerNames.includes(revealedProvider)) {
                  setRevealedProvider(null);
                  setEditing(null);
                }
              });
            }}
          />
        ))}
      </div>
    </SettingsSection>
  );
}

export type ProviderAccessGroup = {
  id: string;
  label: string;
  description: string;
  builtIn: boolean;
  providers: ProviderView[];
  apiKeyEnv: string;
  keySet: boolean;
  requiresKey: boolean;
  configured: boolean;
  keySource?: string;
  keySourcePath?: string;
  baseUrl: string;
  kind: string;
  models: string[];
  recommendedUpgradeAvailable: boolean;
};

type ProviderFetchResult = {
  kind: "ok" | "warn";
  text: string;
};

type ProviderModelDraft = {
  providerName: string;
  candidates: string[];
  selected: string[];
  visionModels: string[];
  visionCapability: ProviderVisionCapability;
};

type AddProviderMode = null | "official" | "custom";
type OfficialProviderKind = "deepseek";

const OFFICIAL_PROVIDER_CHOICES: Array<{ kind: OfficialProviderKind; labelKey: DictKey; descKey: DictKey; keyEnv: string }> = [
  { kind: "deepseek", labelKey: "settings.addProvider.official.deepseek", descKey: "settings.addProvider.official.deepseekDesc", keyEnv: "DEEPSEEK_API_KEY" },
];

type ProviderTemplateChoice =
  | { id: string; source: "official"; kind: OfficialProviderKind; label: string; description: string; keyEnv: string; added: boolean; keySet: boolean }
  | { id: string; source: "preset"; presetID: string; label: string; description: string; keyEnv: string; added: boolean; status: ProviderPresetStatus; statusProviderNames: string[]; keySet: boolean };

function providerTemplateCanAdd(choice: ProviderTemplateChoice | undefined): boolean {
  if (!choice) return false;
  if (choice.source === "official") return !choice.added;
  return choice.status !== "installed" && choice.status !== "installed_modified" && choice.status !== "name_conflict";
}

function providerTemplateStatusBadge(choice: ProviderTemplateChoice, t: ReturnType<typeof useT>): string {
  if (choice.source === "official") return choice.added ? t("settings.addProvider.addedBadge") : "";
  if (choice.status === "installed") return t("settings.addProvider.addedBadge");
  if (choice.status === "installed_modified") return t("settings.addProvider.modifiedBadge");
  if (choice.status === "name_conflict") return t("settings.addProvider.nameConflictBadge");
  if (choice.status === "similar_existing") return t("settings.addProvider.similarExistingBadge");
  return "";
}

function providerTemplateActionLabel(choice: ProviderTemplateChoice | undefined, t: ReturnType<typeof useT>): string {
  if (!choice) return t("settings.addProvider.confirm");
  if (choice.source === "preset" && choice.status === "name_conflict") return t("settings.addProvider.nameConflictAction");
  if (!providerTemplateCanAdd(choice)) return t("settings.addProvider.alreadyAddedAction");
  return t("settings.addProvider.confirm");
}

function providerTemplateStatusClass(choice: ProviderTemplateChoice): string {
  if (choice.source !== "preset" || choice.status === "available") return "";
  return ` provider-template-card--${choice.status.split("_").join("-")}`;
}

function providerTemplateConflictProviderName(choice: ProviderTemplateChoice): string {
  if (choice.source !== "preset" || (choice.status !== "name_conflict" && choice.status !== "installed_modified")) return "";
  return choice.statusProviderNames[0] ?? "";
}

function providerPresetDescription(preset: ProviderPresetView, t: ReturnType<typeof useT>): string {
  switch (preset.id) {
    case "deepseek-responses":
      return t("settings.addProvider.preset.deepseekResponsesDesc");
    case "longcat-openai":
      return t("settings.addProvider.preset.longcatOpenAIDesc");
    case "longcat-anthropic":
      return t("settings.addProvider.preset.longcatAnthropicDesc");
    case "token-rhythm":
      return t("settings.addProvider.preset.tokenRhythmDesc");
    case "kimi-cn":
      return t("settings.addProvider.preset.kimiCnDesc");
    case "kimi-global":
      return t("settings.addProvider.preset.kimiGlobalDesc");
    case "kimi-coding-plan":
      return t("settings.addProvider.preset.kimiCodingPlanDesc");
    case "mimo-api":
      return t("settings.addProvider.preset.mimoApiDesc");
    case "mimo-anthropic":
      return t("settings.addProvider.preset.mimoAnthropicDesc");
    case "mimo-token-plan-cn":
      return t("settings.addProvider.preset.mimoTokenPlanCnDesc");
    case "mimo-token-plan-cn-anthropic":
      return t("settings.addProvider.preset.mimoTokenPlanCnAnthropicDesc");
    case "mimo-token-plan-sgp":
      return t("settings.addProvider.preset.mimoTokenPlanSgpDesc");
    case "mimo-token-plan-sgp-anthropic":
      return t("settings.addProvider.preset.mimoTokenPlanSgpAnthropicDesc");
    case "mimo-token-plan-ams":
      return t("settings.addProvider.preset.mimoTokenPlanAmsDesc");
    case "mimo-token-plan-ams-anthropic":
      return t("settings.addProvider.preset.mimoTokenPlanAmsAnthropicDesc");
    case "minimax-cn-api":
      return t("settings.addProvider.preset.minimaxCnApiDesc");
    case "minimax-global-api":
      return t("settings.addProvider.preset.minimaxGlobalApiDesc");
    case "minimax-cn-anthropic":
      return t("settings.addProvider.preset.minimaxCnAnthropicDesc");
    case "minimax-global-anthropic":
      return t("settings.addProvider.preset.minimaxGlobalAnthropicDesc");
    case "glm-cn":
      return t("settings.addProvider.preset.glmCnDesc");
    case "zai-global":
      return t("settings.addProvider.preset.zaiGlobalDesc");
    case "glm-coding-plan-cn":
      return t("settings.addProvider.preset.glmCodingPlanCnDesc");
    case "glm-coding-plan-cn-anthropic":
      return t("settings.addProvider.preset.glmCodingPlanCnAnthropicDesc");
    case "zai-coding-plan-global":
      return t("settings.addProvider.preset.zaiCodingPlanGlobalDesc");
    case "zai-coding-plan-global-anthropic":
      return t("settings.addProvider.preset.zaiCodingPlanGlobalAnthropicDesc");
    case "opencode-go": case "opencode-go-anthropic":
    case "opencode-go-deepseek-anthropic": case "opencode-go-deepseek-responses":
      return t(opencodeGoPresetDescriptionKeys[preset.id]);
    case "opencode-zen-anthropic":
      return t("settings.addProvider.preset.opencodeZenAnthropicDesc");
    case "qwen-cn":
      return t("settings.addProvider.preset.qwenCnDesc");
    case "qwen-global":
      return t("settings.addProvider.preset.qwenGlobalDesc");
    case "qwen-coding-plan-cn":
      return t("settings.addProvider.preset.qwenCodingPlanCnDesc");
    case "qwen-coding-plan-cn-anthropic":
      return t("settings.addProvider.preset.qwenCodingPlanCnAnthropicDesc");
    case "qwen-coding-plan-global":
      return t("settings.addProvider.preset.qwenCodingPlanGlobalDesc");
    case "qwen-coding-plan-global-anthropic":
      return t("settings.addProvider.preset.qwenCodingPlanGlobalAnthropicDesc");
    case "stepfun":
      return t("settings.addProvider.preset.stepfunDesc");
    case "stepfun-anthropic":
      return t("settings.addProvider.preset.stepfunAnthropicDesc");
    case "novita":
      return t("settings.addProvider.preset.novitaDesc");
    case "gmi":
      return t("settings.addProvider.preset.gmiDesc");
    case "vercel-ai-gateway":
      return t("settings.addProvider.preset.vercelAiGatewayDesc");
    case "huggingface":
      return t("settings.addProvider.preset.huggingfaceDesc");
    case "nvidia":
      return t("settings.addProvider.preset.nvidiaDesc");
    case "kilocode":
      return t("settings.addProvider.preset.kilocodeDesc");
    case "ollama-cloud":
      return t("settings.addProvider.preset.ollamaCloudDesc");
    default:
      return preset.description;
  }
}

function providerPresetLabel(preset: ProviderPresetView, t: ReturnType<typeof useT>): string {
  switch (preset.id) {
    case "deepseek-responses":
      return t("settings.addProvider.preset.deepseekResponsesLabel");
    case "token-rhythm":
      return t("settings.addProvider.preset.tokenRhythmLabel");
    default:
      return preset.label;
  }
}

export function AddProviderPanel({
  mode,
  kinds,
  officialProviders,
  providerPresets,
  busy,
  onMode,
  onCancel,
  onAddOfficial,
  onAddPreset,
  onViewPresetConflict,
  onResetPreset,
  onAddCustom,
}: {
  mode: AddProviderMode; kinds: string[]; officialProviders: ProviderView[];
  providerPresets: ProviderPresetView[];
  busy: boolean;
  onMode: (mode: AddProviderMode) => void;
  onCancel: () => void;
  onAddOfficial: (kind: OfficialProviderKind, key: string) => Promise<void>;
  onAddPreset: (id: string, key: string) => Promise<void>;
  onViewPresetConflict: (providerName: string) => void;
  onResetPreset: (id: string) => Promise<void>;
  onAddCustom: (p: ProviderView, key?: string) => void | Promise<void>;
}) {
  const t = useT();
  const templateChoices = useMemo<ProviderTemplateChoice[]>(() => [
    ...OFFICIAL_PROVIDER_CHOICES.map((choice) => {
      const state = officialProviders.find((provider) => officialProviderKind(provider) === choice.kind);
      return {
        id: `official:${choice.kind}`,
        source: "official" as const, kind: choice.kind,
        label: t(choice.labelKey), description: t(choice.descKey),
        keyEnv: state?.apiKeyEnv || choice.keyEnv,
        added: Boolean(state?.added), keySet: Boolean(state?.keySet),
      };
    }),
    ...providerPresets.map((preset) => ({
      id: `preset:${preset.id}`,
      source: "preset" as const,
      presetID: preset.id,
      label: providerPresetLabel(preset, t),
      description: providerPresetDescription(preset, t),
      keyEnv: preset.keyEnv,
      added: preset.added,
      status: normalizeProviderPresetStatus(preset.status, preset.added),
      statusProviderNames: asArray(preset.statusProviderNames),
      keySet: preset.keySet,
    })),
  ], [officialProviders, providerPresets, t]);
  const [templateID, setTemplateID] = useState("official:deepseek");
  const [key, setKey] = useState("");
  const firstAvailableTemplateID = templateChoices.find(providerTemplateCanAdd)?.id ?? templateChoices[0]?.id ?? "";
  const selected = templateChoices.find((choice) => choice.id === templateID) ?? templateChoices.find((choice) => choice.id === firstAvailableTemplateID) ?? templateChoices[0];
  useEffect(() => {
    const current = templateChoices.find((choice) => choice.id === templateID);
    if (firstAvailableTemplateID && (!current || (!providerTemplateCanAdd(current) && firstAvailableTemplateID !== templateID))) {
      setTemplateID(firstAvailableTemplateID);
    }
  }, [firstAvailableTemplateID, templateChoices, templateID]);

  const header = (
    <div className="provider-add-panel__head">
      <div>
        <strong>{t("settings.addProvider.chooseTitle")}</strong>
        <span>{t("settings.addProvider.chooseHint")}</span>
      </div>
      <button type="button" className="btn btn--small" disabled={busy} onClick={onCancel}>
        {t("common.cancel")}
      </button>
    </div>
  );
  const modeSwitch = (
    <div className="provider-add-segmented" role="tablist" aria-label={t("settings.addProvider.chooseTitle")}>
      <button
        type="button"
        role="tab"
        aria-selected={mode === "official"}
        className={mode === "official" ? "provider-add-segmented__item provider-add-segmented__item--active" : "provider-add-segmented__item"}
        disabled={busy}
        onClick={() => onMode("official")}
      >
        {t("settings.addProvider.officialChoice")}
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={mode === "custom"}
        className={mode === "custom" ? "provider-add-segmented__item provider-add-segmented__item--active" : "provider-add-segmented__item"}
        disabled={busy}
        onClick={() => onMode("custom")}
      >
        {t("settings.addProvider.customChoice")}
      </button>
    </div>
  );

  if (mode === "official") {
    return (
      <div className="provider-add-panel">
        {header}
        {modeSwitch}
        <div className="provider-add-panel__hint">{t("settings.addProvider.officialHint")}</div>
        <div className="provider-template-grid">
          {templateChoices.map((choice) => {
            const canAdd = providerTemplateCanAdd(choice);
            const badge = providerTemplateStatusBadge(choice, t);
            const conflictProviderName = providerTemplateConflictProviderName(choice);
            if (choice.source === "preset" && (choice.status === "name_conflict" || choice.status === "installed_modified")) {
              return (
                <div
                  key={choice.id}
                  className={`provider-template-card${providerTemplateStatusClass(choice)}`}
                >
                  <strong>
                    {choice.label}
                    {badge ? ` · ${badge}` : ""}
                  </strong>
                  <span>{choice.description}</span>
                  <div className="provider-template-card__actions">
                    <button
                      type="button"
                      className="btn btn--small"
                      disabled={busy || !conflictProviderName}
                      onClick={() => onViewPresetConflict(conflictProviderName)}
                    >
                      {choice.status === "installed_modified" ? t("settings.addProvider.viewPresetProvider") : t("settings.addProvider.viewConflictProvider")}
                    </button>
                    <InlineConfirmButton
                      label={t("settings.addProvider.resetPreset")}
                      confirmLabel={t("settings.addProvider.confirmResetPreset")}
                      cancelLabel={t("common.cancel")}
                      disabled={busy}
                      danger
                      onConfirm={() => onResetPreset(choice.presetID)}
                    />
                  </div>
                </div>
              );
            }
            return (
              <button
                key={choice.id}
                type="button"
                className={`provider-template-card${selected?.id === choice.id ? " provider-template-card--active" : ""}${providerTemplateStatusClass(choice)}`}
                disabled={busy || !canAdd}
                onClick={() => setTemplateID(choice.id)}
              >
                <strong>
                  {choice.label}
                  {badge ? ` · ${badge}` : ""}
                </strong>
                <span>{choice.description}</span>
              </button>
            );
          })}
        </div>
        <label className="set-label">{t("settings.providerKeyOptional")}</label>
        <input
          className="mem-input"
          type="password"
          placeholder={selected ? t("settings.setKey", { env: selected.keyEnv }) : ""}
          value={key}
          disabled={busy || !providerTemplateCanAdd(selected)}
          onChange={(e) => setKey(e.target.value)}
        />
        <div className="prov-card__actions">
          <button type="button" className="btn btn--small" disabled={busy} onClick={onCancel}>
            {t("common.cancel")}
          </button>
          <button
            type="button"
            className="btn btn--primary btn--small"
            disabled={busy || !providerTemplateCanAdd(selected)}
            onClick={() => {
              if (!providerTemplateCanAdd(selected)) return;
              if (selected.source === "official") void onAddOfficial(selected.kind, key.trim());
              else void onAddPreset(selected.presetID, key.trim());
            }}
          >
            {providerTemplateActionLabel(selected, t)}
          </button>
        </div>
      </div>
    );
  }

  if (mode === "custom") {
    return (
      <div className="provider-add-panel">
        {header}
        {modeSwitch}
        <div className="provider-add-panel__hint">{t("settings.addProvider.customHint")}</div>
        <ProviderEditor
          kinds={kinds}
          busy={busy}
          onCancel={onCancel}
          onSave={onAddCustom}
        />
      </div>
    );
  }
  return null;
}

export function ProviderAccessCard({
  group,
  busy,
  fetching,
  fetchResult,
  modelDraft,
  defaultProvider,
  editing,
  kinds,
  onEdit,
  onCancelEdit,
  onSave,
  onRefresh,
  onToggleDraftModel,
  onToggleDraftVision,
  onSelectAllDraftModels,
  onClearDraftModels,
  onCancelDraftModels,
  onSaveDraftModels,
  onToggleWebSearch,
  onUpgradeRecommended,
  onSaveEditorKey,
  onClearEditorKey,
  onDelete,
}: {
  group: ProviderAccessGroup;
  busy: boolean;
  fetching: boolean;
  fetchResult?: ProviderFetchResult;
  modelDraft?: ProviderModelDraft;
  defaultProvider: string;
  editing: string | null;
  kinds: string[];
  onEdit: (name: string) => void;
  onCancelEdit: () => void;
  onSave: (p: ProviderView, key?: string) => void | Promise<void>;
  onRefresh: (p: ProviderView) => void;
  onToggleDraftModel: (model: string) => void;
  onToggleDraftVision: (model: string) => void;
  onSelectAllDraftModels: () => void;
  onClearDraftModels: () => void;
  onCancelDraftModels: () => void;
  onSaveDraftModels: () => void;
  onToggleWebSearch: (enabled: boolean) => void;
  onUpgradeRecommended: (name: string) => void | Promise<void>;
  onSaveEditorKey: (apiKeyEnv: string, value: string) => Promise<void>;
  onClearEditorKey?: (apiKeyEnv: string) => Promise<void>;
  onDelete?: (providers: ProviderView[]) => Promise<void>;
}) {
  const t = useT();
  const editableProvider = group.providers[0];
  const isDefault = group.providers.some((p) => p.name === defaultProvider);
  const editingProvider = group.providers.find((p) => editing === p.name);
  const upgradeProvider = group.providers.find((p) => p.recommendedUpgradeAvailable);
  const primaryProviderExpanded = Boolean(editableProvider && editing === editableProvider.name);
  const supportsServerWebSearch = group.providers.length > 0 && group.providers.every(providerSupportsServerWebSearchForView);
  const webSearchEnabled = supportsServerWebSearch && group.providers.every((provider) => Boolean(provider.webSearch));
  const visibleModels = group.models.slice(0, 6);
  const hiddenModelCount = Math.max(0, group.models.length - visibleModels.length);
  return (
    <article className={`provider-access-card${group.builtIn ? " provider-access-card--builtin" : ""}`}>
      <div className="provider-access-card__head">
        <div className="provider-access-card__identity">
          <div className="provider-access-card__title">
            {group.label}
            <span className={`badge ${group.builtIn ? "badge--project" : "badge--neutral"}`}>
              {group.builtIn ? t("settings.builtinProviderBadge") : t("settings.customProviderBadge")}
            </span>
            <span className={`badge ${group.keySet ? "badge--project" : "badge--feedback"}`}>
              {providerKeyStatusLabel(group, t)}
            </span>
          </div>
        </div>
        <div className="provider-access-card__actions">
          {editableProvider && (
            <button
              className="btn btn--small"
              disabled={busy}
              aria-expanded={primaryProviderExpanded}
              onClick={() => primaryProviderExpanded ? onCancelEdit() : onEdit(editableProvider.name)}
            >
              {primaryProviderExpanded ? t("common.collapse") : t("settings.configureProvider")}
            </button>
          )}
          {editableProvider && group.providers.length === 1 && (
            <button
              className="btn btn--small"
              disabled={busy || fetching || !editableProvider.baseUrl || !group.configured}
              onClick={() => onRefresh(editableProvider)}
            >
              {fetching ? t("settings.fetchingModels") : t("settings.fetchModels")}
            </button>
          )}
          {editableProvider && onDelete && (
            <ProviderAccessMoreMenu
              busy={busy}
              removeDisabled={isDefault && !group.builtIn}
              builtIn={group.builtIn}
              onRemove={() => onDelete(group.providers)}
            />
          )}
        </div>
      </div>
      {group.description && <div className="provider-access-card__desc">{group.description}</div>}

      {upgradeProvider && (
        <div className="provider-protocol-upgrade">
          <div className="provider-protocol-upgrade__copy">
            <div className="provider-protocol-upgrade__title">
              {t("settings.providerProtocol")}: OpenAI Chat Completions
            </div>
            <div className="provider-protocol-upgrade__desc">{t("settings.addProvider.official.deepseekDesc")}</div>
          </div>
          <div className="provider-protocol-upgrade__actions">
            <InlineConfirmButton
              label={<>{t("settings.upgradeRecommendedProtocol")}<ArrowRight size={13} aria-hidden="true" /></>}
              confirmLabel={t("common.confirm")}
              cancelLabel={t("common.cancel")}
              disabled={busy}
              primary
              onConfirm={() => onUpgradeRecommended(canonicalOfficialProviderName(upgradeProvider.name))}
            />
          </div>
        </div>
      )}

      {!supportsServerWebSearch && (
        <ProviderModelSummary
          configured={group.configured}
          models={visibleModels}
          hiddenModelCount={hiddenModelCount}
        />
      )}

      {!group.configured && group.requiresKey && (
        <div className="provider-card-status provider-card-status--warn">
          {t("settings.modelsRequireKey")}
        </div>
      )}
      {fetchResult && (
        <div className={`provider-card-status provider-card-status--${fetchResult.kind}`}>
          {fetchResult.text}
        </div>
      )}

      {modelDraft && (
        <ProviderModelDraftPicker
          draft={modelDraft}
          busy={busy}
          fetching={fetching}
          onToggle={onToggleDraftModel}
          onToggleVision={onToggleDraftVision}
          onSelectAll={onSelectAllDraftModels}
          onClear={onClearDraftModels}
          onCancel={onCancelDraftModels}
          onSave={onSaveDraftModels}
        />
      )}

      {editableProvider && (
        <ProviderServiceCapabilities
          supported={supportsServerWebSearch}
          configured={group.configured}
          models={visibleModels}
          hiddenModelCount={hiddenModelCount}
          showModelSummary
          enabled={webSearchEnabled}
          disabled={busy}
          onChange={onToggleWebSearch}
        />
      )}

      <ProviderTechnicalDetails group={group} />

      {group.providers.length > 1 && (
        <div className="provider-profiles">
          {group.providers.map((p) => {
            const profileExpanded = editing === p.name;
            return (
              <div className="provider-profile-row" key={p.name}>
                <span>{p.name}</span>
                <span>{p.models.join(", ") || t("common.none")}</span>
                <button
                  className="btn btn--small provider-profile-row__refresh"
                  disabled={busy || fetching || !p.baseUrl || !providerIsConfigured(p)}
                  onClick={() => onRefresh(p)}
                >
                  {fetching ? t("settings.fetchingModels") : t("settings.fetchModels")}
                </button>
                <button
                  className="btn btn--small provider-profile-row__configure"
                  disabled={busy}
                  aria-expanded={profileExpanded}
                  onClick={() => profileExpanded ? onCancelEdit() : onEdit(p.name)}
                >
                  {profileExpanded ? t("common.collapse") : t("settings.configureProfile")}
                </button>
              </div>
            );
          })}
        </div>
      )}

      {editingProvider && (
        <ProviderEditor
          key={editingProvider.name}
          initial={editingProvider}
          kinds={kinds}
          busy={busy}
          onCancel={onCancelEdit}
          onSave={onSave}
          onSaveKey={onSaveEditorKey}
          onClearKey={onClearEditorKey}
        />
      )}
    </article>
  );
}

function ProviderModelSummary({
  configured,
  models,
  hiddenModelCount,
  compact = false,
}: {
  configured: boolean;
  models: string[];
  hiddenModelCount: number;
  compact?: boolean;
}) {
  const t = useT();
  const label = t(configured ? "settings.enabledModels" : "settings.modelList");
  return (
    <div className={`provider-card-block${compact ? " provider-card-block--inline" : ""}`}>
      <div className="provider-card-block__label">{label}</div>
      <div className="provider-model-chips" aria-label={label}>
        {models.length > 0 ? models.map((model) => (
          <span className="provider-model-chip" key={model}>
            {model}
          </span>
        )) : <span className="provider-model-chip provider-model-chip--empty">{t("settings.noModelsConfigured")}</span>}
        {hiddenModelCount > 0 && (
          <span className="provider-model-chip provider-model-chip--more">
            {t("settings.moreModels", { n: hiddenModelCount })}
          </span>
        )}
      </div>
    </div>
  );
}

function ProviderTechnicalDetails({ group }: { group: ProviderAccessGroup }) {
  const t = useT();
  const imageInputUnsupported = group.providers.length > 0 && group.providers.every((provider) => providerVisionCapabilityForView(provider) === "unsupported");
  return (
    <details className="provider-technical-details">
      <summary>{t("settings.providerAccess")}</summary>
      <dl>
        {group.providers.length === 1 ? (
          <>
            <div><dt>{t("settings.providerProtocol")}</dt><dd>{providerProtocolDisplayName(group.kind)}</dd></div>
            <div><dt>{t("settings.providerBaseUrlLabel")}</dt><dd>{group.baseUrl || t("common.none")}</dd></div>
          </>
        ) : group.providers.map((provider) => (
          <div key={provider.name}><dt>{provider.name}</dt><dd>{providerProtocolDisplayName(provider.kind)} · {provider.baseUrl || t("common.none")}</dd></div>
        ))}
        <div>
          <dt>{t("settings.providerApiKeyEnv")}</dt>
          <dd>{group.apiKeyEnv || t("common.none")}</dd>
        </div>
        {imageInputUnsupported && (
          <div>
            <dt>{t("settings.visionModel")}</dt>
            <dd>{t("settings.imageInputUnsupported")}</dd>
          </div>
        )}
        {group.keySource && (
          <div>
            <dt>{t("settings.providerKey")}</dt>
            <dd title={group.keySourcePath || undefined}>{group.keySource}</dd>
          </div>
        )}
      </dl>
    </details>
  );
}

function providerProtocolDisplayName(kind: string): string {
  switch (kind.trim().toLowerCase()) {
    case "anthropic":
      return "Anthropic Messages";
    case "responses":
      return "Responses API";
    case "openai":
      return "OpenAI Chat Completions";
    default:
      return kind;
  }
}

function ProviderAccessMoreMenu({
  busy,
  removeDisabled,
  builtIn,
  onRemove,
}: {
  busy: boolean;
  removeDisabled: boolean;
  builtIn: boolean;
  onRemove: () => void | Promise<void>;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const disabled = busy || removeDisabled;
  const tooltip = removeDisabled ? t("settings.cantDeleteDefault") : t("settings.themeGallery.moreActions");

  return (
    <div className="provider-access-more">
      <Tooltip label={tooltip}>
        <button
          ref={triggerRef}
          type="button"
          className="btn btn--small provider-access-more__trigger"
          aria-label={t("settings.themeGallery.moreActions")}
          aria-haspopup="menu"
          aria-expanded={open}
          disabled={disabled}
          onClick={() => setOpen((current) => !current)}
        >
          <MoreHorizontal size={16} aria-hidden="true" />
        </button>
      </Tooltip>
      <AnchoredPopover
        open={open && !disabled}
        anchorRef={triggerRef}
        onClose={() => setOpen(false)}
        className="provider-access-more__menu"
        align="end"
        placement="bottom"
      >
        <div className="provider-access-more__items" role="menu" aria-label={t("settings.themeGallery.moreActions")}>
          <InlineConfirmButton
            label={<><Trash2 size={14} aria-hidden="true" />{t("settings.removeProviderAccess")}</>}
            confirmLabel={builtIn ? t("settings.confirmRemoveProviderAccess") : t("settings.confirmDeleteProvider")}
            cancelLabel={t("common.cancel")}
            danger={!builtIn}
            buttonRole="menuitem"
            onConfirm={async () => {
              setOpen(false);
              await onRemove();
            }}
          />
        </div>
      </AnchoredPopover>
    </div>
  );
}

function ProviderModelDraftPicker({
  draft,
  busy,
  fetching,
  onToggle,
  onToggleVision,
  onSelectAll,
  onClear,
  onCancel,
  onSave,
}: {
  draft: ProviderModelDraft;
  busy: boolean;
  fetching: boolean;
  onToggle: (model: string) => void;
  onToggleVision: (model: string) => void;
  onSelectAll: () => void;
  onClear: () => void;
  onCancel: () => void;
  onSave: () => void;
}) {
  const t = useT();
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  // Debounce search to avoid expensive filtering on every keystroke
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 150);
    return () => clearTimeout(timer);
  }, [query]);
  const selected = new Set(draft.selected);
  const vision = new Set(draft.visionModels);
  const q = debouncedQuery.trim().toLowerCase();
  const visibleCandidates = useMemo(
    () => (q ? draft.candidates.filter((model) => model.toLowerCase().includes(q)) : draft.candidates),
    [draft.candidates, q],
  );
  const deferredCandidates = useDeferredValue(visibleCandidates);
  const disabled = busy || fetching;

  return (
    <div className="provider-model-draft">
      <div className="provider-model-draft__head">
        <div>
          <div className="provider-card-block__label">{t("settings.modelCandidates")}</div>
          <span>{t("settings.modelCandidatesSelected", { n: draft.selected.length })}</span>
        </div>
        <div className="provider-model-draft__tools">
          <button type="button" className="btn btn--small" disabled={disabled || draft.selected.length === draft.candidates.length} onClick={onSelectAll}>
            {t("settings.selectAllModels")}
          </button>
          <button type="button" className="btn btn--small" disabled={disabled || draft.selected.length === 0} onClick={onClear}>
            {t("settings.clearModelSelection")}
          </button>
        </div>
      </div>
      <input
        className="mem-input provider-model-draft__search"
        placeholder={t("settings.modelCandidateSearch")}
        value={query}
        disabled={disabled}
        onChange={(e) => setQuery(e.target.value)}
      />
      <div className="provider-model-draft__list" role="list" aria-label={t("settings.modelCandidates")}>
        {deferredCandidates.length > 0 ? deferredCandidates.map((model) => {
          const enabled = selected.has(model);
          return (
            <div className="provider-model-draft__option" key={model} role="listitem" style={{ contentVisibility: "auto", containIntrinsicSize: "auto 48px" }}>
              <label className="provider-model-draft__model">
                <input
                  type="checkbox"
                  checked={enabled}
                  disabled={disabled}
                  onChange={() => onToggle(model)}
                />
                <span>{model}</span>
              </label>
              {draft.visionCapability === "configurable" ? (
                <label className="provider-model-draft__vision">
                  <input
                    type="checkbox"
                    checked={enabled && vision.has(model)}
                    disabled={disabled || !enabled}
                    aria-label={t("settings.visionModelAria", { model })}
                    onChange={() => onToggleVision(model)}
                  />
                  <span>{t("settings.visionModel")}</span>
                </label>
              ) : (
                <div className="provider-model-draft__capabilities" aria-label={t("settings.modelCapabilitiesAria", { model })}>
                  <span>{t("settings.textInput")}</span>
                  <span>{t("settings.imageInputUnsupported")}</span>
                </div>
              )}
            </div>
          );
        }) : (
          <div className="provider-model-draft__empty">{t("settings.noMatchingCandidateModels")}</div>
        )}
      </div>
      <div className="provider-model-draft__actions">
        <button type="button" className="btn btn--small" disabled={disabled} onClick={onCancel}>
          {t("common.cancel")}
        </button>
        <button type="button" className="btn btn--primary btn--small" disabled={disabled || draft.selected.length === 0} onClick={onSave}>
          {t("settings.saveEnabledModels")}
        </button>
      </div>
    </div>
  );
}

function ProviderServiceCapabilities({
  supported,
  configured,
  models,
  hiddenModelCount,
  showModelSummary = false,
  enabled,
  disabled,
  onChange,
}: {
  supported: boolean;
  configured?: boolean;
  models: string[];
  hiddenModelCount?: number;
  showModelSummary?: boolean;
  enabled: boolean;
  disabled: boolean;
  onChange: (enabled: boolean) => void;
}) {
  const t = useT();
  const capabilityID = useId();
  if (!supported) return null;
  return (
    <section className="provider-capabilities" aria-labelledby={capabilityID}>
      <div className="provider-card-block__label" id={capabilityID}>
        {t("settings.providerCapabilities")}
      </div>
      {showModelSummary && (
        <ProviderModelSummary
          configured={Boolean(configured)}
          models={models}
          hiddenModelCount={hiddenModelCount ?? 0}
          compact
        />
      )}
      <label className="provider-capability-row">
        <span className="provider-capability-row__copy">
          <span className="provider-capability-row__title">
            {t("settings.serverWebSearch")}
            <span className="badge badge--project">{t("settings.recommended")}</span>
          </span>
          <span>{t("settings.serverWebSearchHint")}</span>
        </span>
        <input
          className="provider-capability-row__switch"
          type="checkbox"
          role="switch"
          checked={enabled}
          disabled={disabled}
          onChange={(event) => onChange(event.target.checked)}
        />
      </label>
    </section>
  );
}

function providerAccessGroups(providers: ProviderView[], t: ReturnType<typeof useT>): ProviderAccessGroup[] {
  const groups = new Map<string, ProviderAccessGroup>();
  for (const p of providers) {
    const id = providerGroupID(p);
    const builtIn = id.startsWith("builtin:");
    const existing = groups.get(id);
    if (existing) {
      existing.providers.push(p);
      existing.keySet = existing.keySet || p.keySet;
      existing.requiresKey = existing.requiresKey && providerRequiresKey(p);
      existing.configured = existing.configured || providerIsConfigured(p);
      existing.recommendedUpgradeAvailable = existing.recommendedUpgradeAvailable || Boolean(p.recommendedUpgradeAvailable);
      if (existing.recommendedUpgradeAvailable && existing.id === "builtin:deepseek") {
        existing.description = "";
      }
      if (!existing.keySource && p.keySource) existing.keySource = p.keySource;
      if (!existing.keySourcePath && p.keySourcePath) existing.keySourcePath = p.keySourcePath;
      existing.models = uniqueStrings([...existing.models, ...p.models]);
      continue;
    }
    groups.set(id, {
      id,
      label: providerGroupLabel(p, t),
      description: providerGroupDescription(p, t),
      builtIn,
      providers: [p],
      apiKeyEnv: p.apiKeyEnv,
      keySet: p.keySet,
      requiresKey: providerRequiresKey(p),
      configured: providerIsConfigured(p),
      keySource: p.keySource,
      keySourcePath: p.keySourcePath,
      baseUrl: p.baseUrl,
      kind: p.kind,
      models: uniqueStrings(p.models),
      recommendedUpgradeAvailable: Boolean(p.recommendedUpgradeAvailable),
    });
  }
  return Array.from(groups.values());
}

function providerBaseHost(baseUrl: string): string {
  try {
    return new URL(baseUrl).hostname.toLowerCase();
  } catch {
    return "";
  }
}

type ProviderVisionCapability = "configurable" | "unsupported";

function isDeepSeekOfficialEndpoint(baseUrl: string): boolean {
  return providerBaseHost(baseUrl).endsWith(".deepseek.com");
}

export function providerSupportsServerWebSearch(kind: string, baseUrl: string): boolean {
  try {
    const endpoint = new URL(baseUrl.trim());
    if (
      endpoint.protocol !== "https:" ||
      endpoint.hostname.toLowerCase() !== "api.deepseek.com" ||
      endpoint.port ||
      endpoint.username ||
      endpoint.password ||
      endpoint.search ||
      endpoint.hash
    ) return false;
    const path = endpoint.pathname.replace(/\/+$/, "");
    switch (kind.trim().toLowerCase()) {
      case "responses":
        return path === "";
      case "anthropic":
        return path === "/anthropic";
      default:
        return false;
    }
  } catch {
    return false;
  }
}

export function providerSupportsServerWebSearchForView(
  provider: Pick<ProviderView, "kind" | "baseUrl" | "serverWebSearchCapability">,
): boolean {
  if (typeof provider.serverWebSearchCapability === "boolean") {
    return provider.serverWebSearchCapability;
  }
  return providerSupportsServerWebSearch(provider.kind, provider.baseUrl);
}

function providerVisionCapability(kind: string, baseUrl: string): ProviderVisionCapability {
  if (!isDeepSeekOfficialEndpoint(baseUrl)) return "configurable";
  switch (kind.trim().toLowerCase()) {
    case "openai":
    case "responses":
    case "anthropic":
      return "unsupported";
    default:
      return "configurable";
  }
}

export function providerVisionCapabilityForView(
  provider: Pick<ProviderView, "kind" | "baseUrl" | "visionCapability">,
): ProviderVisionCapability {
  if (provider.visionCapability === "unsupported" || provider.visionCapability === "configurable") {
    return provider.visionCapability;
  }
  return providerVisionCapability(provider.kind, provider.baseUrl);
}

function canonicalOfficialProviderName(name: string): string {
  switch (name.trim()) {
    case "deepseek-flash":
    case "deepseek-pro":
      return "deepseek";
    default:
      return name.trim();
  }
}

function officialProviderKind(p: ProviderView): string {
  if (!p.builtIn) return "";
  const name = canonicalOfficialProviderName(p.name);
  const host = providerBaseHost(p.baseUrl);
  if (name === "deepseek" && host === "api.deepseek.com") return "deepseek";
  return "";
}

function providerGroupID(p: ProviderView): string {
  const official = officialProviderKind(p);
  if (official) return `builtin:${official}`;
  return `custom:${p.name}`;
}

function providerGroupLabel(p: ProviderView, t?: ReturnType<typeof useT>): string {
  const id = providerGroupID(p);
  if (id === "builtin:deepseek") return t ? t("settings.providerLabel.deepseek") : "DeepSeek";
  return p.name;
}

function providerGroupDescription(p: ProviderView, t: ReturnType<typeof useT>): string {
  const id = providerGroupID(p);
  if (id === "builtin:deepseek") {
    return p.recommendedUpgradeAvailable ? "" : t("settings.providerDesc.deepseek");
  }
  return "";
}

function uniqueStrings(values: string[]): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const value of values) {
    if (value && !seen.has(value)) {
      seen.add(value);
      out.push(value);
    }
  }
  return out;
}

function parseProviderListInput(value: string): string[] {
  return uniqueStrings(value
    .split(/[,，]/)
    .map((entry) => entry.trim())
    .filter(Boolean));
}




export const ProviderEditorModelPicker = memo(function ProviderEditorModelPicker({
  candidates,
  selectedModels,
  visionModels,
  visionCapability = "configurable",
  contextWindows,
  disabled,
  onToggleModel,
  onToggleVision,
  onContextWindowChange,
  onSelectAll,
  onClear,
}: {
  candidates: string[];
  selectedModels: string[];
  visionModels: string[];
  visionCapability?: ProviderVisionCapability;
  contextWindows: Record<string, string>;
  disabled: boolean;
  onToggleModel: (model: string) => void;
  onToggleVision: (model: string) => void;
  onContextWindowChange: (model: string, value: string) => void;
  onSelectAll: () => void;
  onClear: () => void;
}) {
  const t = useT();
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedQuery(query), 150);
    return () => clearTimeout(timer);
  }, [query]);
  const q = debouncedQuery.trim().toLowerCase();
  const visibleCandidates = q
    ? candidates.filter((model) => model.toLowerCase().includes(q))
    : candidates;
  const deferredCandidates = useDeferredValue(visibleCandidates);
  if (candidates.length === 0) return null;
  const selected = new Set(selectedModels);
  const vision = new Set(visionModels);
  return (
    <div className="provider-model-draft provider-model-draft--inline">
      <div className="provider-model-draft__head">
        <div>
          <div className="provider-card-block__label">{t("settings.modelCandidates")}</div>
          <span>{t("settings.modelCandidatesSelected", { n: selectedModels.length })}</span>
        </div>
        <div className="provider-model-draft__tools">
          <button type="button" className="btn btn--small" disabled={disabled || selectedModels.length === candidates.length} onClick={onSelectAll}>
            {t("settings.selectAllModels")}
          </button>
          <button type="button" className="btn btn--small" disabled={disabled || selectedModels.length === 0} onClick={onClear}>
            {t("settings.clearModelSelection")}
          </button>
        </div>
      </div>
      <div className="provider-model-draft__context-guide">{t("settings.modelContextWindowGuide")}</div>
      {candidates.length > 8 && (
        <input
          className="mem-input provider-model-draft__search"
          placeholder={t("settings.modelCandidateSearch")}
          value={query}
          disabled={disabled}
          onChange={(e) => setQuery(e.target.value)}
        />
      )}
      <div className="provider-model-draft__list" role="list" aria-label={t("settings.modelCandidates")}>
        {deferredCandidates.length > 0 ? deferredCandidates.map((model) => {
          const enabled = selected.has(model);
          return (
            <div className="provider-model-draft__option" key={model} role="listitem" style={{ contentVisibility: "auto", containIntrinsicSize: "auto 48px" }}>
              <label className="provider-model-draft__model">
                <input
                  type="checkbox"
                  checked={enabled}
                  disabled={disabled}
                  onChange={() => onToggleModel(model)}
                />
                <span>{model}</span>
              </label>
              {visionCapability === "configurable" ? (
                <label className="provider-model-draft__vision">
                  <input
                    type="checkbox"
                    checked={enabled && vision.has(model)}
                    disabled={disabled || !enabled}
                    aria-label={t("settings.visionModelAria", { model })}
                    onChange={() => onToggleVision(model)}
                  />
                  <span>{t("settings.visionModel")}</span>
                </label>
              ) : (
                <div className="provider-model-draft__capabilities" aria-label={t("settings.modelCapabilitiesAria", { model })}>
                  <span>{t("settings.textInput")}</span>
                  <span>{t("settings.imageInputUnsupported")}</span>
                </div>
              )}
              <div className="provider-model-draft__context-field">
                <label className="provider-model-draft__context">
                  <span>{t("settings.modelContextWindow")}</span>
                  <input
                    className="mem-input provider-model-draft__context-input"
                    type="number"
                    inputMode="numeric"
                    min={1}
                    disabled={disabled || !enabled}
                    placeholder={t("settings.modelContextWindowPlaceholder")}
                    title={t("settings.modelContextWindowHint")}
                    aria-label={t("settings.modelContextWindowAria", { model })}
                    value={contextWindows[model] ?? ""}
                    onChange={(event) => onContextWindowChange(model, event.target.value)}
                  />
                </label>
                {enabled && providerModelContextWindowIsSmall(contextWindows[model]) && (
                  <div className="provider-model-draft__context-warning" role="status">
                    {t("settings.modelContextWindowSmallWarning")}
                  </div>
                )}
              </div>
            </div>
          );
        }) : (
          <div className="provider-model-draft__empty">{t("settings.noMatchingCandidateModels")}</div>
        )}
      </div>
    </div>
  );
});

export function ProviderEditor({
  initial,
  kinds,
  busy,
  onCancel,
  onSave,
  onSaveKey,
  onClearKey,
}: {
  initial?: ProviderView;
  kinds: string[];
  busy: boolean;
  onCancel: () => void;
  onSave: (p: ProviderView, key?: string) => void | Promise<void>;
  onSaveKey?: (apiKeyEnv: string, value: string) => Promise<void>;
  onClearKey?: (apiKeyEnv: string) => Promise<void>;
}) {
  const t = useT();
  const [name, setName] = useState(initial?.name ?? "");
  const [kind, setKind] = useState(initial?.kind ?? "openai");
  const [requestUrl, setRequestUrl] = useState(() => providerRequestURLFromConfig(
    initial?.kind ?? "openai",
    initial?.baseUrl ?? "",
    initial?.requestUrl ?? "",
    initial?.chatUrl ?? "",
  ));
  const providerUrlInputId = useId();
  const providerUrlHelpId = useId();
  const [models, setModels] = useState((initial?.models ?? []).join(", "));
  const [modelCandidates, setModelCandidates] = useState<string[]>(initial?.models ?? []);
  const [visionModels, setVisionModels] = useState((initial?.visionModels ?? []).join(", "));
  const [visionModelsConfigured, setVisionModelsConfigured] = useState(
    Boolean(initial?.visionModelsConfigured ?? ((initial?.visionModels ?? []).length > 0)),
  );
  const [modelsUrl, setModelsUrl] = useState(initial?.modelsUrl ?? "");
  const [apiKeyEnv, setApiKeyEnv] = useState(initial?.apiKeyEnv ?? "");
  const [headersDraft, setHeadersDraft] = useState(formatProviderHeaders(initial?.headers));
  const [extraBodyDraft, setExtraBodyDraft] = useState(formatProviderExtraBody(initial?.extraBody));
  const [authHeader, setAuthHeader] = useState(Boolean(initial?.authHeader));
  const [keyDraft, setKeyDraft] = useState("");
  const [balanceUrl, setBalanceUrl] = useState(initial?.balanceUrl ?? "");
  // Empty when unset so the placeholder (and its "0 = disabled" hint) reads instead
  // of a bare "0"; saved back as 0.
  const [ctx, setCtx] = useState(initial?.contextWindow ? String(initial.contextWindow) : "");
  const [modelContextWindows, setModelContextWindows] = useState<Record<string, string>>(
    () => providerModelContextWindowDrafts(initial?.modelOverrides),
  );
  const [reasoningProtocol, setReasoningProtocol] = useState(normalizeReasoningProtocol(initial?.reasoningProtocol));
  const [thinking, setThinking] = useState(normalizeThinkingMode(initial?.thinking));
  const [webSearch, setWebSearch] = useState(Boolean(initial?.webSearch));
  const [supportedEfforts] = useState<string[]>(initial?.supportedEfforts ?? []);
  const [defaultEffort] = useState(initial?.defaultEffort ?? "");
  const [fetchingModels, setFetchingModels] = useState(false);
  const [fetchStatus, setFetchStatus] = useState<string | null>(null);
  const [fetchFallback, setFetchFallback] = useState<string | null>(null);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const builtIn = initial?.builtIn ?? false;
  const isNewCustomProvider = !initial;
  const providerKindChoices = useMemo(() => {
    const choices = uniqueStrings([kind, ...kinds].map((candidate) => candidate.trim()).filter(Boolean));
    return choices.length > 0 ? choices : ["openai"];
  }, [kind, kinds]);
  const effectiveKind = providerEditorEffectiveKind(isNewCustomProvider, kind, providerKindChoices);
  const effectiveRequestUrl = requestUrl.trim();
  const effectiveBaseUrl = providerBaseURLForSave(initial, effectiveKind, effectiveRequestUrl);
  const effectiveLegacyChatUrl = effectiveKind.toLowerCase() === "openai" ? effectiveRequestUrl : initial?.chatUrl ?? "";
  const effectiveModelsUrl = modelsUrl.trim();
  const initialEffectiveBaseUrl = initial ? trimmedBaseURL(initial.baseUrl) : "";
  const retainedVisionCapability = initial &&
    effectiveKind.trim().toLowerCase() === initial.kind.trim().toLowerCase() &&
    trimmedBaseURL(effectiveBaseUrl) === initialEffectiveBaseUrl
    ? initial.visionCapability
    : undefined;
  const effectiveVisionCapability = providerVisionCapabilityForView({
    kind: effectiveKind,
    baseUrl: effectiveBaseUrl,
    visionCapability: retainedVisionCapability,
  });
  const retainedServerWebSearchCapability = initial &&
    effectiveKind.trim().toLowerCase() === initial.kind.trim().toLowerCase() &&
    trimmedBaseURL(effectiveBaseUrl) === initialEffectiveBaseUrl
    ? initial.serverWebSearchCapability
    : undefined;
  const effectiveServerWebSearchCapability = retainedServerWebSearchCapability ??
    providerSupportsServerWebSearch(effectiveKind, effectiveBaseUrl);
  const effectiveHeaders = parseProviderHeaders(headersDraft);
  const extraBodyParse = useMemo(() => {
    try {
      return { value: parseProviderExtraBody(extraBodyDraft, t), error: "" };
    } catch (e) {
      return { value: {}, error: providerExtraBodyParseError(e, t) };
    }
  }, [extraBodyDraft, t]);
  const effectiveExtraBody = extraBodyParse.value;
  const extraBodyInvalid = Boolean(extraBodyDraft.trim() && extraBodyParse.error);
  const modelNames = useMemo(
    () => parseProviderListInput(models),
    [models],
  );
  const modelCandidateNames = useMemo(
    () => uniqueStrings([...modelCandidates, ...modelNames]),
    [modelCandidates, modelNames],
  );
  const visionModelNames = useMemo(
    () => parseProviderListInput(visionModels).filter((model) => modelNames.includes(model)),
    [modelNames, visionModels],
  );

  // Empty supportedEfforts means "use protocol defaults". The simplified
  // provider flow no longer edits these levels directly, but it preserves
  // existing advanced TOML unless the user explicitly disables reasoning.
  const cleanedSupportedEfforts = reasoningProtocol !== "none"
    ? uniqueStrings(
        supportedEfforts
          .map((level) => level.toLowerCase().trim())
          .filter((level) => level && level !== "auto")
      )
    : [];
  const normalizedDefaultEffort = defaultEffort.toLowerCase().trim();
  const cleanDefaultEffort = cleanedSupportedEfforts.includes(normalizedDefaultEffort) ? normalizedDefaultEffort : "";

  const fetchModels = async () => {
    if (extraBodyInvalid) return;
    setFetchingModels(true);
    setFetchStatus(null);
    setFetchFallback(null);
    try {
      const effectiveApiKeyEnv = providerApiKeyEnvForSave(name, apiKeyEnv, keyDraft);
      if (!apiKeyEnv.trim()) setApiKeyEnv(effectiveApiKeyEnv);
      if (keyDraft.trim()) {
        await app.SaveProviderKey(effectiveApiKeyEnv, keyDraft.trim());
        invalidateProviderCacheByAPIKeyEnv(effectiveApiKeyEnv);
      }
      const fetched = await cachedFetchProviderModels((provider) => app.FetchProviderModels(provider), {
        name: name.trim() || t("settings.newProviderDraftName"),
        builtIn: initial?.builtIn ?? false,
        added: initial?.added ?? true,
        kind: effectiveKind,
        baseUrl: effectiveBaseUrl,
        chatUrl: effectiveLegacyChatUrl,
        requestUrl: effectiveRequestUrl,
        modelsUrl: effectiveModelsUrl,
        models: [],
        visionModels: [],
        visionModelsConfigured: false,
        default: "",
        apiKeyEnv: effectiveApiKeyEnv,
        headers: effectiveHeaders,
        extraBody: effectiveExtraBody,
        authHeader,
        keySet: Boolean(keyDraft.trim()) || (initial?.keySet ?? false),
        balanceUrl: balanceUrl.trim(),
        contextWindow: Number(ctx) || 0,
        reasoningProtocol,
        thinking,
        webSearch: effectiveServerWebSearchCapability && webSearch,
        serverWebSearchCapability: effectiveServerWebSearchCapability,
        supportedEfforts: cleanedSupportedEfforts,
        defaultEffort: cleanDefaultEffort,
        modelOverrides: mergeProviderModelContextWindows(initial?.modelOverrides, parseProviderListInput(models), modelContextWindows),
      }, true);
      if (fetched.length === 0) {
        setFetchFallback(t("settings.fetchModelsManualFallbackEmpty"));
        return;
      }
      setModelCandidates(fetched);
      setModels(fetched.join(", "));
      setVisionModels((current) => {
        const existing = parseProviderListInput(current).filter((model) => fetched.includes(model));
        return uniqueStrings([...existing, ...inferredVisionModels(fetched)]).filter((model) => fetched.includes(model)).join(", ");
      });
      setVisionModelsConfigured(true);
      if (keyDraft.trim()) setKeyDraft("");
      setFetchStatus(t("settings.fetchModelsSuccess", { n: fetched.length }));
    } catch (e) {
      setFetchFallback(providerModelFetchFallbackMessage(e, t));
    } finally {
      setFetchingModels(false);
    }
  };

  const save = async () => {
    if (extraBodyInvalid) return;
    setFetchStatus(null);
    setFetchFallback(null);
    const ms = parseProviderListInput(models);
    const vms = effectiveVisionCapability === "unsupported"
      ? []
      : parseProviderListInput(visionModels).filter((model) => ms.includes(model));
    const effectiveApiKeyEnv = providerApiKeyEnvForSave(name, apiKeyEnv, keyDraft);
    const provider: ProviderView = {
      name: name.trim(),
      builtIn: initial?.builtIn ?? false,
      added: initial?.added ?? true,
      kind: effectiveKind,
      baseUrl: effectiveBaseUrl,
      chatUrl: effectiveLegacyChatUrl,
      requestUrl: effectiveRequestUrl,
      models: ms,
      visionModels: vms,
      visionModelsConfigured: visionModelsConfigured || vms.length > 0,
      default: ms[0] ?? "",
      apiKeyEnv: effectiveApiKeyEnv,
      headers: effectiveHeaders,
      extraBody: effectiveExtraBody,
      authHeader,
      modelsUrl: effectiveModelsUrl,
      keySet: Boolean(keyDraft.trim()) || (initial?.keySet ?? false),
      balanceUrl: balanceUrl.trim(),
      contextWindow: Number(ctx) || 0,
      reasoningProtocol,
      thinking,
      webSearch: effectiveServerWebSearchCapability && webSearch,
      serverWebSearchCapability: effectiveServerWebSearchCapability,
      supportedEfforts: cleanedSupportedEfforts,
      // Clear the stored default if no levels are selected; the backend's
      // NormalizeEffort would otherwise silently ignore an unsupported value.
      defaultEffort: cleanedSupportedEfforts.length > 0 ? cleanDefaultEffort : "",
      modelOverrides: mergeProviderModelContextWindows(initial?.modelOverrides, ms, modelContextWindows),
    };
    try {
      await onSave(provider, keyDraft.trim() || undefined);
    } catch (e) {
      setFetchFallback(String((e as Error)?.message ?? e));
    }
  };

  if (builtIn) {
    const keyEnv = initial?.apiKeyEnv.trim() ?? "";
    return (
      <div className="provider-editor provider-editor--builtin provider-editor--key-only">
        {initial && onSaveKey && keyEnv && (
          <>
            <div className="provider-key-status provider-key-status--managed provider-key-status--compact">
              <span title={initial.keySourcePath || undefined}>
                {initial.keySet ? t("settings.configuredKey", { env: keyEnv }) : t("settings.notConfiguredKey", { env: keyEnv })}
                {initial.keySource ? ` · ${t("settings.keySource", { source: initial.keySource })}` : ""}
              </span>
              {initial.keySet && onClearKey && (
                <InlineConfirmButton
                  label={t("settings.clearKey")}
                  confirmLabel={t("settings.confirmClearKey")}
                  cancelLabel={t("common.cancel")}
                  disabled={busy}
                  danger
                  onConfirm={() => onClearKey(keyEnv)}
                />
              )}
            </div>
            <KeyField
              apiKeyEnv={keyEnv}
              busy={busy}
              keySet={initial.keySet}
              onSet={(env, value) => onSaveKey(env, value)}
            />
          </>
        )}
      </div>
    );
  }

  const canFetch = Boolean(name.trim() && effectiveBaseUrl);

  const setModelsFromList = (nextModels: string[]) => {
    setModels(uniqueStrings(nextModels).join(", "));
  };

  const updateManualModels = (value: string) => {
    setModels(value);
    const typedModels = parseProviderListInput(value);
    if (typedModels.length > 0) {
      setModelCandidates((current) => uniqueStrings([...current, ...typedModels]));
    }
  };

  const toggleEditorModel = (model: string) => {
    const selected = new Set(modelNames);
    if (selected.has(model)) {
      selected.delete(model);
      setVisionModels(visionModelNames.filter((candidate) => candidate !== model).join(", "));
    } else {
      selected.add(model);
    }
    setModelsFromList(modelCandidateNames.filter((candidate) => selected.has(candidate)));
    setVisionModelsConfigured(true);
  };

  const toggleEditorVisionModel = (model: string) => {
    if (!modelNames.includes(model)) return;
    const vision = new Set(visionModelNames);
    if (vision.has(model)) vision.delete(model);
    else vision.add(model);
    setVisionModels(modelCandidateNames.filter((candidate) => vision.has(candidate)).join(", "));
    setVisionModelsConfigured(true);
  };

  const updateEditorModelContextWindow = (model: string, value: string) => {
    setModelContextWindows((current) => ({ ...current, [model]: value }));
  };

  const selectAllEditorModels = () => {
    setModelsFromList(modelCandidateNames);
    setVisionModels(visionModelNames.filter((model) => modelCandidateNames.includes(model)).join(", "));
    setVisionModelsConfigured(true);
  };

  const clearEditorModels = () => {
    setModels("");
    setVisionModels("");
    setVisionModelsConfigured(true);
  };

  const advancedFields = (
    <details className="provider-editor-advanced" open={advancedOpen} onToggle={(e) => setAdvancedOpen(e.currentTarget.open)}>
      <summary>
        <span className="provider-editor-advanced__title">
          <ChevronDown className="provider-editor-advanced__icon" size={16} aria-hidden="true" />
          {t("settings.providerAdvancedSettings")}
        </span>
        <span className="provider-editor-advanced__hint">
          {advancedOpen ? t("settings.providerAdvancedCollapseHint") : t("settings.providerAdvancedExpandHint")}
        </span>
      </summary>
      <div className="provider-editor-advanced__body">
        <label className="set-label">{t("settings.providerApiKeyEnv")}</label>
        <input
          className="mem-input"
          placeholder={apiKeyEnvFromProviderName(name)}
          value={apiKeyEnv}
          onChange={(e) => setApiKeyEnv(e.target.value)}
        />
        <div className="mem-hint">{t("settings.providerApiKeyEnvHint")}</div>
        <label className="set-label">{t("settings.providerModelsUrl")}</label>
        <input
          className="mem-input"
          placeholder={t("settings.providerModelsUrlPlaceholder")}
          value={modelsUrl}
          onChange={(e) => setModelsUrl(e.target.value)}
        />
        <div className="mem-hint">{t("settings.providerModelsUrlHint")}</div>
        <label className="set-label">{t("settings.providerHeaders")}</label>
        <textarea
          className="mem-textarea provider-headers-textarea"
          placeholder={t("settings.providerHeadersPlaceholder")}
          value={headersDraft}
          onChange={(e) => setHeadersDraft(e.target.value)}
          rows={3}
        />
        <div className="mem-hint">{t("settings.providerHeadersHint")}</div>
        <label className="set-label">{t("settings.providerExtraBody")}</label>
        <textarea
          className="mem-textarea provider-headers-textarea"
          placeholder={t("settings.providerExtraBodyPlaceholder")}
          value={extraBodyDraft}
          onChange={(e) => setExtraBodyDraft(e.target.value)}
          rows={4}
        />
        <div className={`mem-hint${extraBodyInvalid ? " mem-hint--error" : ""}`}>
          {extraBodyInvalid ? extraBodyParse.error : t("settings.providerExtraBodyHint")}
        </div>
        <label className="set-check">
          <input
            type="checkbox"
            checked={authHeader}
            onChange={(e) => setAuthHeader(e.target.checked)}
          />
          {t("settings.providerAuthHeader")}
        </label>
        <div className="mem-hint">{t("settings.providerAuthHeaderHint")}</div>
        <label className="set-label">{t("settings.reasoningProtocol")}</label>
        <select className="mem-select" value={reasoningProtocol} onChange={(e) => setReasoningProtocol(e.target.value)}>
          {REASONING_PROTOCOLS.map((protocol) => (
            <option key={protocol || "auto"} value={protocol}>
              {reasoningProtocolLabel(protocol, t)}
            </option>
          ))}
        </select>
        <div className="mem-hint">{t("settings.reasoningProtocolHint")}</div>
        <label className="set-label">{t("settings.thinkingMode")}</label>
        <select className="mem-select" value={thinking} onChange={(e) => setThinking(normalizeThinkingMode(e.target.value))}>
          {THINKING_MODES.map((mode) => (
            <option key={mode || "auto"} value={mode}>
              {thinkingModeLabel(mode, t)}
            </option>
          ))}
        </select>
        <div className="mem-hint">{t("settings.thinkingModeHint")}</div>
        <label className="set-label">{t("settings.providerBalanceUrl")}</label>
        <input
          className="mem-input"
          placeholder={t("settings.balanceUrlPlaceholder")}
          value={balanceUrl}
          onChange={(e) => setBalanceUrl(e.target.value)}
        />
        <div className="mem-hint">{t("settings.balanceUrlHint")}</div>
        <label className="set-label">{t("settings.providerContextWindow")}</label>
        <input
          className="mem-input"
          inputMode="numeric"
          min={0}
          placeholder={t("settings.contextWindowPlaceholder")}
          type="number"
          value={ctx}
          onChange={(e) => setCtx(e.target.value)}
        />
        <div className="mem-hint">{t("settings.contextWindowHint")}</div>
      </div>
    </details>
  );

  return (
    <div className={`provider-editor${isNewCustomProvider ? " provider-editor--wizard" : ""}`}>
      <label className="set-label">{t("settings.customProviderName")}</label>
      <input className="mem-input" placeholder={t("settings.customProviderNamePlaceholder")} value={name} onChange={(e) => setName(e.target.value)} disabled={!!initial} />
      <label className="set-label">{t("settings.providerProtocol")}</label>
      <select className="mem-select" value={kind} onChange={(e) => setKind(e.target.value)}>
        {providerKindChoices.map((choice) => (
          <option key={choice} value={choice}>
            {providerKindLabel(choice, t)}
          </option>
        ))}
      </select>
      <div className="mem-hint">{providerKindHint(effectiveKind, t)}</div>
      <label className="set-label" htmlFor={providerUrlInputId}>
        {t("settings.providerBaseUrlLabel")}
      </label>
      <input
        id={providerUrlInputId}
        className="mem-input provider-url-input"
        aria-describedby={providerUrlHelpId}
        placeholder={t("settings.providerChatUrlPlaceholder")}
        value={requestUrl}
        onChange={(e) => setRequestUrl(e.target.value)}
      />
      <div id={providerUrlHelpId} className="mem-hint">
        {t("settings.providerRequestUrlHint")}
      </div>
      {!initial && (
        <>
          <label className="set-label">{t("settings.providerKey")}</label>
          <input
            className="mem-input"
            type="password"
            placeholder={t("settings.providerKeyPlaceholder")}
            value={keyDraft}
            onChange={(e) => setKeyDraft(e.target.value)}
          />
        </>
      )}
      {initial && onSaveKey && apiKeyEnv.trim() && (
        <>
          <label className="set-label">{t("settings.providerKey")}</label>
          {initial.keySource && (
            <div className="mem-hint" title={initial.keySourcePath || undefined}>
              {t("settings.keySource", { source: initial.keySource })}
            </div>
          )}
          <KeyField
            apiKeyEnv={apiKeyEnv.trim()}
            busy={busy || fetchingModels}
            keySet={initial.keySet}
            onSet={(env, value) => onSaveKey(env, value)}
          />
        </>
      )}
      <div className="provider-model-fetch-row">
        <button
          type="button"
          className="btn btn--small"
          disabled={busy || fetchingModels || !canFetch || extraBodyInvalid}
          onClick={() => void fetchModels()}
        >
          {fetchingModels ? t("settings.fetchingModels") : t("settings.testFetchModels")}
        </button>
        <span>{t("settings.testFetchModelsHint")}</span>
      </div>
      {fetchStatus && <div className="provider-fetch-status provider-fetch-status--ok">{fetchStatus}</div>}
      {fetchFallback && <div className="provider-fetch-status provider-fetch-status--warn">{fetchFallback}</div>}
      <label className="set-label">{t("settings.manualModels")}</label>
      <input className="mem-input" placeholder={t("settings.providerModels")} value={models} onChange={(e) => updateManualModels(e.target.value)} />
      <div className="mem-hint">{t("settings.manualModelsHint")}</div>
      <ProviderEditorModelPicker
        candidates={modelCandidateNames}
        selectedModels={modelNames}
        visionModels={visionModelNames}
        visionCapability={effectiveVisionCapability}
        contextWindows={modelContextWindows}
        disabled={busy || fetchingModels}
        onToggleModel={toggleEditorModel}
        onToggleVision={toggleEditorVisionModel}
        onContextWindowChange={updateEditorModelContextWindow}
        onSelectAll={selectAllEditorModels}
        onClear={clearEditorModels}
      />
      <ProviderServiceCapabilities
        supported={effectiveServerWebSearchCapability}
        models={modelNames}
        enabled={webSearch}
        disabled={busy || fetchingModels}
        onChange={setWebSearch}
      />
      {advancedFields}
      <div className="prov-card__actions">
        <button className="btn btn--small" onClick={onCancel} disabled={busy}>
          {t("common.cancel")}
        </button>
        <button className="btn btn--primary btn--small" onClick={() => void save()} disabled={busy || !name.trim() || !effectiveBaseUrl || !models.trim() || extraBodyInvalid}>
          {t("common.save")}
        </button>
      </div>
    </div>
  );
}

function KeyField({
  apiKeyEnv,
  busy,
  keySet = false,
  onSet,
}: {
  apiKeyEnv: string;
  busy: boolean;
  keySet?: boolean;
  onSet: (apiKeyEnv: string, value: string) => Promise<void>;
}) {
  const t = useT();
  const [val, setVal] = useState("");
  if (!apiKeyEnv) return null;
  return (
    <div className="set-key">
      <input
        className="mem-input"
        type="password"
        placeholder={t(keySet ? "settings.updateKey" : "settings.setKey", { env: apiKeyEnv })}
        value={val}
        onChange={(e) => setVal(e.target.value)}
      />
      <button
        className="btn btn--small"
        disabled={busy || !val.trim()}
        onClick={() => {
          void onSet(apiKeyEnv, val.trim());
          setVal("");
        }}
      >
        {t(keySet ? "settings.updateKeyAction" : "settings.saveKey")}
      </button>
    </div>
  );
}

function PermissionsSection({ s, busy, apply }: SectionProps) {
  const t = useT();
  return (
    <>
    <SettingsSection title={t("settings.permissions")} description={t("settings.permissionsModeHint")}>
      <SettingsField label={t("settings.writerMode")}>
        <select
          className="mem-select set-grow"
          value={s.permissions.mode}
          disabled={busy}
          onChange={(e) => void apply(() => app.SetPermissionMode(e.target.value))}
        >
          <option value="ask">{t("settings.modeAsk")}</option>
          <option value="allow">{t("settings.modeAllow")}</option>
          <option value="deny">{t("settings.modeDeny")}</option>
        </select>
      </SettingsField>
    </SettingsSection>
    <SettingsSection title={t("settings.permissionRules")} description={t("settings.ruleForm")}>
      <div className="set-rules-grid">
        {(["deny", "ask", "allow"] as const).map((list) => (
          <RuleList
            key={list}
            list={list}
            rules={s.permissions[list]}
            busy={busy}
            onAdd={async (rule) => { await apply(() => app.AddPermissionRule(list, rule)); }}
            onRemove={async (rule) => { await apply(() => app.RemovePermissionRule(list, rule)); }}
          />
        ))}
      </div>
    </SettingsSection>
    </>
  );
}

function RuleList({
  list,
  rules,
  busy,
  onAdd,
  onRemove,
}: {
  list: string;
  rules: string[];
  busy: boolean;
  onAdd: (rule: string) => Promise<void>;
  onRemove: (rule: string) => Promise<void>;
}) {
  const t = useT();
  const [draft, setDraft] = useState("");
  const add = () => {
    const r = draft.trim();
    if (r) {
      void onAdd(r);
      setDraft("");
    }
  };
  return (
    <div className="set-rules">
      <div className="set-rules__head">
        <div className="set-rules__label">{ruleListLabel(list, t)}</div>
        {ruleListHint(list, t) && <div className="set-rules__hint">{ruleListHint(list, t)}</div>}
      </div>
      <div className="set-rules__chips">
        {rules.length === 0 && <span className="mem-empty">{t("common.none")}</span>}
        {rules.map((r) => (
          <span className="set-rule" key={r}>
            <span className="set-rule__text" title={r}>{r}</span>
            <Tooltip label={t("common.delete")}>
              <button className="set-rule__x" disabled={busy} onClick={() => void onRemove(r)}>
                ✕
              </button>
            </Tooltip>
          </span>
        ))}
      </div>
      <div className="set-rules__add">
        <input
          className="mem-input"
          placeholder={t("settings.addRule", { list })}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") add();
          }}
        />
        <button className="btn btn--small" disabled={busy || !draft.trim()} onClick={add}>
          {t("common.add")}
        </button>
      </div>
    </div>
  );
}

function ruleListLabel(list: string, t: ReturnType<typeof useT>): string {
  switch (list) {
    case "deny":
      return t("settings.ruleDeny");
    case "ask":
      return t("settings.ruleAsk");
    case "allow":
      return t("settings.ruleAllow");
    case "allow_write":
      return t("settings.ruleAllowWrite");
    default:
      return list;
  }
}

function ruleListHint(list: string, t: ReturnType<typeof useT>): string {
  switch (list) {
    case "deny":
      return t("settings.ruleDenyHint");
    case "ask":
      return t("settings.ruleAskHint");
    case "allow":
      return t("settings.ruleAllowHint");
    default:
      return "";
  }
}

type HookScope = "global" | "project";

function HooksSection({ onChanged }: { onChanged: (settings?: SettingsView | null) => void }) {
  const t = useT();
  const [scope, setScope] = useState<HookScope>("global");
  const [view, setView] = useState<HooksSettingsView | null>(null);
  const [jsonText, setJsonText] = useState("");
  const [jsonMessage, setJsonMessage] = useState<string | null>(null);
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [pathMessage, setPathMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async (nextScope: HookScope) => {
    setBusy(true);
    setErr(null);
    try {
      const next = normalizeHooksSettingsView(await app.HooksSettings(nextScope), nextScope);
      setView(next);
      setJsonText(formatHooksJSON(next.hooks, next.events));
      setJsonMessage(null);
      setJsonError(null);
      setPathMessage(null);
    } catch (e) {
      setErr(String((e as Error)?.message ?? e));
      setView(null);
      setJsonText("");
      setJsonMessage(null);
      setJsonError(null);
      setPathMessage(null);
    } finally {
      setBusy(false);
    }
  }, []);

  useEffect(() => {
    void load(scope);
  }, [load, scope]);

  const parseHooksEditorJSON = (raw = jsonText): { hooks: HookConfigView[]; text: string } | null => {
    try {
      const hooks = parseHooksJSON(raw, view?.events ?? [], t);
      const text = formatHooksJSON(hooks, view?.events ?? []);
      setJsonText(text);
      setJsonError(null);
      return { hooks, text };
    } catch (e) {
      setJsonError(t("settings.hooksJsonInvalid", { error: String((e as Error)?.message ?? e) }));
      setJsonMessage(null);
      return null;
    }
  };
  const copyHooksJSON = async () => {
    const parsed = parseHooksEditorJSON();
    if (!parsed) return;
    try {
      await navigator.clipboard?.writeText(parsed.text);
      setJsonMessage(t("settings.hooksJsonCopied"));
    } catch {
      setJsonMessage(t("settings.hooksJsonClipboardUnavailable"));
    }
  };
  const formatHooksEditorJSON = (raw = jsonText) => {
    const parsed = parseHooksEditorJSON(raw);
    if (parsed) setJsonMessage(t("settings.hooksJsonFormatted"));
  };
  const pasteHooksJSON = async () => {
    try {
      const raw = await navigator.clipboard?.readText();
      if (!raw) throw new Error(t("settings.hooksJsonClipboardEmpty"));
      setJsonText(raw);
      formatHooksEditorJSON(raw);
    } catch (e) {
      setJsonError(t("settings.hooksJsonPasteFailed", { error: String((e as Error)?.message ?? e) }));
      setJsonMessage(null);
    }
  };
  const copyHooksPath = async () => {
    const path = view?.path?.trim();
    if (!path) {
      setPathMessage(t("settings.hooksPathUnavailable"));
      return;
    }
    try {
      await navigator.clipboard?.writeText(path);
      setPathMessage(t("settings.hooksPathCopied"));
    } catch {
      setPathMessage(t("settings.hooksJsonClipboardUnavailable"));
    }
  };
  const save = async () => {
    setBusy(true);
    setErr(null);
    try {
      const parsed = parseHooksEditorJSON();
      if (!parsed) return;
      await app.SaveHooksSettingsForRoot(scope, view?.projectRoot?.trim() ?? "", parsed.hooks);
      await load(scope);
      onChanged();
    } catch (e) {
      setErr(String((e as Error)?.message ?? e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      {err && <div className="banner banner--error">{err}</div>}
      <SettingsSection title={t("settings.hooksScopeSection")} description={t("settings.hooksScopeHint")}>
        <SettingsField label={t("settings.hooksScopeField")}>
          <select name="hooks-scope" className="mem-select set-grow" value={scope} disabled={busy} onChange={(e) => setScope(e.target.value === "project" ? "project" : "global")}>
            <option value="global">{t("settings.hooksGlobal")}</option>
            <option value="project">{t("settings.hooksProject")}</option>
          </select>
        </SettingsField>
        <SettingsField label={t("settings.hooksPath")} hint={scope === "project" ? t("settings.hooksPathProjectHint") : t("settings.hooksPathGlobalHint")}>
          <div className="hooks-path-stack">
            <div className={`hooks-path-display${view?.path ? "" : " hooks-path-display--empty"}`}>
              <code className="hooks-path-display__value" title={view?.path || t("settings.hooksPathUnavailable")}>
                {view?.path || t("settings.hooksPathUnavailable")}
              </code>
              <button className="btn btn--small" disabled={busy || !view?.path} onClick={() => void copyHooksPath()}>{t("settings.hooksPathCopy")}</button>
            </div>
            {pathMessage && <div className="hooks-path-display__message">{pathMessage}</div>}
          </div>
        </SettingsField>
      </SettingsSection>

      <SettingsSection
        title={t("settings.hooks")}
        description={scope === "project" ? t("settings.hooksProjectHint") : t("settings.hooksGlobalHint")}
        actions={(
          <button className="btn btn--small btn--primary" disabled={busy} onClick={() => void save()}>{t("common.save")}</button>
        )}
      >
        {view && (
          <div className="hooks-json-panel">
            <div className="hooks-json-panel__head">
              <div>
                <div className="set-rules__label">{t("settings.hooksJsonTitle")}</div>
                <div className="set-rules__hint">{t("settings.hooksJsonHint")}</div>
              </div>
              <div className="hooks-json-panel__actions">
                <button className="btn btn--small" disabled={busy} onClick={() => void copyHooksJSON()}>{t("settings.hooksJsonCopy")}</button>
                <button className="btn btn--small" disabled={busy} onClick={() => void pasteHooksJSON()}>{t("settings.hooksJsonPaste")}</button>
                <button className="btn btn--small" disabled={busy || !jsonText.trim()} onClick={() => formatHooksEditorJSON()}>{t("settings.hooksJsonApply")}</button>
              </div>
            </div>
            <textarea
              name="hooks-json"
              className="mem-textarea hooks-json-panel__textarea"
              value={jsonText}
              disabled={busy}
              spellCheck={false}
              onChange={(e) => {
                setJsonText(e.target.value);
                setJsonMessage(null);
                setJsonError(null);
              }}
            />
            {jsonError && <div className="hooks-json-panel__message hooks-json-panel__message--error">{jsonError}</div>}
            {jsonMessage && <div className="hooks-json-panel__message">{jsonMessage}</div>}
          </div>
        )}
        {!view && <div className="empty">{t("settings.loading")}</div>}
      </SettingsSection>
    </>
  );
}

function normalizeHooksSettingsView(view: HooksSettingsView, scope: HookScope): HooksSettingsView {
  const events = asArray(view?.events).filter(Boolean);
  return {
    scope: view?.scope === "project" ? "project" : scope,
    path: view?.path ?? "",
    projectRoot: view?.projectRoot ?? "",
    trusted: !!view?.trusted,
    events,
    hooks: asArray(view?.hooks).map(normalizeHookConfig).filter((h) => h.event),
  };
}

function formatHooksJSON(hooks: HookConfigView[], eventOrder: string[]): string {
  const grouped: Record<string, Array<Record<string, string | number>>> = {};
  const events = new Set(eventOrder);
  for (const hook of hooks.map(normalizeHookConfig).filter((h) => h.event)) {
    events.add(hook.event);
    const entry: Record<string, string | number> = { command: hook.command };
    if (hook.match) entry.match = hook.match;
    if (hook.description) entry.description = hook.description;
    if ((hook.timeout ?? 0) > 0) entry.timeout = hook.timeout ?? 0;
    if (hook.cwd) entry.cwd = hook.cwd;
    (grouped[hook.event] ||= []).push(entry);
  }
  const ordered: typeof grouped = {};
  for (const event of [...eventOrder, ...Array.from(events).sort()]) {
    if (grouped[event]?.length && !ordered[event]) ordered[event] = grouped[event];
  }
  return JSON.stringify({ hooks: ordered }, null, 2);
}

function parseHooksJSON(raw: string, validEvents: string[], t: ReturnType<typeof useT>): HookConfigView[] {
  const trimmed = raw.trim();
  if (!trimmed) return [];
  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch (e) {
    throw new Error(String((e as Error)?.message ?? e));
  }
  if (Array.isArray(parsed)) {
    return parsed.map((item) => normalizeHookConfig(parseHookArrayItem(item, validEvents, t))).filter((h) => h.event);
  }
  if (!parsed || typeof parsed !== "object") {
    throw new Error(t("settings.hooksJsonExpectedObjectArray"));
  }
  const obj = parsed as Record<string, unknown>;
  const hooksValue = obj.hooks && typeof obj.hooks === "object" && !Array.isArray(obj.hooks) ? obj.hooks : obj;
  return flattenHooksMap(hooksValue as Record<string, unknown>, validEvents, t);
}

function parseHookArrayItem(item: unknown, validEvents: string[], t: ReturnType<typeof useT>): HookConfigView {
  if (!item || typeof item !== "object" || Array.isArray(item)) throw new Error(t("settings.hooksJsonItemObject"));
  const obj = item as Record<string, unknown>;
  const event = stringField(obj, "event") || "PreToolUse";
  if (validEvents.length > 0 && !validEvents.includes(event)) throw new Error(t("settings.hooksJsonUnknownEvent", { event }));
  return {
    event,
    match: stringField(obj, "match"),
    command: stringField(obj, "command"),
    description: stringField(obj, "description"),
    timeout: numberField(obj, "timeout"),
    cwd: stringField(obj, "cwd"),
  };
}

function flattenHooksMap(hooks: Record<string, unknown>, validEvents: string[], t: ReturnType<typeof useT>): HookConfigView[] {
  const valid = new Set(validEvents);
  const out: HookConfigView[] = [];
  for (const [event, value] of Object.entries(hooks)) {
    if (valid.size > 0 && !valid.has(event)) throw new Error(t("settings.hooksJsonUnknownEvent", { event }));
    const items = Array.isArray(value) ? value : [value];
    for (const item of items) {
      if (!item || typeof item !== "object" || Array.isArray(item)) throw new Error(t("settings.hooksJsonEventItemObject", { event }));
      const obj = item as Record<string, unknown>;
      out.push(normalizeHookConfig({
        event,
        match: stringField(obj, "match"),
        command: stringField(obj, "command"),
        description: stringField(obj, "description"),
        timeout: numberField(obj, "timeout"),
        cwd: stringField(obj, "cwd"),
      }));
    }
  }
  return out.filter((h) => h.event);
}

function stringField(obj: Record<string, unknown>, key: string): string {
  const value = obj[key];
  return typeof value === "string" ? value : "";
}

function numberField(obj: Record<string, unknown>, key: string): number {
  const value = obj[key];
  return typeof value === "number" && Number.isFinite(value) ? Math.floor(value) : 0;
}

function normalizeHookConfig(h: HookConfigView): HookConfigView {
  return {
    event: h.event || "PreToolUse",
    match: h.match ?? "",
    command: h.command ?? "",
    description: h.description ?? "",
    timeout: h.timeout && h.timeout > 0 ? Math.floor(h.timeout) : 0,
    cwd: h.cwd ?? "",
  };
}

function effectiveShellLabel(value: string, t: ReturnType<typeof useT>): string {
  switch (value) {
    case "git-bash": return t("settings.effectiveShellGitBash");
    case "pwsh": return t("settings.effectiveShellPwsh");
    case "powershell": return t("settings.effectiveShellPowershell");
    case "bash": return t("settings.effectiveShellBash");
    case "auto": return t("common.auto");
    default: return value.trim() || t("common.none");
  }
}

function SandboxSection({ s, busy, apply, windows }: SectionProps & { windows: boolean }) {
  const t = useT();
  const sb = s.sandbox;
  const [root, setRoot] = useState(sb.workspaceRoot);
  const effectiveWriteRoots = asArray(sb.effectiveWriteRoots).filter((path) => String(path).trim());
  const effectiveShell = effectiveShellLabel(String(sb.effectiveShell || sb.shell || ""), t);
  const set = (next: Partial<typeof sb>) =>
    apply(() => app.SetSandbox(next.bash ?? sb.bash, next.network ?? sb.network, next.workspaceRoot ?? sb.workspaceRoot, next.allowWrite ?? sb.allowWrite, next.shell ?? sb.shell));
  const reload = () => apply(() => app.ReloadSettings());

  return (
    <SettingsSection
      title={t("settings.sandboxTitle")}
      description={t("settings.sandboxBoundaryHint")}
      actions={
        <Tooltip label={t("settings.reloadSessionConfigHint")}>
          <button className="btn btn--small" disabled={busy} title={t("settings.reloadSessionConfigHint")} onClick={() => void reload()}>
            <RefreshCw size={14} aria-hidden="true" />
            <span>{t("settings.reloadSessionConfig")}</span>
          </button>
        </Tooltip>
      }
    >
      <SettingsField label={t("settings.shellInterpreter")}>
        <select className="mem-select set-grow" value={sb.shell || "auto"} disabled={busy} onChange={(e) => void set({ shell: e.target.value })}>
          <option value="auto">{windows ? t("settings.shellAutoWindows") : t("settings.shellAuto")}</option>
          <option value="bash">{t("settings.shellBash")}</option>
          <option value="powershell">{t("settings.shellPowershell")}</option>
          <option value="pwsh">{t("settings.shellPwsh")}</option>
        </select>
      </SettingsField>
      <SettingsField label={t("settings.effectiveShell")}>
        <div className="settings-readonly-field">{effectiveShell}</div>
      </SettingsField>
      <SettingsField label={t("settings.bashSandbox")} hint={windows ? t("settings.bashUnavailableWindows") : undefined}>
        {/* Windows has no OS-level Bash backend and config.BashModeForGOOS fixes
            the effective value to off. Keep the control visibly immutable and
            omit enforce so the UI cannot imply a dormant capability. */}
        <select className="mem-select set-grow" value={windows ? "off" : sb.bash} disabled={busy || windows} onChange={(e) => void set({ bash: e.target.value })}>
          {!windows && <option value="enforce">{t("settings.bashEnforce")}</option>}
          <option value="off">{t("settings.bashOff")}</option>
        </select>
      </SettingsField>
      <SettingsField label={t("settings.allowNetwork")}>
        <label className="set-check set-check--inline">
          <input type="checkbox" checked={sb.network} disabled={busy} onChange={(e) => void set({ network: e.target.checked })} />
          {t("settings.allowNetwork")}
        </label>
      </SettingsField>
      <SettingsField label={t("settings.workspaceRoot")}>
        <input
          className="mem-input set-grow"
          placeholder={t("settings.workspaceDefault")}
          value={root}
          disabled={busy}
          onChange={(e) => setRoot(e.target.value)}
          onBlur={() => root !== sb.workspaceRoot && void set({ workspaceRoot: root })}
        />
      </SettingsField>
      <SettingsField label={t("settings.effectiveWriteRoots")} hint={t("settings.effectiveWriteRootsHint")} stacked>
        <div className="set-rules set-rules--readonly">
          <div className="set-rules__chips">
            {effectiveWriteRoots.length === 0 && <span className="mem-empty">{t("settings.noEffectiveWriteRoots")}</span>}
            {effectiveWriteRoots.map((path, index) => (
              <span className="set-rule set-rule--path" key={`${path}-${index}`}>
                {path}
              </span>
            ))}
          </div>
        </div>
      </SettingsField>
      <RuleList
        list="allow_write"
        rules={sb.allowWrite}
        busy={busy}
        onAdd={async (d) => { await set({ allowWrite: [...sb.allowWrite, d] }); }}
        onRemove={async (d) => { await set({ allowWrite: sb.allowWrite.filter((x) => x !== d) }); }}
      />
    </SettingsSection>
  );
}

const MB = 1024 * 1024;
const mb = (n: number) => (n / MB).toFixed(1);

// UpdatesSection is the manual side of the auto-updater: it shows the startup
// check preference, running version, and a Check button, then the same state
// machine the top banner uses (useUpdater) — a single "update and restart"
// action with inline progress and errors.
function UpdatesSection({
  configPath,
  shadowedByPath,
  checkUpdates,
  telemetry,
  metrics,
  settingsBusy,
  applySettings,
}: {
  configPath: string;
  shadowedByPath?: string;
  checkUpdates: boolean;
  telemetry: boolean;
  metrics: boolean;
  settingsBusy: boolean;
  applySettings: (fn: () => Promise<void>) => Promise<boolean>;
}) {
  const t = useT();
  const { status, check, apply: applyUpdate, openDownload, abandonPending } = useUpdater();
  const [version, setVersion] = useState("");
  useEffect(() => {
    app.Version().then(setVersion).catch(() => {});
  }, []);

  const updaterBusy =
    status.kind === "checking" ||
    status.kind === "downloading" ||
    status.kind === "verifying" ||
    status.kind === "authorizing" ||
    status.kind === "installing" ||
    status.kind === "relaunching";
  const updateStatus =
    status.kind === "checking" ? t("updater.checking") :
    status.kind === "upToDate" ? t("updater.upToDate") :
    status.kind === "available" ? t("updater.available", { v: status.info.latest }) :
    status.kind === "downloading" ? t("updater.downloading", {
      done: mb(status.received),
      total: mb(status.total),
      pct: status.total > 0 ? Math.round((status.received / status.total) * 100) : 0,
    }) :
    status.kind === "verifying" ? t("updater.verifying") :
    status.kind === "authorizing" ? t("updater.authorizing") :
    status.kind === "installing" ? (
      status.info?.requiresElevation || status.info?.installMode === "deb"
        ? t("updater.installingPackage")
        : t("updater.installing")
    ) :
    status.kind === "relaunching" || status.kind === "done" ? t("updater.done") :
    status.kind === "error" ? "" :
    "";
  const updateStatusTone =
    status.kind === "error" ? "error" :
    status.kind === "available" ? "available" :
    status.kind === "upToDate" || status.kind === "done" || status.kind === "relaunching" ? "success" :
    status.kind === "checking" || updaterBusy ? "busy" :
    "neutral";
  const updateErrorTitle = status.kind === "error"
    ? status.disposition === "recovery"
      ? t("updater.recoveryBlocked")
      : status.disposition === "manual"
        ? t("updater.manualUpdateRequired")
        : t("updater.failed", { msg: status.message })
    : "";
  const updateErrorHint = status.kind === "error"
    ? status.disposition === "recovery"
      ? t("updater.recoveryHint")
      : status.disposition === "manual"
        ? t("updater.manualFallbackHint")
        : ""
    : "";
  const downloadIsPrimary = status.kind === "error" && status.disposition !== "retryable";

  return (
    <SettingsSection>
      <SettingsField
        className="settings-field--wide-copy updates-control"
        label={
          <div className="updates-control__summary">
            <div className="updates-control__version">
              {t("updater.currentVersion", { v: version || "…" })}
            </div>
            <div className={`updates-control__status updates-control__status--${updateStatusTone}`} role="status" aria-live="polite">
              {updateStatus && (
                <>
                  {updateStatusTone === "success" && <CheckCircle2 size={14} aria-hidden="true" />}
                  {updateStatusTone === "busy" && <Loader2 className="updates-control__spinner" size={14} aria-hidden="true" />}
                  <span>{updateStatus}</span>
                </>
              )}
            </div>
          </div>
        }
      >
        <div className="updates-control__controls">
          <Tooltip label={t("updater.checkButton")}>
            <button
              className="chip chip--icon"
              type="button"
              disabled={settingsBusy || updaterBusy}
              aria-label={t("updater.checkButton")}
              onClick={() => void check()}
            >
              <RefreshCw className={status.kind === "checking" ? "updates-control__spinner" : undefined} size={14} aria-hidden="true" />
            </button>
          </Tooltip>
        </div>
      </SettingsField>
      <div
        className="updates-control__hint"
        style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: "4px 8px" }}
      >
        <span>{t("updater.officialReleaseHint")}</span>
        <button
          className="btn btn--small"
          type="button"
          onClick={openDownload}
          style={{
            height: "auto",
            minHeight: 0,
            padding: 0,
            borderColor: "transparent",
            background: "transparent",
            color: "var(--fg-dim)",
            textDecoration: "underline",
            textUnderlineOffset: 2,
          }}
        >
          {t("updater.officialDownload")}
          <ExternalLink size={13} aria-hidden="true" />
        </button>
      </div>
      {status.kind === "available" && (
        <div className="updates-control__action">
          <div className="updates-control__action-copy">
            {!status.info.canSelfUpdate && <div>{status.info.manualReason || t("updater.macHint")}</div>}
          </div>
          <button
            className="btn btn--primary btn--small"
            disabled={settingsBusy || updaterBusy}
            onClick={() => applyUpdate(status.info)}
          >
            {status.info.canSelfUpdate ? t("updater.updateAndRestart") : t("updater.goToDownload")}
          </button>
        </div>
      )}
      {status.kind === "error" && (
        <div
          className="banner banner--update banner--error"
          role="alert"
          style={{ alignItems: "flex-start", flexWrap: "wrap", marginBottom: 12 }}
        >
          <div style={{ flex: "1 1 360px", minWidth: 0 }}>
            <div>{updateErrorTitle}</div>
            {updateErrorHint && <div className="banner__hint">{updateErrorHint}</div>}
            {status.disposition !== "retryable" && (
              <div className="banner__hint" style={{ overflowWrap: "anywhere" }}>
                {t("updater.errorDetails", { msg: status.message })}
              </div>
            )}
          </div>
          <span className="banner__spacer" />
          {status.disposition === "recovery" && (
            <button
              className="btn btn--small"
              type="button"
              disabled={settingsBusy || updaterBusy}
              onClick={() => void abandonPending()}
            >
              {t("updater.discardPrevious")}
            </button>
          )}
          {downloadIsPrimary && (
            <button className="btn btn--primary btn--small" type="button" onClick={openDownload}>
              {t("updater.officialDownload")}
              <ExternalLink size={14} aria-hidden="true" />
            </button>
          )}
          <button
            className={`btn btn--small${downloadIsPrimary ? "" : " btn--primary"}`}
            type="button"
            disabled={settingsBusy || updaterBusy}
            onClick={() => status.info ? applyUpdate(status.info) : void check()}
          >
            {t("updater.retry")}
          </button>
        </div>
      )}
      <SettingsField
        className="settings-field--wide-copy"
        label={t("changelog.title")}
        hint={t("changelog.subtitle")}
      >
        <button className="btn btn--small" onClick={() => void openExternal("https://reasonix.io/changelog/")}>
          {t("changelog.openWeb")}
          <ExternalLink size={14} aria-hidden="true" />
        </button>
      </SettingsField>
      <SettingsField
        className="settings-field--wide-copy"
        label={t("feedback.title")}
        hint={t("feedback.subtitle")}
      >
        <div className="settings-inline-controls">
          <button
            className="btn btn--small"
            onClick={() => void openExternal("https://github.com/esengine/DeepSeek-Reasonix/issues/new/choose")}
          >
            {t("feedback.submitIssue")}
            <ExternalLink size={14} aria-hidden="true" />
          </button>
          <button
            className="btn btn--small"
            onClick={() => void openExternal("https://github.com/esengine/DeepSeek-Reasonix/issues")}
          >
            {t("feedback.viewIssues")}
            <ExternalLink size={14} aria-hidden="true" />
          </button>
        </div>
      </SettingsField>
      <details
        className="provider-editor-advanced"
        style={{
          marginTop: 0,
          borderRight: 0,
          borderBottom: 0,
          borderLeft: 0,
          borderRadius: 0,
          background: "transparent",
        }}
      >
        <summary style={{ padding: "0 2px" }}>
          <span className="provider-editor-advanced__title">
            <ChevronDown className="provider-editor-advanced__icon" size={16} aria-hidden="true" />
            {t("updater.privacyAndUpdatePreferences")}
          </span>
        </summary>
        <div className="provider-editor-advanced__body">
          <SettingsField
            className="settings-field--wide-copy"
            label={t("updater.autoCheckLabel")}
            hint={t("updater.autoCheckHint")}
          >
            <ToggleSegment
              value={checkUpdates}
              disabled={settingsBusy}
              onChange={(enabled) => void applySettings(() => app.SetDesktopCheckUpdates(enabled))}
            />
          </SettingsField>
          <SettingsField
            className="settings-field--wide-copy"
            label={t("settings.telemetryLabel")}
            hint={t("settings.telemetryHint")}
          >
            <ToggleSegment
              value={telemetry}
              disabled={settingsBusy}
              onChange={(enabled) => void applySettings(() => app.SetDesktopTelemetry(enabled))}
            />
          </SettingsField>
          <SettingsField
            className="settings-field--wide-copy"
            label={t("settings.metricsLabel")}
            hint={t("settings.metricsHint")}
          >
            <ToggleSegment
              value={metrics}
              disabled={settingsBusy}
              onChange={(enabled) => void applySettings(() => app.SetDesktopMetrics(enabled))}
            />
          </SettingsField>
          {configPath && (
            <Tooltip label={configPath} fill block className="mem-hint settings-config-path">
              {t("settings.config", { path: configPath })}
            </Tooltip>
          )}
          {shadowedByPath && (
            <Tooltip label={shadowedByPath} fill block className="mem-hint settings-config-path settings-config-path--shadowed">
              {t("settings.configShadowed", { path: shadowedByPath })}
            </Tooltip>
          )}
        </div>
      </details>
    </SettingsSection>
  );
}

function ToggleSegment({
  value,
  disabled,
  onLabel,
  offLabel,
  onChange,
}: {
  value: boolean;
  disabled: boolean;
  onLabel?: string;
  offLabel?: string;
  onChange: (value: boolean) => void;
}) {
  const t = useT();
  return (
    <div className="set-seg">
      <button
        type="button"
        className={`set-seg__btn${value ? " set-seg__btn--on" : ""}`}
        disabled={disabled}
        onClick={() => onChange(true)}
      >
        {onLabel ?? t("settings.toggleOn")}
      </button>
      <button
        type="button"
        className={`set-seg__btn${!value ? " set-seg__btn--on" : ""}`}
        disabled={disabled}
        onClick={() => onChange(false)}
      >
        {offLabel ?? t("settings.toggleOff")}
      </button>
    </div>
  );
}
