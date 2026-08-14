import { describe, expect, it } from "vitest";
import {
  defaultModelForProvider,
  registryForProvider,
  resolveProviderEndpoint,
} from "../lib/providerEndpoints";
import type {
  ProviderConfigStatusEntry,
  ProviderRegistryStatusEntry,
} from "../contracts/types";

const registry: ProviderRegistryStatusEntry[] = [
  {
    provider: "deepseek",
    brand: null,
    priority: 10,
    provider_kind: "model_provider",
    api_format: "openai_compatible",
    requires_api_key: true,
    api_key_env: "DEEPSEEK_API_KEY",
    base_url: null,
    base_url_config_key: null,
    base_url_template: null,
    default_model: null,
    default_models: ["deepseek-v4-pro", "deepseek-v4-flash"],
    default_model_config_key: null,
    supports: [],
    docs_url: null,
    requires_workspace_id: false,
    supports_cache: true,
    context_window_tokens: 128000,
    usage_field_mapping: {},
    price_input_per_1m_tokens: null,
    price_output_per_1m_tokens: null,
    price_cache_read_per_1m_tokens: null,
  },
  {
    provider: "aliyun_dashscope",
    brand: null,
    priority: 20,
    provider_kind: "model_provider",
    api_format: "openai_compatible",
    requires_api_key: true,
    api_key_env: "ALIYUN_API_KEY",
    base_url: null,
    base_url_config_key: null,
    base_url_template: "https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
    default_model: null,
    default_models: ["qwen-plus"],
    default_model_config_key: null,
    supports: [],
    docs_url: null,
    requires_workspace_id: true,
    supports_cache: false,
    context_window_tokens: 131072,
    usage_field_mapping: {},
    price_input_per_1m_tokens: null,
    price_output_per_1m_tokens: null,
    price_cache_read_per_1m_tokens: null,
  },
];

const configFor = (provider: string, overrides: Partial<ProviderConfigStatusEntry> = {}): ProviderConfigStatusEntry => ({
  provider,
  brand: null,
  priority: 10,
  provider_kind: "model_provider",
  requires_api_key: true,
  has_api_key: false,
  key_fingerprint: null,
  validation_state: "missing",
  enabled: false,
  base_url: null,
  default_model: null,
  workspace_id: null,
  ...overrides,
});

describe("resolveProviderEndpoint", () => {
  it("uses the built-in endpoint table for known providers", () => {
    const entry = registryForProvider("deepseek", registry);
    const resolved = resolveProviderEndpoint(entry, configFor("deepseek"));
    expect(resolved).toEqual({ builtin: true, url: "https://api.deepseek.com/v1" });
  });

  it("resolves template placeholders with the workspace id", () => {
    const entry = registryForProvider("aliyun_dashscope", registry);
    const withWorkspace = resolveProviderEndpoint(
      entry,
      configFor("aliyun_dashscope", { workspace_id: "ws-abc" }),
    );
    expect(withWorkspace.url).toBe("https://ws-abc.cn-beijing.maas.aliyuncs.com/compatible-mode/v1");

    const missingWorkspace = resolveProviderEndpoint(entry, configFor("aliyun_dashscope"));
    expect(missingWorkspace.url).toBeNull();
    expect(missingWorkspace.hint).toContain("workspace id");
  });

  it("labels private relays and falls back to custom config for unknown providers", () => {
    const relay = resolveProviderEndpoint(undefined, configFor("private_new_api"));
    expect(relay.builtin).toBe(true);
    expect(relay.url).toBeNull();
    expect(relay.hint).toContain("Private relay");

    const custom = resolveProviderEndpoint(
      undefined,
      configFor("some_custom", { base_url: "https://relay.example/v1" }),
    );
    expect(custom).toEqual({ builtin: false, url: "https://relay.example/v1" });
  });
});

describe("defaultModelForProvider / registryForProvider", () => {
  it("returns the first registry default model", () => {
    expect(defaultModelForProvider(registry[0])).toBe("deepseek-v4-pro");
    expect(defaultModelForProvider(registry[1])).toBe("qwen-plus");
  });

  it("returns null when no defaults are registered", () => {
    expect(defaultModelForProvider(undefined)).toBeNull();
  });

  it("finds registry entries by provider id", () => {
    expect(registryForProvider("deepseek", registry)?.provider).toBe("deepseek");
    expect(registryForProvider("missing", registry)).toBeUndefined();
    expect(registryForProvider("deepseek")).toBeUndefined();
  });
});
