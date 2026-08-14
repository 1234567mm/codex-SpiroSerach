// Provider endpoints — built-in base URLs for official model providers so the
// user only supplies an API key (Reasonix preset-provider model). Endpoints
// resolve from the provider preset registry first (data/provider-presets.json,
// mirroring cherry-studio's provider-registry providers.json), then the live
// registry template, then the configured base_url.

import type {
  ProviderConfigStatusEntry,
  ProviderRegistryStatusEntry,
} from "../contracts/types";
import presetsData from "../data/provider-presets.json";

export interface ProviderPreset {
  id: string;
  name: string;
  brand?: string | null;
  kind: string;
  requires_api_key: boolean;
  supports_cache?: boolean;
  base_url?: string | null;
  base_url_template?: string | null;
  requires_workspace_id?: boolean;
  endpoint_note?: string | null;
  default_models: string[];
  context_window_tokens?: number | null;
}

export interface ResolvedProviderEndpoint {
  /** Whether the endpoint comes from a built-in/template preset (vs custom). */
  builtin: boolean;
  /** Resolved URL, or null when no built-in endpoint is known. */
  url: string | null;
  /** Human hint when the URL needs a workspace id (e.g. Aliyun MaaS). */
  hint?: string;
}

const PRESETS: ProviderPreset[] = (presetsData as { providers: ProviderPreset[] }).providers;

export const providerPresets = (): ProviderPreset[] => PRESETS;

export const presetForProvider = (providerId: string): ProviderPreset | undefined =>
  PRESETS.find((preset) => preset.id === providerId);

export function resolveProviderEndpoint(
  registry?: ProviderRegistryStatusEntry,
  config?: ProviderConfigStatusEntry,
): ResolvedProviderEndpoint {
  const providerId = config?.provider ?? registry?.provider ?? "";
  const preset = presetForProvider(providerId);
  if (preset) {
    if (preset.base_url) return { builtin: true, url: preset.base_url };
    if (preset.base_url_template) {
      const workspaceId = (config?.workspace_id ?? "").trim();
      if (preset.base_url_template.includes("{WorkspaceId}")) {
        if (!workspaceId) {
          return {
            builtin: true,
            url: null,
            hint: "This endpoint needs a workspace id (register workspace_id in provider config).",
          };
        }
        return { builtin: true, url: preset.base_url_template.split("{WorkspaceId}").join(workspaceId) };
      }
      return { builtin: true, url: preset.base_url_template };
    }
    if (preset.endpoint_note) {
      return { builtin: true, url: null, hint: preset.endpoint_note };
    }
  }
  const template = registry?.base_url_template?.trim();
  if (template) {
    const workspaceId = (config?.workspace_id ?? "").trim();
    if (template.includes("{WorkspaceId}")) {
      if (!workspaceId) {
        return {
          builtin: true,
          url: null,
          hint: "This endpoint needs a workspace id (register workspace_id in provider config).",
        };
      }
      return { builtin: true, url: template.split("{WorkspaceId}").join(workspaceId) };
    }
    return { builtin: true, url: template };
  }
  return { builtin: false, url: config?.base_url ?? null };
}

/** Default model id for a provider, from the preset registry's default_models. */
export function defaultModelForProvider(registry?: ProviderRegistryStatusEntry): string | null {
  const providerId = registry?.provider ?? "";
  const preset = presetForProvider(providerId);
  if (preset && preset.default_models.length > 0) return preset.default_models[0];
  const models = registry?.default_models ?? [];
  return models.length > 0 ? models[0] : null;
}

/** Context window tokens for a provider, from the preset registry. */
export function contextWindowForProvider(providerId: string): number | null {
  return presetForProvider(providerId)?.context_window_tokens ?? null;
}

/** Provider registry entry lookup by provider id. */
export function registryForProvider(
  providerId: string,
  registry?: ProviderRegistryStatusEntry[],
): ProviderRegistryStatusEntry | undefined {
  return (registry ?? []).find((entry) => entry.provider === providerId);
}
