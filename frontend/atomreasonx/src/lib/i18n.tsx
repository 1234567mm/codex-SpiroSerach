// i18n is the localization seam of the AtomReasonX desktop UI. Adapted from the
// Reasonix desktop lib/i18n.tsx (https://github.com/esengine/DeepSeek-Reasonix,
// MIT), trimmed to the two supported UI languages (en / zh).
//
// The active locale lives in React state behind a context — flipping it
// re-renders the whole tree. A module-level mirror (`currentLocale`) lets
// non-React code translate too; the provider keeps it fresh on every render.
//
// The language preference is persisted through the Rust settings store
// (`langPref` inside atomreasonx-settings.json). localStorage is only read as
// a legacy fallback (older builds / browser dev mode) and written back when
// the Tauri bridge is unavailable.

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { ReactNode } from "react";
import { en, type DictKey } from "../locales/en";
import { readDesktopSettings, writeDesktopSettings } from "./settings-bridge";

export type Locale = "en" | "zh";
export type { DictKey };
// LangPref is the stored preference: "" means auto-detect from the OS.
export type LangPref = "" | "en" | "zh";

type Dict = Record<DictKey, string>;

const DICTS: Partial<Record<Locale, Dict>> = { en };
const localeLoads = new Map<Locale, Promise<void>>();
const STORAGE_KEY = "reasonix-lang";
const RUST_SETTINGS_LANG_KEY = "langPref";

// currentLocale mirrors the active locale for callers outside React.
let currentLocale: Locale = "en";

// Whimsical present-participles cycled in the status line while a turn runs.
// Kept out of the dict (it's an array, and purely decorative).
export const SPINNER_WORDS: Record<Locale, string[]> = {
  en: [
    "Frolicking", "Pondering", "Noodling", "Brewing", "Conjuring", "Cogitating",
    "Percolating", "Ruminating", "Simmering", "Synthesizing", "Tinkering",
    "Marinating", "Crunching", "Hatching", "Mulling", "Whirring", "Forging",
    "Spelunking", "Puttering", "Vibing",
  ],
  zh: [
    "嬉游中", "沉思中", "鼓捣中", "酝酿中", "施法中", "苦思中",
    "渗滤中", "反刍中", "文火慢炖", "合成中", "修补中",
    "腌制入味", "嘎吱运算", "孵化中", "盘算中", "嗡嗡运转", "锻造中",
    "探洞中", "摆弄中", "来感觉了",
  ],
};

export function detectLocale(pref: LangPref): Locale {
  if (pref === "en" || pref === "zh") return pref;
  const nav = typeof navigator !== "undefined" ? navigator.language.toLowerCase() : "en";
  return nav.startsWith("zh") ? "zh" : "en";
}

export function preloadLocale(locale: Locale): Promise<void> {
  if (DICTS[locale]) return Promise.resolve();
  const pending = localeLoads.get(locale);
  if (pending) return pending;
  const load = locale === "zh"
    ? import("../locales/zh").then(({ zh }) => { DICTS.zh = zh; })
    : Promise.resolve();
  localeLoads.set(locale, load);
  void load.catch(() => localeLoads.delete(locale));
  return load;
}

export function preloadDetectedLocale(pref: LangPref = ""): Promise<void> {
  return preloadLocale(detectLocale(pref));
}

export function normalizeLangPref(v: unknown): LangPref {
  return v === "en" || v === "zh" ? v : "";
}

/** Reads the legacy localStorage preference (older builds / browser mode). */
export function readLegacyLangPref(): LangPref {
  const v = typeof localStorage !== "undefined" ? localStorage.getItem(STORAGE_KEY) : null;
  return normalizeLangPref(v);
}

export function clearLegacyLangPref(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    /* private mode / no storage */
  }
}

function readLegacyOrEmptyPref(): LangPref {
  try {
    return readLegacyLangPref();
  } catch {
    return "";
  }
}

function storePrefFallback(pref: LangPref): void {
  try {
    localStorage.setItem(STORAGE_KEY, pref);
  } catch {
    /* private mode / no storage */
  }
}

