// Context window ring — Reasonix-style context usage gauge driven by
// AtomReasonX telemetry (cache/context metrics). Structure and CSS class names
// mirror Reasonix ContextWindowRing.tsx so the visual contract stays aligned.

import React from "react";
import type { AtomReasonXTelemetryView } from "../lib/telemetry";
import {
  formatCacheHitRate,
  formatMoney,
  formatTokensCompact,
} from "../lib/telemetry";

export type ContextRingTone = "good" | "notice" | "warn";

export function contextWindowStatus(rawUsagePct: number, compactPct: number): ContextRingTone {
  if (rawUsagePct > 100) return "warn";
  const usagePct = Math.min(100, Math.max(0, rawUsagePct));
  if (usagePct >= 90) return "warn";
  if (compactPct > 0 && usagePct >= compactPct) return "warn";
  if (compactPct > 0 && usagePct >= Math.max(0, compactPct - 10)) return "notice";
  return "good";
}

const RING = 22;
const RING_R = (RING - 3) / 2;
const RING_C = 2 * Math.PI * RING_R;

export const ContextWindowRing: React.FC<{
  telemetry: AtomReasonXTelemetryView;
  enabled?: boolean;
}> = ({ telemetry, enabled = true }) => {
  const [open, setOpen] = React.useState(false);
  const enterTimer = React.useRef<ReturnType<typeof setTimeout> | null>(null);
  const leaveTimer = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  const used = telemetry.session_tokens;
  const windowTokens = telemetry.context_window;
  const rawUsagePct = windowTokens > 0 ? Math.round((used / windowTokens) * 100) : 0;
  const usagePct = Math.min(100, Math.max(0, rawUsagePct));
  const compactRatio = telemetry.compression_threshold > 0 && windowTokens > 0
    ? Math.min(0.95, telemetry.compression_threshold / windowTokens)
    : 0.78;
  const compactPct = Math.round(compactRatio * 100);
  const tone = contextWindowStatus(rawUsagePct, compactPct);
  const ringOffset = RING_C * (1 - usagePct / 100);

  const usage = telemetry.provider_usage;
  const cacheHit = usage.cache_read_input_tokens ?? 0;
  const cacheMiss = usage.prompt_tokens ?? 0;
  const cacheRate = formatCacheHitRate(cacheHit, cacheMiss);
  const compactTokens = windowTokens > 0 ? Math.round(windowTokens * compactRatio) : 0;
  const tokensToCompact = compactTokens > used ? compactTokens - used : 0;

  const onEnter = React.useCallback(() => {
    if (leaveTimer.current != null) clearTimeout(leaveTimer.current);
    enterTimer.current = setTimeout(() => setOpen(true), 200);
  }, []);

  const onLeave = React.useCallback(() => {
    if (enterTimer.current != null) clearTimeout(enterTimer.current);
    leaveTimer.current = setTimeout(() => setOpen(false), 120);
  }, []);

  React.useEffect(() => () => {
    if (enterTimer.current != null) clearTimeout(enterTimer.current);
    if (leaveTimer.current != null) clearTimeout(leaveTimer.current);
  }, []);

  if (!enabled) return null;

  return (
    <div className="context-ring-wrap" onMouseEnter={onEnter} onMouseLeave={onLeave}>
      <button
        type="button"
        className={`context-ring context-ring--${tone}${open ? " context-ring--open" : ""}`}
        aria-label={`Context window usage: ${used} of ${windowTokens} tokens (${rawUsagePct}%)`}
        onClick={() => setOpen((previous) => !previous)}
      >
        <svg width={RING} height={RING} viewBox={`0 0 ${RING} ${RING}`} className="context-ring__svg" aria-hidden="true">
          <circle className="context-ring__track" cx={RING / 2} cy={RING / 2} r={RING_R} fill="none" strokeWidth={3} />
          <circle
            className="context-ring__arc"
            cx={RING / 2}
            cy={RING / 2}
            r={RING_R}
            fill="none"
            strokeWidth={3}
            strokeLinecap="round"
            strokeDasharray={RING_C}
            strokeDashoffset={ringOffset}
            transform={`rotate(-90 ${RING / 2} ${RING / 2})`}
          />
        </svg>
      </button>
      {open && (
        <div className={`context-ring-popover context-ring-popover--${tone}`} role="dialog" aria-label="Context window usage">
          <div className="context-ring-popover__inner">
            <div className="context-ring-popover__header">
              <span className="context-ring-popover__title">
                {formatTokensCompact(used)} / {formatTokensCompact(windowTokens)}
              </span>
              <span className="context-ring-popover__pct">{rawUsagePct}%</span>
            </div>
            <div className="context-ring-popover__gauge">
              <div className="context-ring-popover__bar">
                <span className="context-ring-popover__fill" style={{ width: `${usagePct}%` }} />
                <span className="context-ring-popover__mark context-ring-popover__mark--compact" style={{ left: `${compactPct}%` }} />
                <span className="context-ring-popover__mark context-ring-popover__mark--attention" style={{ left: "30%" }} />
              </div>
            </div>
            <div className="context-ring-popover__rows">
              <div className="context-ring-popover__row">
                <span className="context-ring-popover__label">Distance to compact</span>
                <span className="context-ring-popover__value">{formatTokensCompact(tokensToCompact)}</span>
              </div>
              <div className="context-ring-popover__row">
                <span className="context-ring-popover__label">Requests</span>
                <span className="context-ring-popover__value">{telemetry.request_count}</span>
              </div>
              <div className="context-ring-popover__row">
                <span className="context-ring-popover__label">Prompt cache</span>
                <span className="context-ring-popover__value">{cacheRate}</span>
              </div>
              <div className="context-ring-popover__row">
                <span className="context-ring-popover__label">Cache avg</span>
                <span className="context-ring-popover__value">{(telemetry.average_hit_rate * 100).toFixed(1)}%</span>
              </div>
              <div className="context-ring-popover__row">
                <span className="context-ring-popover__label">Retrieval hits</span>
                <span className="context-ring-popover__value">{telemetry.retrieval_hit_count}</span>
              </div>
              <div className="context-ring-popover__row">
                <span className="context-ring-popover__label">Turn cost</span>
                <span className="context-ring-popover__value">{formatMoney(telemetry.current_turn_cost)}</span>
              </div>
              <div className="context-ring-popover__row">
                <span className="context-ring-popover__label">Session cost</span>
                <span className="context-ring-popover__value">{formatMoney(telemetry.session_cost)}</span>
              </div>
              <div className="context-ring-popover__row">
                <span className="context-ring-popover__label">Balance</span>
                <span className="context-ring-popover__value context-ring-popover__value--accent">
                  {telemetry.balance > 0 ? `$${telemetry.balance.toFixed(2)}` : "-"}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
