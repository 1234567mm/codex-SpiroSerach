"""Session telemetry contract for V33.

Defines the backend session telemetry contract consumed by V33B's bottom
telemetry bar (B5) and right inspector Overview (B4). Every field carries a
source label. The read plane must not trigger live provider calls.

Source labels (canonical, underscore form):
  provider_reported  — provider/relay returned the real value
  runtime_computed    — local runtime computed from real events
  estimated           — local fallback estimate (only when safe query unavailable)
  unavailable         — currently not available
  stale               — expired value

`observed` is not a standalone label; it is the parent concept of
`provider_reported` + `runtime_computed`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

SESSION_TELEMETRY_SCHEMA_VERSION = "v33.session_telemetry.v1"

SourceLabel = Literal[
    "provider_reported",
    "runtime_computed",
    "estimated",
    "unavailable",
    "stale",
]

# Canonical field → preferred source mapping
FIELD_SOURCE_MAP: dict[str, tuple[SourceLabel, SourceLabel]] = {
    "model_provider": ("provider_reported", "runtime_computed"),
    "retrieval_hit_count": ("runtime_computed", "unavailable"),
    "average_hit_rate": ("runtime_computed", "unavailable"),
    "current_turn_tokens": ("provider_reported", "runtime_computed"),
    "session_tokens": ("runtime_computed", "unavailable"),
    "context_window": ("provider_reported", "runtime_computed"),
    "context_usage_percent": ("runtime_computed", "unavailable"),
    "context_remaining": ("runtime_computed", "unavailable"),
    "compression_threshold": ("runtime_computed", "unavailable"),
    "current_turn_cost": ("provider_reported", "estimated"),
    "session_cost": ("runtime_computed", "estimated"),
    "total_cost": ("runtime_computed", "estimated"),
    "balance": ("provider_reported", "estimated"),
    "active_session_state": ("runtime_computed", "unavailable"),
    "request_count": ("runtime_computed", "unavailable"),
    "provider_usage": ("provider_reported", "unavailable"),
}

# Fields that must NEVER be downgraded to estimated
NEVER_ESTIMATED_FIELDS = {"average_hit_rate", "retrieval_hit_count", "request_count"}


@dataclass(frozen=True)
class TelemetryField:
    name: str
    value: Any
    source: SourceLabel

    def __post_init__(self) -> None:
        if self.source == "estimated" and self.name in NEVER_ESTIMATED_FIELDS:
            raise ValueError(
                f"field '{self.name}' must never be marked 'estimated'; "
                f"it is {FIELD_SOURCE_MAP.get(self.name)}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "value": self.value, "source": self.source}


def build_telemetry(
    *,
    model_provider: str | None = None,
    retrieval_hit_count: int | None = None,
    average_hit_rate: float | None = None,
    current_turn_tokens: int | None = None,
    session_tokens: int | None = None,
    context_window: int | None = None,
    context_usage_percent: float | None = None,
    context_remaining: int | None = None,
    compression_threshold: int | None = None,
    current_turn_cost: float | None = None,
    session_cost: float | None = None,
    total_cost: float | None = None,
    balance: float | None = None,
    active_session_state: str | None = None,
    request_count: int | None = None,
    provider_usage: dict[str, Any] | None = None,
    # Source overrides — used when the caller knows the actual source
    sources: dict[str, SourceLabel] | None = None,
) -> dict[str, Any]:
    """Build a session telemetry contract payload with source labels.

    Each field is assigned its preferred source from FIELD_SOURCE_MAP unless
    overridden. If the value is None and the source would be 'estimated',
    the source becomes 'unavailable' instead.
    """
    overrides = sources or {}
    fields: list[TelemetryField] = []

    raw_values = {
        "model_provider": model_provider,
        "retrieval_hit_count": retrieval_hit_count,
        "average_hit_rate": average_hit_rate,
        "current_turn_tokens": current_turn_tokens,
        "session_tokens": session_tokens,
        "context_window": context_window,
        "context_usage_percent": context_usage_percent,
        "context_remaining": context_remaining,
        "compression_threshold": compression_threshold,
        "current_turn_cost": current_turn_cost,
        "session_cost": session_cost,
        "total_cost": total_cost,
        "balance": balance,
        "active_session_state": active_session_state,
        "request_count": request_count,
        "provider_usage": provider_usage,
    }

    for field_name, value in raw_values.items():
        preferred, fallback = FIELD_SOURCE_MAP.get(field_name, ("runtime_computed", "unavailable"))
        source = overrides.get(field_name, preferred)
        if value is None and source == "estimated":
            source = "unavailable"
        fields.append(TelemetryField(name=field_name, value=value, source=source))

    return {
        "schema_version": SESSION_TELEMETRY_SCHEMA_VERSION,
        "fields": [f.to_dict() for f in fields],
    }


def build_fake_provider_telemetry() -> dict[str, Any]:
    """First-version fake-provider telemetry field source mapping.

    provider_reported: model_provider, current_turn_tokens, context_window, cache_hit
    runtime_computed: retrieval_hit_count, average_hit_rate, session_tokens,
                      request_count, active_session_state
    estimated: current/session/total_cost, balance
    unavailable: none in first version
    stale: none in first version
    """
    return build_telemetry(
        model_provider="fake-private-new-api",
        retrieval_hit_count=3,
        average_hit_rate=0.42,
        current_turn_tokens=150,
        session_tokens=1250,
        context_window=128000,
        context_usage_percent=1.0,
        context_remaining=126750,
        compression_threshold=100000,
        current_turn_cost=0.001,
        session_cost=0.012,
        total_cost=0.012,
        balance=50.00,
        active_session_state="active",
        request_count=5,
        provider_usage={
            "cache_read_input_tokens": 80,
            "prompt_tokens": 150,
            "completion_tokens": 50,
        },
        sources={
            "model_provider": "provider_reported",
            "current_turn_tokens": "provider_reported",
            "context_window": "provider_reported",
            "current_turn_cost": "estimated",
            "session_cost": "estimated",
            "total_cost": "estimated",
            "balance": "estimated",
            "provider_usage": "provider_reported",
        },
    )
