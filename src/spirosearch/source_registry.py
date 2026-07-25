from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from spirosearch.contracts import TRUST_LEVELS


SOURCE_PROFILE_SCHEMA_VERSION = "v35.data_source_profile.v1"
BACKOFF_STRATEGIES = {"none", "fixed", "exponential"}
OPERATIONAL_STATUSES = {"active", "experimental", "quarantined", "disabled"}
EXECUTION_MODES = {"direct", "enrichment", "local_dataset"}
SOURCE_FAMILIES = {
    "archive_metadata",
    "computed_materials",
    "computed_molecule",
    "general",
    "literature_metadata",
    "molecule_identity",
    "opv_benchmark",
    "project_generated",
    "psc_device_performance",
    "schema_reference",
}
LICENSE_SCOPES = {
    "api_terms_record",
    "dataset_snapshot",
    "project_generated",
    "record_specific",
    "schema_software_only",
    "source_record",
}
CURATION_STATUSES = {
    "calculated",
    "curated_reference",
    "machine_extracted",
    "machine_normalized",
    "schema_reference",
    "user_import_required",
}
GO_MIGRATION_STATES = {
    "deferred",
    "go_owned",
    "go_shadow_ready",
    "out_of_current_slice",
    "parity_required",
    "python_bridge_retained",
    "python_oracle_p0",
}
TYPESCRIPT_SURFACES = {
    "read_only_reference",
    "settings_and_import_commands",
    "source_coverage_and_settings_only",
    "source_coverage_settings_and_commands",
}
V35_SLICES = {
    "p0_live_provider",
    "p0_local_snapshot",
    "p0_manual_import",
    "p0_schema_module",
    "deferred",
    "out_of_current_slice",
}
ACQUISITION_MODES = {
    "api_lookup",
    "api_sync",
    "local_snapshot",
    "manual_archive_import",
    "manual_import",
    "schema_fixture",
    "disabled",
    "deferred",
    "local_dataset",
}
SOURCE_DISTRIBUTION_POLICIES = {
    "derived_facts_with_source_pointers",
    "local_only_pending_attribution",
    "schema_only",
    "api_terms_required",
    "project_generated",
}
V35_REQUIRED_PROFILE_FIELDS = {
    "schema_version",
    "provider",
    "display_name",
    "source_family",
    "base_url",
    "license_hint",
    "license_scope",
    "trust_level",
    "default_curation_status",
    "rate_limit",
    "requires_api_key",
    "cache_ttl_hours",
    "allowed_output_fields",
    "review_triggers",
    "go_migration_state",
    "python_bridge_required",
    "typescript_surface",
    "disambiguation_required",
    "operational_status",
    "capabilities",
    "execution_modes",
    "data_library_path",
    "v35_slice",
    "acquisition_mode",
    "distribution_policy",
}