/** Persists the language preference (Rust settings store; localStorage fallback). */
export async function persistLangPref(pref: LangPref): Promise<void> {
  const normalized = normalizeLangPref(pref);
  try {
    await writeDesktopSettings({ [RUST_SETTINGS_LANG_KEY]: normalized });
    clearLegacyLangPref();
  } catch {
    // Bridge unavailable (browser dev mode or very old backend): keep the
    // legacy localStorage copy so the choice survives a reload.
    storePrefFallback(normalized);
  }
}

/** Reads the persisted language preference (Rust settings store, then legacy). */
export async function readPersistedLangPref(): Promise<LangPref> {
  try {
    const settings = await readDesktopSettings();
    const pref = normalizeLangPref(settings[RUST_SETTINGS_LANG_KEY]);
    const legacy = readLegacyOrEmptyPref();
    if (pref === "" && legacy !== "") {
      // One-time migration of the legacy localStorage choice into the Rust
      // settings store, then drop the legacy copy.
      await persistLangPref(legacy);
      return legacy;
    }
    if (legacy !== "") {
      clearLegacyLangPref();
    }
    return pref;
  } catch {
    return readLegacyOrEmptyPref();
  }
}

// translate resolves a key for a locale and fills {placeholders}. Missing keys
// fall back to English, then to the raw key, so the UI never renders blank.
function translate(locale: Locale, key: DictKey, vars?: Record<string, string | number>): string {
  const s = DICTS[locale]?.[key] ?? en[key] ?? key;
  if (!vars) return s;
  return s.replace(/\{(\w+)\}/g, (_, k) => (vars[k] !== undefined ? String(vars[k]) : `{${k}}`));
}

// t is the non-reactive translator for code outside React. It reads the module
// mirror, which the provider keeps in sync.
export function t(key: DictKey, vars?: Record<string, string | number>): string {
  return translate(currentLocale, key, vars);
}

export function getLocale(): Locale {
  return currentLocale;
}

export type Translator = (key: DictKey, vars?: Record<string, string | number>) => string;

interface I18nValue {
  locale: Locale;
  pref: LangPref;
  setPref: (pref: LangPref) => void;
  t: Translator;
}

const I18nContext = createContext<I18nValue | null>(null);

export function LocaleProvider({ children }: { children: ReactNode }) {
  const [pref, setPrefState] = useState<LangPref>(() => readLegacyOrEmptyPref());
  const [dictionaryVersion, setDictionaryVersion] = useState(0);
  const locale = detectLocale(pref);
  currentLocale = locale; // keep the mirror fresh for non-React callers

  // Load the persisted preference from the Rust settings store on mount
  // (async; the legacy value seeds the initial render to avoid a flash).
  useEffect(() => {
    let cancelled = false;
    void readPersistedLangPref().then((persisted) => {
      if (!cancelled && persisted !== "") {
        setPrefState(persisted);
      }
    });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (typeof document === "undefined") return;
    document.documentElement.lang = locale === "zh" ? "zh-CN" : "en";
  }, [locale]);

  useEffect(() => {
    if (DICTS[locale]) return;
    let cancelled = false;
    void preloadLocale(locale).then(() => {
      if (!cancelled) setDictionaryVersion((version) => version + 1);
    });
    return () => {
      cancelled = true;
    };
  }, [locale]);

  // setPref updates the live UI and persists the choice through the settings
  // store (fire-and-forget; the next boot re-reads it).
  const setPref = useCallback((next: LangPref) => {
    const normalized = normalizeLangPref(next);
    setPrefState(normalized);
    void persistLangPref(normalized);
  }, []);

  const tt = useCallback<Translator>(
    (key, vars) => translate(detectLocale(pref), key, vars),
    [dictionaryVersion, pref],
  );

  return <I18nContext.Provider value={{ locale, pref, setPref, t: tt }}>{children}</I18nContext.Provider>;
}

export function useI18n(): I18nValue {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used within a LocaleProvider");
  return ctx;
}

// useT is the common shorthand: just the translator.
export function useT(): Translator {
  return useI18n().t;
}
