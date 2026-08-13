import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { SettingsModal, buildModelConfigWritePayload, buildModelSettingsCommandPayload } from "../components/SettingsModal";
import type { ProviderConfigStatusEntry } from "../contracts/types";
import fixture from "../fixtures/atomreasonx-ui-fixture.json";

const modelEntry: ProviderConfigStatusEntry = {
  provider: "deepseek",
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
};

describe("SettingsModal Models panel", () => {
  it("renders model providers from sanitized settings state", () => {
    const settings = fixture.settings as unknown as {
      providers: ProviderConfigStatusEntry[];
    };
    const markup = renderToStaticMarkup(
      <SettingsModal
        categories={["Models"]}
        modelSettings={{
          schema_version: "v33.sanitized_config_status.v1",
          producer_version: "v33",
          config_version: 0,
          providers: settings.providers,
        }}
      />,
    );
    expect(markup).toContain("Models");
    expect(markup).toContain("private_new_api");
    expect(markup).toContain("deepseek");
    expect(markup).toContain("tencent_hunyuan");
    expect(markup).toContain("volcengine_ark");
    expect(markup).toContain("no key");
  });

  it("disables controls and explains missing backend", () => {
    const markup = renderToStaticMarkup(
      <SettingsModal
        categories={["Models"]}
        modelSettings={{
          schema_version: "v33.sanitized_config_status.v1",
          producer_version: "v33",
          config_version: 0,
          providers: [modelEntry],
        }}
      />,
    );
    expect(markup).toContain("Model configuration backend unavailable");
    expect(markup).toContain("disabled");
  });

  it("builds model command payloads with provider_scope model", () => {
    const base = buildModelSettingsCommandPayload(modelEntry);
    expect(base).toEqual({ provider: "deepseek", provider_scope: "model" });

    const write = buildModelConfigWritePayload(modelEntry, {
      enabled: true,
      base_url: "https://relay.example/v1",
      default_model: "deepseek-chat",
    });
    expect(write).toEqual({
      provider: "deepseek",
      provider_scope: "model",
      config: {
        enabled: true,
        base_url: "https://relay.example/v1",
        default_model: "deepseek-chat",
      },
    });
  });
});
