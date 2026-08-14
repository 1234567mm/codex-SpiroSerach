// Bottom status bar — Reasonix statusbar format driven by AtomReasonX
// telemetry: model, prompt-cache rate (turn + session), tokens, cost, balance.
// Class names mirror Reasonix StatusBar/stat CSS so the visual contract stays
// aligned.

import React from "react";
import { Activity, Database, Percent, Wallet, Zap } from "lucide-react";
import type { AtomReasonXTelemetryState } from "../contracts/types";
import {
  currentTurnCacheRate,
  formatMoney,
  formatTokenCount,
  rateTone,
  toTelemetryView,
} from "../lib/telemetry";

const RATE_TONE_CLASS: Record<"good" | "notice" | "critical", string> = {
  good: "statusbar__rate-value--good",
  notice: "statusbar__rate-value--notice",
  critical: "statusbar__rate-value--critical",
};

export const BottomTelemetryBar: React.FC<{
  telemetry: AtomReasonXTelemetryState;
}> = ({ telemetry }) => {
  const view = toTelemetryView(telemetry);
  const model = view.model_provider ?? "not configured";
  const turnCacheRate = currentTurnCacheRate(view.provider_usage);
  const turnTone = turnCacheRate !== null ? rateTone(parseFloat(turnCacheRate) / 100) : null;
  const avgRatePct = view.average_hit_rate > 0 ? view.average_hit_rate * 100 : null;
  const avgTone = avgRatePct !== null ? rateTone(view.average_hit_rate) : null;

  return (
    <div className="statusbar" role="status" aria-label="Workbench telemetry">
      <span className="statusbar__metric statusbar__metric--model" title={`Model provider: ${view.model_provider ?? "none configured"}`}>
        <span className="stat statusbar__model">
          <span className="statusbar__dot" aria-hidden="true" />
          <b>{model}</b>
        </span>
      </span>

      <span className="statusbar__group">
        <span className="statusbar__metric statusbar__metric--cache" title="Prompt cache hit rate this turn (cache_read_input_tokens / prompt_tokens)">
          <span className="stat statusbar__cache">
            <span className="stat__label stat__label--icon" aria-hidden="true"><Percent size={12} /></span>
            <span className="stat__label">Cache</span>
            <b className={turnTone ? RATE_TONE_CLASS[turnTone] : "stat__value--empty"}>{turnCacheRate ?? "-"}</b>
          </span>
        </span>

        <span className="statusbar__metric statusbar__metric--avg" title="Session-average cache hit rate">
          <span className="stat statusbar__avg">
            <span className="stat__label stat__label--icon" aria-hidden="true"><Activity size={12} /></span>
            <span className="stat__label">Avg</span>
            <b className={avgTone ? RATE_TONE_CLASS[avgTone] : "stat__value--empty"}>
              {avgRatePct !== null ? `${avgRatePct.toFixed(1)}%` : "-"}
            </b>
          </span>
        </span>

        <span className="statusbar__metric statusbar__metric--tokens" title="Session tokens (across all turns)">
          <span className="stat statusbar__tokens">
            <span className="stat__label stat__label--icon" aria-hidden="true"><Database size={12} /></span>
            <span className="stat__label">Tokens</span>
            <b>{formatTokenCount(view.session_tokens)}</b>
          </span>
        </span>

        <span className="statusbar__metric statusbar__metric--turn-tokens" title="Tokens in the current turn">
          <span className="stat statusbar__turn-tokens">
            <span className="stat__label stat__label--icon" aria-hidden="true"><Zap size={12} /></span>
            <span className="stat__label">Turn</span>
            <b>{formatTokenCount(view.current_turn_tokens)}</b>
          </span>
        </span>

        <span className="statusbar__metric statusbar__metric--cost" title="Estimated session cost">
          <span className="stat statusbar__cost">
            <span className="stat__label stat__label--icon" aria-hidden="true"><Wallet size={12} /></span>
            <span className="stat__label">Cost</span>
            <b>{formatMoney(view.session_cost)}</b>
          </span>
        </span>

        <span className="statusbar__metric statusbar__metric--balance" title="Account balance">
          <span className="stat statusbar__balance">
            <span className="stat__label">Balance</span>
            <b>{view.balance > 0 ? `$${view.balance.toFixed(2)}` : "-"}</b>
          </span>
        </span>
      </span>
    </div>
  );
};
