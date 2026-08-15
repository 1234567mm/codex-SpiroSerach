// AtomReasonX theme management, adapted from Reasonix desktop lib/theme.ts
// (https://github.com/esengine/DeepSeek-Reasonix, MIT). The stylesheet follows
// the OS via prefers-color-scheme unless data-theme forces "dark" or "light";
// a separate data-theme-style attribute selects a visual direction
// (graphite/aurora/slate/carbon/nocturne/amber) orthogonal to theme, so every
// direction supports both light & dark.

export type Theme = "auto" | "light" | "dark";
export type ResolvedTheme = Exclude<Theme, "auto">;

export const THEME_STYLES = [
  "graphite",
  "aurora",
  "slate",
  "carbon",
  "nocturne",
  "amber",
] as const;

export type ThemeStyle = (typeof THEME_STYLES)[number];

export const THEME_STYLE_LABELS: Record<ThemeStyle, string> = {
  graphite: "Graphite",
  aurora: "Aurora",
  slate: "Slate",
  carbon: "Carbon",
  nocturne: "Nocturne",
  amber: "Amber",
};

export const THEME_STYLE_DESCRIPTIONS: Record<ThemeStyle, string> = {
  graphite: "Paper-like surfaces, hairline borders, orange accent.",
  aurora: "Misty violet surfaces with a blue-green glow.",
  slate: "Cool blue-grey, muted and technical.",
  carbon: "Neutral studio greys, precise and calm.",
  nocturne: "Soft violet, deep and relaxed.",
  amber: "Warm orange, friendly and bright.",
};

export const THEME_STYLE_SWATCHES: Record<ThemeStyle, { bg: string; fg: string; accent: string }> = {
  graphite: { bg: "#0c0d10", fg: "#f1f1ef", accent: "#ff6a3d" },
  aurora: { bg: "#0e0d18", fg: "#ecebf7", accent: "#8b7cff" },
  slate: { bg: "#0d1116", fg: "#ecf1f5", accent: "#38a3b8" },
  carbon: { bg: "#0e1116", fg: "#eef1f4", accent: "#3f93d8" },
  nocturne: { bg: "#101019", fg: "#eceaf3", accent: "#818cf8" },
  amber: { bg: "#0e0d0b", fg: "#efe8dd", accent: "#d4632f" },
};

const LEGACY_STYLE_MAP: Record<string, ThemeStyle> = {
  ember: "carbon",
  midnight: "nocturne",
  sandstone: "amber",
  porcelain: "nocturne",
  linen: "amber",
  glacier: "slate",
};

const DEFAULT_THEME_STYLE: ThemeStyle = "graphite";
const DEFAULT_THEME: Theme = "auto";

const THEME_KEY = "atomreasonx-theme";
const STYLE_KEY = "atomreasonx-theme-style";
const AUTO_THEME_MEDIA_QUERY = "(prefers-color-scheme: light)";

let currentTheme: Theme = DEFAULT_THEME;
let currentThemeStyle: ThemeStyle = DEFAULT_THEME_STYLE;

export function normalizeThemePreference(value: unknown): Theme {
  if (typeof value === "object" && value !== null) {
    return normalizeThemePreference((value as { mode?: unknown }).mode);
  }
  if (typeof value !== "string") return DEFAULT_THEME;
  switch (value) {
    case "auto":
      return "auto";
    case "light":
    case "focus":
    case "forest":
      return "light";
    case "dark":
    case "midnight":
    case "contrast":
      return "dark";
    default:
      return DEFAULT_THEME;
  }
}

export function isThemeStyle(value: unknown): value is ThemeStyle {
  return typeof value === "string" && (THEME_STYLES as readonly string[]).includes(value);
}

export function getTheme(): Theme {
  return currentTheme;
}

export function getResolvedTheme(theme: Theme = getTheme()): ResolvedTheme {
  if (theme === "light" || theme === "dark") return theme;
  if (typeof window !== "undefined" && window.matchMedia?.(AUTO_THEME_MEDIA_QUERY).matches) {
    return "light";
  }
  return "dark";
}

export function getThemeStyle(_theme?: Theme): ThemeStyle {
  return currentThemeStyle;
}

export function normalizeThemeStyleForTheme(
  style: string | undefined,
  _theme?: Theme,
): ThemeStyle {
  if (typeof style !== "string") return DEFAULT_THEME_STYLE;
  if (isThemeStyle(style)) return style;
  return LEGACY_STYLE_MAP[style] ?? DEFAULT_THEME_STYLE;
}

export function applyTheme(
  theme: Theme,
  style: ThemeStyle = getThemeStyle(),
  options: { persist?: boolean } = {},
): void {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.removeAttribute("data-theme-mode");
  root.removeAttribute("data-theme-scheme");
  if (theme === "auto") root.removeAttribute("data-theme");
  else root.setAttribute("data-theme", theme);

  const nextStyle: ThemeStyle = isThemeStyle(style) ? style : DEFAULT_THEME_STYLE;
  currentTheme = theme;
  currentThemeStyle = nextStyle;
  root.setAttribute("data-theme-style", nextStyle);

  if (options.persist !== false) {
    try {
      localStorage.setItem(THEME_KEY, JSON.stringify(theme));
      localStorage.setItem(STYLE_KEY, JSON.stringify(nextStyle));
    } catch {
      // storage unavailable (private mode / SSR): theme still applies for this session
    }
  }
}

export function readThemePreference(): { theme: Theme; style: ThemeStyle; hasValue: boolean } {
  if (typeof localStorage === "undefined") {
    return { theme: DEFAULT_THEME, style: DEFAULT_THEME_STYLE, hasValue: false };
  }
  let rawTheme: string | null = null;
  let rawStyle: string | null = null;
  try {
    rawTheme = localStorage.getItem(THEME_KEY);
    rawStyle = localStorage.getItem(STYLE_KEY);
  } catch {
    return { theme: DEFAULT_THEME, style: DEFAULT_THEME_STYLE, hasValue: false };
  }
  const hasValue = rawTheme !== null || rawStyle !== null;
  let theme = DEFAULT_THEME;
  if (rawTheme) {
    try {
      theme = normalizeThemePreference(JSON.parse(rawTheme) as unknown);
    } catch {
      theme = normalizeThemePreference(rawTheme);
    }
  }
  const style = normalizeThemeStyleForTheme(rawStyle ?? undefined);
  return { theme, style, hasValue };
}

/** Applies the persisted (or default) theme on app boot. Call once before render. */
export function applyPersistedTheme(): { theme: Theme; style: ThemeStyle } {
  const { theme, style } = readThemePreference();
  applyTheme(theme, style, { persist: false });
  return { theme, style };
}
