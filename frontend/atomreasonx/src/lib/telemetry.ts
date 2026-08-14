// Telemetry helpers — parse AtomReasonX telemetry fields into a typed map and
// format metrics the Reasonix way (compact tokens, cache hit rates, money).

import type { AtomReasonXTelemetryState, TelemetryField } from "../contracts/types";

export interface ProviderUsage {
  cache_read_input_tokens?: number;
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  [key: string]: unknown;
}

export interface AtomReasonXTelemetryView {
  model_provider?: string;
  retrieval_hit_count: number;
  average_hit_rate: number;
  current_turn_tokens: number;
  session_tokens: number;
  context_window: number;
  context_usage_percent: number;
  context_remaining: number;
  compression_threshold: number;
  current_turn_cost: number;
  session_cost: number;
  total_cost: number;
  balance: number;
  active_session_state: string;
  request_count: number;
  provider_usage: ProviderUsage;
}

export function telemetryFieldsToMap(fields: TelemetryField[]): Record<string, unknown> {
  const map: Record<string, unknown> = {};
  for (const field of fields) {
    map[field.name] = field.value;
  }
  return map;
}

export function toTelemetryView(telemetry?: AtomReasonXTelemetryState): AtomReasonXTelemetryView {
  const map = telemetryFieldsToMap(telemetry?.fields ?? []);
  const asNumber = (value: unknown): number => {
    const n = Number(value);
    return Number.isFinite(n) ? n : 0;
  };
  const providerUsageRaw = map.provider_usage;
  return {
    model_provider: typeof map.model_provider === "string" ? map.model_provider : undefined,
    retrieval_hit_count: asNumber(map.retrieval_hit_count),
    average_hit_rate: asNumber(map.average_hit_rate),
    current_turn_tokens: asNumber(map.current_turn_tokens),
    session_tokens: asNumber(map.session_tokens),
    context_window: asNumber(map.context_window),
    context_usage_percent: asNumber(map.context_usage_percent),
    context_remaining: asNumber(map.context_remaining),
    compression_threshold: asNumber(map.compression_threshold),
    current_turn_cost: asNumber(map.current_turn_cost),
    session_cost: asNumber(map.session_cost),
    total_cost: asNumber(map.total_cost),
    balance: asNumber(map.balance),
    active_session_state: typeof map.active_session_state === "string" ? map.active_session_state : "unknown",
    request_count: asNumber(map.request_count),
    provider_usage:
      typeof providerUsageRaw === "object" && providerUsageRaw !== null
        ? (providerUsageRaw as ProviderUsage)
        : {},
  };
}

/** Compact token count: 12.5k / 1.2M (Reasonix fmtCompact). */
export function formatTokensCompact(n: number): string {
  if (!Number.isFinite(n) || n <= 0) return "0";
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1).replace(/\.0$/, "") + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1).replace(/\.0$/, "") + "k";
  return String(Math.round(n));
}

/** Full token count with thousands separators. */
export function formatTokenCount(n?: number): string {
  if (typeof n !== "number" || !Number.isFinite(n) || n <= 0) return "-";
  return n.toLocaleString();
}

/**
 * Cache hit rate from hit/miss token counts (Reasonix formatCacheHitRate).
 * Returns "-" when there is no usage denominator.
 */
export function formatCacheHitRate(hitTokens: number, missTokens: number): string {
  const denom = hitTokens + missTokens;
  if (denom <= 0) return "-";
  return `${((hitTokens / denom) * 100).toFixed(2)}%`;
}

export type CacheHitTone = "good" | "notice" | "warn" | undefined;

/** Tone for a cache hit rate: ≥80% good, ≥60% notice, else warn (Reasonix cacheHitTone). */
export function cacheHitTone(hitTokens: number, missTokens: number): CacheHitTone {
  const denom = hitTokens + missTokens;
  if (denom <= 0) return undefined;
  const pct = (hitTokens / denom) * 100;
  if (pct >= 80) return "good";
  if (pct >= 60) return "notice";
  return "warn";
}

/** Tone for an already-computed rate percentage (0..1). */
export function rateTone(pct: number): "good" | "notice" | "critical" {
  if (pct >= 0.8) return "good";
  if (pct >= 0.5) return "notice";
  return "critical";
}

/** Current-turn cache rate from provider_usage (cache_read_input_tokens vs prompt_tokens). */
export function currentTurnCacheRate(usage?: ProviderUsage): string | null {
  if (!usage) return null;
  const hit = usage.cache_read_input_tokens ?? 0;
  const miss = usage.prompt_tokens ?? 0;
  const denom = hit + miss;
  if (denom <= 0) return null;
  return `${((hit / denom) * 100).toFixed(1)}%`;
}

export function formatMoney(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "-";
  if (value >= 1) return `$${value.toFixed(3)}`;
  return `$${value.toFixed(4)}`;
}
