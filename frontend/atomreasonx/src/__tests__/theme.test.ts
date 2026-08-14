import { describe, expect, it } from "vitest";
import {
  applyPersistedTheme,
  applyTheme,
  getResolvedTheme,
  getTheme,
  getThemeStyle,
  isThemeStyle,
  normalizeThemePreference,
  normalizeThemeStyleForTheme,
  readThemePreference,
  THEME_STYLES,
} from "../lib/theme";

const noop = () => undefined;

describe("theme preference normalization", () => {
  it("maps legacy and object values to the three modes", () => {
    expect(normalizeThemePreference("auto")).toBe("auto");
    expect(normalizeThemePreference("light")).toBe("light");
    expect(normalizeThemePreference("dark")).toBe("dark");
    expect(normalizeThemePreference("focus")).toBe("light");
    expect(normalizeThemePreference("midnight")).toBe("dark");
    expect(normalizeThemePreference("contrast")).toBe("dark");
    expect(normalizeThemePreference({ mode: "dark" })).toBe("dark");
    expect(normalizeThemePreference("unknown")).toBe("auto");
    expect(normalizeThemePreference(null)).toBe("auto");
  });

  it("validates theme styles and maps legacy style ids", () => {
    expect(THEME_STYLES).toEqual([
      "graphite", "aurora", "slate", "carbon", "nocturne", "amber",
    ]);
    for (const style of THEME_STYLES) {
      expect(isThemeStyle(style)).toBe(true);
    }
    expect(isThemeStyle("neon")).toBe(false);
    expect(normalizeThemeStyleForTheme("ember")).toBe("carbon");
    expect(normalizeThemeStyleForTheme("glacier")).toBe("slate");
    expect(normalizeThemeStyleForTheme("carbon")).toBe("carbon");
    expect(normalizeThemeStyleForTheme("bogus")).toBe("graphite");
  });
});

describe("applyTheme DOM contract", () => {
  it("sets data-theme and data-theme-style attributes on documentElement", () => {
    const attributes = new Map<string, string>();
    const removed = new Set<string>();
    const stored = new Map<string, string>();
    const originalDocument = globalThis.document;
    const originalLocalStorage = globalThis.localStorage;
    globalThis.document = {
      documentElement: {
        setAttribute: (name: string, value: string) => { attributes.set(name, value); },
        removeAttribute: (name: string) => { removed.add(name); attributes.delete(name); },
      },
    } as unknown as Document;
    globalThis.localStorage = {
      getItem: (key: string) => stored.get(key) ?? null,
      setItem: (key: string, value: string) => { stored.set(key, value); },
      removeItem: noop,
    } as unknown as Storage;

    try {
      applyTheme("dark", "aurora");
      expect(attributes.get("data-theme")).toBe("dark");
      expect(attributes.get("data-theme-style")).toBe("aurora");
      expect(stored.get("atomreasonx-theme")).toBe('"dark"');
      expect(stored.get("atomreasonx-theme-style")).toBe('"aurora"');
      expect(getTheme()).toBe("dark");
      expect(getThemeStyle()).toBe("aurora");

      applyTheme("auto", "graphite");
      expect(attributes.has("data-theme")).toBe(false);
      expect(attributes.get("data-theme-style")).toBe("graphite");
      expect(removed.has("data-theme")).toBe(true);
    } finally {
      globalThis.document = originalDocument;
      globalThis.localStorage = originalLocalStorage;
    }
  });

  it("resolves auto to the OS scheme and persists on boot", () => {
    const originalDocument = globalThis.document;
    const originalMatchMedia = globalThis.window?.matchMedia;
    globalThis.document = {
      documentElement: {
        setAttribute: noop,
        removeAttribute: noop,
      },
    } as unknown as Document;
    try {
      const saved = globalThis.window?.matchMedia;
      Object.defineProperty(globalThis, "window", {
        value: { matchMedia: () => ({ matches: true }) },
        configurable: true,
      });
      expect(getResolvedTheme("auto")).toBe("light");
      Object.defineProperty(globalThis, "window", {
        value: { matchMedia: () => ({ matches: false }) },
        configurable: true,
      });
      expect(getResolvedTheme("auto")).toBe("dark");
      Object.defineProperty(globalThis, "window", { value: saved, configurable: true });
    } finally {
      globalThis.document = originalDocument;
      Object.defineProperty(globalThis, "window", {
        value: originalMatchMedia ? { matchMedia: originalMatchMedia } : undefined,
        configurable: true,
      });
    }
  });

  it("readThemePreference falls back to defaults when storage is empty", () => {
    const originalLocalStorage = globalThis.localStorage;
    globalThis.localStorage = {
      getItem: () => null,
      setItem: noop,
      removeItem: noop,
    } as unknown as Storage;
    try {
      const preference = readThemePreference();
      expect(preference.theme).toBe("auto");
      expect(preference.style).toBe("graphite");
      expect(preference.hasValue).toBe(false);
      expect(applyPersistedTheme()).toEqual({ theme: "auto", style: "graphite" });
    } finally {
      globalThis.localStorage = originalLocalStorage;
    }
  });
});
