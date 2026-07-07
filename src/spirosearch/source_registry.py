from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from spirosearch.contracts import TRUST_LEVELS


BACKOFF_STRATEGIES = {"none", "fixed", "exponential"}


@dataclass(frozen=True)
class SourceRegistryEntry:
    provider: str
    base_url: str
    license_hint: str
    trust_level: str
    rate_limit: dict[str, Any]
    requires_api_key: bool
    cache_ttl_hours: int
    allowed_output_fields: tuple[str, ...]
    disambiguation_required: bool
    api_key_env: str | None = None

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider is required")
        if not self.base_url.strip():
            raise ValueError(f"base_url is required for {self.provider}")
        if self.trust_level not in TRUST_LEVELS:
            raise ValueError(f"unknown trust_level for {self.provider}: {self.trust_level}")
        if self.cache_ttl_hours <= 0:
            raise ValueError(f"cache_ttl_hours must be positive for {self.provider}")
        if not self.allowed_output_fields:
            raise ValueError(f"allowed_output_fields is required for {self.provider}")
        requests_per_second = self.rate_limit.get("requests_per_second")
        if not isinstance(requests_per_second, int | float) or requests_per_second <= 0:
            raise ValueError(f"rate_limit.requests_per_second must be positive for {self.provider}")
        if self.rate_limit.get("backoff_strategy") not in BACKOFF_STRATEGIES:
            raise ValueError(f"unknown backoff_strategy for {self.provider}")
        if self.requires_api_key and not (self.api_key_env or "").strip():
            raise ValueError(f"api_key_env is required for API-key provider {self.provider}")

        object.__setattr__(self, "rate_limit", dict(self.rate_limit))
        object.__setattr__(self, "allowed_output_fields", tuple(self.allowed_output_fields))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SourceRegistryEntry":
        return cls(
            provider=str(data["provider"]),
            base_url=str(data["base_url"]),
            license_hint=str(data["license_hint"]),
            trust_level=str(data["trust_level"]),
            rate_limit=dict(data["rate_limit"]),
            requires_api_key=bool(data["requires_api_key"]),
            cache_ttl_hours=int(data["cache_ttl_hours"]),
            allowed_output_fields=tuple(str(item) for item in data["allowed_output_fields"]),
            disambiguation_required=bool(data["disambiguation_required"]),
            api_key_env=str(data["api_key_env"]) if data.get("api_key_env") else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "license_hint": self.license_hint,
            "trust_level": self.trust_level,
            "rate_limit": dict(self.rate_limit),
            "requires_api_key": self.requires_api_key,
            "cache_ttl_hours": self.cache_ttl_hours,
            "allowed_output_fields": list(self.allowed_output_fields),
            "disambiguation_required": self.disambiguation_required,
            "api_key_env": self.api_key_env,
        }

    def validate_output_fields(self, normalized_result: Mapping[str, Any]) -> None:
        allowed = set(self.allowed_output_fields)
        extra = sorted(set(normalized_result) - allowed)
        if extra:
            raise ValueError(f"{self.provider} output fields are not allowed: {', '.join(extra)}")


class SourceRateLimiter:
    def __init__(
        self,
        entry: SourceRegistryEntry,
        *,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ):
        self.entry = entry
        self.clock = clock or time.monotonic
        self.sleeper = sleeper or time.sleep
        self._last_call_at: float | None = None

    def wait_for_slot(self) -> None:
        requests_per_second = float(self.entry.rate_limit["requests_per_second"])
        interval_seconds = 1.0 / requests_per_second
        now = self.clock()
        if self._last_call_at is not None:
            elapsed = now - self._last_call_at
            remaining = interval_seconds - elapsed
            if remaining > 0:
                self.sleeper(remaining)
                now = self.clock()
        self._last_call_at = now

    def wait_for_retry(self, attempt: int) -> None:
        strategy = str(self.entry.rate_limit["backoff_strategy"])
        if strategy == "none":
            return
        interval_seconds = 1.0 / float(self.entry.rate_limit["requests_per_second"])
        if strategy == "fixed":
            self.sleeper(interval_seconds)
            return
        if strategy == "exponential":
            self.sleeper(interval_seconds * (2 ** max(0, attempt - 1)))
            return
        raise ValueError(f"unknown backoff_strategy for {self.entry.provider}: {strategy}")


class SourceRegistry:
    def __init__(self, entries: Iterable[SourceRegistryEntry]):
        self._entries = {entry.provider: entry for entry in entries}
        if not self._entries:
            raise ValueError("source registry must contain at least one provider")
        self._rate_limiters: dict[str, SourceRateLimiter] = {}

    def get(self, provider: str) -> SourceRegistryEntry:
        try:
            return self._entries[provider]
        except KeyError as exc:
            raise KeyError(f"unknown provider: {provider}") from exc

    def providers(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def rate_limiter(
        self,
        provider: str,
        *,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> SourceRateLimiter:
        if provider not in self._rate_limiters:
            self._rate_limiters[provider] = SourceRateLimiter(
                self.get(provider),
                clock=clock,
                sleeper=sleeper,
            )
        return self._rate_limiters[provider]

    def to_dict(self) -> list[dict[str, Any]]:
        return [self._entries[name].to_dict() for name in self.providers()]


def load_source_registry(path_or_records: str | Path | Iterable[Mapping[str, Any]]) -> SourceRegistry:
    if isinstance(path_or_records, str | Path):
        records = json.loads(Path(path_or_records).read_text(encoding="utf-8"))
    else:
        records = list(path_or_records)
    if not isinstance(records, list):
        raise ValueError("source registry must be a JSON array")
    return SourceRegistry(SourceRegistryEntry.from_dict(record) for record in records)


class ApiKeyManager:
    def __init__(self, registry: SourceRegistry):
        self.registry = registry

    def optional_key(self, provider: str) -> str | None:
        entry = self.registry.get(provider)
        if not entry.requires_api_key:
            return None
        return os.environ.get(str(entry.api_key_env))

    def require_key(self, provider: str) -> str:
        entry = self.registry.get(provider)
        if not entry.requires_api_key:
            return ""
        key = os.environ.get(str(entry.api_key_env))
        if not key:
            raise RuntimeError(
                f"Provider '{provider}' requires API key environment variable {entry.api_key_env}"
            )
        return key
