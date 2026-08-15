import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import React from "react";
import {
  detectLocale,
  normalizeLangPref,
  preloadLocale,
  readPersistedLangPref,
  LocaleProvider,
  useT,
  type DictKey,
} from "../lib/i18n";
import { zh } from "../locales/zh";

const MISSING_KEY = "definitely.missing.key" as DictKey;

const Probe: React.FC<{
  keys: DictKey[];
  vars?: Record<string, string | number>;
}> = ({ keys, vars }) => {
  const t = useT();
  return <span>{keys.map((key) => t(key, vars)).join("|")}</span>;
};

describe("i18n locale detection", () => {
  const withNavigatorLanguage = (language: string | undefined, run: () => void) => {
    const original = Object.getOwnPropertyDescriptor(globalThis, "navigator");
    if (language === undefined) {
      Reflect.deleteProperty(globalThis, "navigator");
    } else {
      Object.defineProperty(globalThis, "navigator", {
        value: { language },
        configurable: true,
      });
    }
    try {
      run();
    } finally {
      if (original) {
        Object.defineProperty(globalThis, "navigator", original);
      } else {
        Reflect.deleteProperty(globalThis, "navigator");
      }
    }
  };

  it("passes explicit language preferences through", () => {
    expect(detectLocale("en")).toBe("en");
    expect(detectLocale("zh")).toBe("zh");
  });

  it("detects Chinese from the system language", () => {
    withNavigatorLanguage("zh-CN", () => {
      expect(detectLocale("")).toBe("zh");
    });
  });

  it("falls back to English without any signal", () => {
    withNavigatorLanguage(undefined, () => {
      expect(detectLocale("")).toBe("en");
    });
  });
});

describe("i18n language preference normalization", () => {
  it("accepts only the supported languages", () => {
    expect(normalizeLangPref("en")).toBe("en");
    expect(normalizeLangPref("zh")).toBe("zh");
    expect(normalizeLangPref("")).toBe("");
  });

  it("rejects unsupported or malformed values", () => {
    expect(normalizeLangPref("zh-TW")).toBe("");
    expect(normalizeLangPref("fr")).toBe("");
    expect(normalizeLangPref(123)).toBe("");
    expect(normalizeLangPref(undefined)).toBe("");
  });
});

describe("i18n translation", () => {
  it("translates English keys with placeholder substitution", () => {
    const markup = renderToStaticMarkup(
      <LocaleProvider>
        <Probe
          keys={["common.close", "topbar.startupError", MISSING_KEY]}
          vars={{ msg: "boom" }}
        />
      </LocaleProvider>,
    );
    expect(markup).toContain("Close|startup error: boom|definitely.missing.key");
  });

  it("missing keys fall back to the raw key instead of rendering blank", () => {
    const markup = renderToStaticMarkup(
      <LocaleProvider>
        <Probe keys={[MISSING_KEY]} />
      </LocaleProvider>,
    );
    expect(markup).toContain("definitely.missing.key");
  });

  it("loads the Chinese dictionary and keeps placeholder names aligned", async () => {
    await preloadLocale("zh");
    expect(zh["common.close"]).toBe("关闭");
    expect(zh["topbar.startupError"]).toBe("启动错误：{msg}");
    expect(zh[MISSING_KEY]).toBeUndefined();
  });
});

describe("i18n persistence fallbacks", () => {
  it("reads an empty preference when no bridge or storage exists", async () => {
    // Node test environment: no __TAURI__ bridge, no localStorage.
    await expect(readPersistedLangPref()).resolves.toBe("");
  });
});
