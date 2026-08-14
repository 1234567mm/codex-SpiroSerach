import { describe, expect, it } from "vitest";
import fixture from "../fixtures/atomreasonx-ui-fixture.json";
import type { AtomReasonXWorkspaceState } from "../contracts/types";
import {
  cacheHitTone,
  currentTurnCacheRate,
  formatCacheHitRate,
  formatMoney,
  formatTokenCount,
  formatTokensCompact,
  rateTone,
  telemetryFieldsToMap,
  toTelemetryView,
} from "../lib/telemetry";

const telemetry = (fixture as unknown as AtomReasonXWorkspaceState).telemetry;

describe("telemetry fields parsing", () => {
  it("maps telemetry fields to a lookup map", () => {
    const map = telemetryFieldsToMap(telemetry.fields);
    expect(map.retrieval_hit_count).toBe(3);
    expect(map.context_window).toBe(128000);
    expect(map.provider_usage).toMatchObject({ cache_read_input_tokens: 80 });
  });

  it("builds a typed telemetry view from fixture fields", () => {
    const view = toTelemetryView(telemetry);
    expect(view.model_provider).toBe("fake-private-new-api");
    expect(view.session_tokens).toBe(1250);
    expect(view.context_window).toBe(128000);
    expect(view.context_usage_percent).toBe(1);
    expect(view.average_hit_rate).toBe(0.42);
    expect(view.request_count).toBe(5);
    expect(view.provider_usage).toMatchObject({
      cache_read_input_tokens: 80,
      prompt_tokens: 150,
      completion_tokens: 50,
    });
  });

  it("tolerates missing telemetry and non-numeric fields", () => {
    const view = toTelemetryView(undefined);
    expect(view.session_tokens).toBe(0);
    expect(view.model_provider).toBeUndefined();
    expect(view.provider_usage).toEqual({});
    const odd = toTelemetryView({
      schema_version: "v1",
      fields: [
        { name: "session_tokens", value: "n/a", source: "estimated" },
        { name: "model_provider", value: 42, source: "provider_reported" },
      ],
    });
    expect(odd.session_tokens).toBe(0);
    expect(odd.model_provider).toBeUndefined();
  });
});

describe("metric formatting (Reasonix formats)", () => {
  it("formats compact token counts", () => {
    expect(formatTokensCompact(0)).toBe("0");
    expect(formatTokensCompact(150)).toBe("150");
    expect(formatTokensCompact(1250)).toBe("1.3k");
    expect(formatTokensCompact(128000)).toBe("128k");
    expect(formatTokensCompact(1_500_000)).toBe("1.5M");
  });

  it("formats full token counts with separators", () => {
    expect(formatTokenCount(1250)).toBe("1,250");
    expect(formatTokenCount(0)).toBe("-");
    expect(formatTokenCount(undefined)).toBe("-");
  });

  it("computes cache hit rates and tones", () => {
    expect(formatCacheHitRate(80, 150)).toBe("34.78%");
    expect(formatCacheHitRate(0, 0)).toBe("-");
    expect(cacheHitTone(80, 20)).toBe("good");
    expect(cacheHitTone(60, 40)).toBe("notice");
    expect(cacheHitTone(10, 90)).toBe("warn");
    expect(cacheHitTone(0, 0)).toBeUndefined();
    expect(rateTone(0.9)).toBe("good");
    expect(rateTone(0.6)).toBe("notice");
    expect(rateTone(0.2)).toBe("critical");
  });

  it("derives the current-turn cache rate from provider usage", () => {
    expect(currentTurnCacheRate({ cache_read_input_tokens: 80, prompt_tokens: 150 })).toBe("34.8%");
    expect(currentTurnCacheRate({})).toBeNull();
    expect(currentTurnCacheRate(undefined)).toBeNull();
  });

  it("formats money values", () => {
    expect(formatMoney(0.012)).toBe("$0.0120");
    expect(formatMoney(1.5)).toBe("$1.500");
    expect(formatMoney(0)).toBe("-");
  });
});