@dataclass(frozen=True)
class SourceRegistryEntry:
    schema_version: str
    provider: str
    display_name: str
    source_family: str
    base_url: str
    license_hint: str
    license_scope: str
    trust_level: str
    default_curation_status: str
    rate_limit: dict[str, Any]
    requires_api_key: bool
    cache_ttl_hours: int
    allowed_output_fields: tuple[str, ...]
    review_triggers: tuple[str, ...]
    go_migration_state: str
    python_bridge_required: bool
    typescript_surface: str
    disambiguation_required: bool
    api_key_env: str | None = None
    operational_status: str = "experimental"
    capabilities: tuple[str, ...] = ()
    execution_modes: tuple[str, ...] = ()
    last_verified_at: str | None = None
    data_library_path: str | None = None
    v35_slice: str = "deferred"
    acquisition_mode: str = "deferred"
    distribution_policy: str = "derived_facts_with_source_pointers"
    probe_notes: str | None = None

    def __post_init__(self) -> None:
        if self.schema_version != SOURCE_PROFILE_SCHEMA_VERSION:
            raise ValueError(
                f"unknown schema_version for {self.provider}: {self.schema_version}"
            )
        if not self.provider.strip():
            raise ValueError("provider is required")
        if not self.display_name.strip():
            raise ValueError(f"display_name is required for {self.provider}")
        if not self.source_family.strip():
            raise ValueError(f"source_family is required for {self.provider}")
        if self.source_family not in SOURCE_FAMILIES:
            raise ValueError(f"unknown source_family for {self.provider}: {self.source_family}")
        if not self.base_url.strip():
            raise ValueError(f"base_url is required for {self.provider}")
        if not self.license_scope.strip():
            raise ValueError(f"license_scope is required for {self.provider}")
        if self.license_scope not in LICENSE_SCOPES:
            raise ValueError(f"unknown license_scope for {self.provider}: {self.license_scope}")
        if not self.default_curation_status.strip():
            raise ValueError(f"default_curation_status is required for {self.provider}")
        if self.default_curation_status not in CURATION_STATUSES:
            raise ValueError(
                "unknown default_curation_status for "
                f"{self.provider}: {self.default_curation_status}"
            )
        if not self.go_migration_state.strip():
            raise ValueError(f"go_migration_state is required for {self.provider}")
        if self.go_migration_state not in GO_MIGRATION_STATES:
            raise ValueError(
                f"unknown go_migration_state for {self.provider}: {self.go_migration_state}"
            )
        if not self.typescript_surface.strip():
            raise ValueError(f"typescript_surface is required for {self.provider}")
        if self.typescript_surface not in TYPESCRIPT_SURFACES:
            raise ValueError(
                f"unknown typescript_surface for {self.provider}: {self.typescript_surface}"
            )
        if self.trust_level not in TRUST_LEVELS:
            raise ValueError(f"unknown trust_level for {self.provider}: {self.trust_level}")
        if self.cache_ttl_hours <= 0:
            raise ValueError(f"cache_ttl_hours must be positive for {self.provider}")
        if not self.allowed_output_fields:
            raise ValueError(f"allowed_output_fields is required for {self.provider}")
        if any(not str(field).strip() for field in self.allowed_output_fields):
            raise ValueError(f"allowed_output_fields contains blank item for {self.provider}")
        if not self.review_triggers:
            raise ValueError(f"review_triggers is required for {self.provider}")
        if any(not str(trigger).strip() for trigger in self.review_triggers):
            raise ValueError(f"review_triggers contains blank item for {self.provider}")
        if len(set(self.review_triggers)) != len(self.review_triggers):
            raise ValueError(f"review_triggers contains duplicate item for {self.provider}")
        requests_per_second = self.rate_limit.get("requests_per_second")
        if not isinstance(requests_per_second, int | float) or requests_per_second <= 0:
            raise ValueError(f"rate_limit.requests_per_second must be positive for {self.provider}")
        if self.rate_limit.get("backoff_strategy") not in BACKOFF_STRATEGIES:
            raise ValueError(f"unknown backoff_strategy for {self.provider}")
        if self.requires_api_key and not (self.api_key_env or "").strip():
            raise ValueError(f"api_key_env is required for API-key provider {self.provider}")
        if self.operational_status not in OPERATIONAL_STATUSES:
            raise ValueError(
                f"unknown operational_status for {self.provider}: {self.operational_status}"
            )
        if not self.capabilities:
            raise ValueError(f"at least one capability is required for {self.provider}")
        for mode in self.execution_modes:
            if mode not in EXECUTION_MODES:
                raise ValueError(f"unknown execution_mode for {self.provider}: {mode}")
        if not self.execution_modes:
            raise ValueError(f"at least one execution_mode is required for {self.provider}")
        if self.v35_slice not in V35_SLICES:
            raise ValueError(f"unknown v35_slice for {self.provider}: {self.v35_slice}")
        if self.acquisition_mode not in ACQUISITION_MODES:
            raise ValueError(
                f"unknown acquisition_mode for {self.provider}: {self.acquisition_mode}"
            )
        if self.distribution_policy not in SOURCE_DISTRIBUTION_POLICIES:
            raise ValueError(
                f"unknown distribution_policy for {self.provider}: {self.distribution_policy}"
            )
        if self.v35_slice.startswith("p0_") and not self.data_library_path:
            raise ValueError(f"data_library_path is required for P0 provider {self.provider}")
        if self.data_library_path is not None:
            _validate_data_library_path(self.provider, self.data_library_path)

        object.__setattr__(self, "rate_limit", dict(self.rate_limit))
        object.__setattr__(self, "allowed_output_fields", tuple(self.allowed_output_fields))
        object.__setattr__(self, "review_triggers", tuple(self.review_triggers))
        object.__setattr__(self, "capabilities", tuple(self.capabilities))
        object.__setattr__(self, "execution_modes", tuple(self.execution_modes))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SourceRegistryEntry":
        missing = sorted(field for field in V35_REQUIRED_PROFILE_FIELDS if field not in data)
        if missing:
            provider = str(data.get("provider", "<unknown>"))
            raise ValueError(
                f"source profile for {provider} is missing required fields: {', '.join(missing)}"
            )
        return cls(
            schema_version=str(data["schema_version"]),
            provider=str(data["provider"]),
            display_name=str(data["display_name"]),
            source_family=str(data["source_family"]),
            base_url=str(data["base_url"]),
            license_hint=str(data["license_hint"]),
            license_scope=str(data["license_scope"]),
            trust_level=str(data["trust_level"]),
            default_curation_status=str(data["default_curation_status"]),
            rate_limit=dict(data["rate_limit"]),
            requires_api_key=bool(data["requires_api_key"]),
            cache_ttl_hours=int(data["cache_ttl_hours"]),
            allowed_output_fields=tuple(str(item) for item in data["allowed_output_fields"]),
            review_triggers=tuple(str(item) for item in data["review_triggers"]),
            go_migration_state=str(data["go_migration_state"]),
            python_bridge_required=bool(data["python_bridge_required"]),
            typescript_surface=str(data["typescript_surface"]),
            disambiguation_required=bool(data["disambiguation_required"]),
            api_key_env=str(data["api_key_env"]) if data.get("api_key_env") else None,
            operational_status=str(data["operational_status"]),
            capabilities=tuple(str(item) for item in data["capabilities"]),
            execution_modes=tuple(str(item) for item in data["execution_modes"]),
            last_verified_at=str(data["last_verified_at"]) if data.get("last_verified_at") else None,
            data_library_path=(
                str(data["data_library_path"]) if data.get("data_library_path") else None
            ),
            v35_slice=str(data["v35_slice"]),
            acquisition_mode=str(data["acquisition_mode"]),
            distribution_policy=str(data["distribution_policy"]),
            probe_notes=str(data["probe_notes"]) if data.get("probe_notes") else None,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "provider": self.provider,
            "display_name": self.display_name,
            "source_family": self.source_family,
            "base_url": self.base_url,
            "license_hint": self.license_hint,
            "license_scope": self.license_scope,
            "trust_level": self.trust_level,
            "default_curation_status": self.default_curation_status,
            "rate_limit": dict(self.rate_limit),
            "requires_api_key": self.requires_api_key,
            "cache_ttl_hours": self.cache_ttl_hours,
            "allowed_output_fields": list(self.allowed_output_fields),
            "review_triggers": list(self.review_triggers),
            "go_migration_state": self.go_migration_state,
            "python_bridge_required": self.python_bridge_required,
            "typescript_surface": self.typescript_surface,
            "disambiguation_required": self.disambiguation_required,
            "api_key_env": self.api_key_env,
            "operational_status": self.operational_status,
            "capabilities": list(self.capabilities),
            "execution_modes": list(self.execution_modes),
            "last_verified_at": self.last_verified_at,
            "data_library_path": self.data_library_path,
            "v35_slice": self.v35_slice,
            "acquisition_mode": self.acquisition_mode,
            "distribution_policy": self.distribution_policy,
            "probe_notes": self.probe_notes,
        }

    @property
    def live_enabled(self) -> bool:
        return (
            self.operational_status == "active"
            and "enrichment" in self.execution_modes
        )

    @property
    def local_dataset(self) -> bool:
        return (
            "local_dataset" in self.execution_modes
            or self.acquisition_mode
            in {"local_snapshot", "manual_archive_import", "schema_fixture"}
        )

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
        self._entries: dict[str, SourceRegistryEntry] = {}
        for entry in entries:
            if entry.provider in self._entries:
                raise ValueError(f"duplicate provider: {entry.provider}")
            self._entries[entry.provider] = entry
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


def _validate_data_library_path(provider: str, value: str) -> None:
    path = value.strip()
    if path != value or not path:
        raise ValueError(f"unsafe data_library_path for {provider}: {value}")
    if path.startswith(("file://", "/", "\\")):
        raise ValueError(f"unsafe data_library_path for {provider}: {value}")
    if "\\" in path or ":" in path:
        raise ValueError(f"unsafe data_library_path for {provider}: {value}")
    parts = path.split("/")
    if len(parts) < 3 or parts[0] != "data" or parts[1] != "lib":
        raise ValueError(f"data_library_path must be under data/lib for {provider}: {value}")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"unsafe data_library_path for {provider}: {value}")


class ApiKeyManager:
    def __init__(self, registry: SourceRegistry, config_store: Any | None = None):
        self.registry = registry
        self.config_store = config_store

    def optional_key(self, provider: str) -> str | None:
        entry = self.registry.get(provider)
        if not entry.requires_api_key:
            return None
        if self.config_store is not None:
            key = self.config_store.get_api_key(provider)
            if key:
                return key
        return os.environ.get(str(entry.api_key_env))

    def require_key(self, provider: str) -> str:
        entry = self.registry.get(provider)
        if not entry.requires_api_key:
            return ""
        key = self.optional_key(provider)
        if not key:
            raise RuntimeError(
                f"Provider '{provider}' requires API key in local config or environment variable {entry.api_key_env}"
            )
        return key
