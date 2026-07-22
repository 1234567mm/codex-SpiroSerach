"""Model provider registry for the V33 configurable perovskite agent platform.

Separates model-execution infrastructure metadata from scientific data-source
trust. Providers are execution infrastructure, not scientific evidence sources.
No ranking or screening decision is introduced here.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

MODEL_PROVIDER_REGISTRY_SCHEMA_VERSION = "v33.model_provider_registry.v1"
SANITIZED_PROVIDER_STATUS_SCHEMA_VERSION = "v33.sanitized_provider_status.v1"

PROVIDER_KINDS = {"private_relay", "model_provider"}
API_FORMATS = {"openai_compatible"}


@dataclass(frozen=True)
class ModelProviderEntry:
    """Static metadata for a model provider (no user-specific values)."""

    provider: str
    priority: int
    provider_kind: str
    api_format: str
    requires_api_key: bool
    brand: str | None = None
    base_url: str | None = None
    base_url_config_key: str | None = None
    base_url_template: str | None = None
    api_key_env: str | None = None
    default_model: str | None = None
    default_models: tuple[str, ...] = ()
    default_model_config_key: str | None = None
    supports: tuple[str, ...] = ()
    docs_url: str | None = None
    requires_workspace_id: bool = False
    supports_cache: bool = False
    context_window_tokens: int | None = None
    usage_field_mapping: Mapping[str, str] = field(default_factory=dict)  # type: ignore[arg-type]
    price_input_per_1m_tokens: float | None = None
    price_output_per_1m_tokens: float | None = None
    price_cache_read_per_1m_tokens: float | None = None

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider is required")
        if self.priority < 0:
            raise ValueError(f"priority must be non-negative for {self.provider}")
        if self.provider_kind not in PROVIDER_KINDS:
            raise ValueError(
                f"unknown provider_kind for {self.provider}: {self.provider_kind}"
            )
        if self.api_format not in API_FORMATS:
            raise ValueError(
                f"unknown api_format for {self.provider}: {self.api_format}"
            )
        if self.requires_api_key and not (self.api_key_env or "").strip():
            raise ValueError(
                f"api_key_env is required for API-key provider {self.provider}"
            )
        # Mutables → immutable
        object.__setattr__(self, "default_models", tuple(self.default_models))
        object.__setattr__(self, "supports", tuple(self.supports))
        object.__setattr__(self, "usage_field_mapping", dict(self.usage_field_mapping))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "ModelProviderEntry":
        if not data.get("provider"):
            raise ValueError("provider is required")
        if "priority" not in data:
            raise ValueError("priority is required")
        if "provider_kind" not in data:
            raise ValueError("provider_kind is required")
        if "api_format" not in data:
            raise ValueError("api_format is required")
        return cls(
            provider=str(data["provider"]),
            priority=int(data["priority"]),
            provider_kind=str(data["provider_kind"]),
            api_format=str(data["api_format"]),
            requires_api_key=bool(data.get("requires_api_key", True)),
            brand=str(data["brand"]) if data.get("brand") else None,
            base_url=str(data["base_url"]) if data.get("base_url") else None,
            base_url_config_key=str(data["base_url_config_key"]) if data.get("base_url_config_key") else None,
            base_url_template=str(data["base_url_template"]) if data.get("base_url_template") else None,
            api_key_env=str(data["api_key_env"]) if data.get("api_key_env") else None,
            default_model=str(data["default_model"]) if data.get("default_model") is not None else None,
            default_models=tuple(str(m) for m in data.get("default_models", ())),
            default_model_config_key=str(data["default_model_config_key"]) if data.get("default_model_config_key") else None,
            supports=tuple(str(s) for s in data.get("supports", ())),
            docs_url=str(data["docs_url"]) if data.get("docs_url") else None,
            requires_workspace_id=bool(data.get("requires_workspace_id", False)),
            supports_cache=bool(data.get("supports_cache", False)),
            context_window_tokens=int(data["context_window_tokens"]) if data.get("context_window_tokens") is not None else None,
            usage_field_mapping=dict(data.get("usage_field_mapping", {})),
            price_input_per_1m_tokens=float(data["price_input_per_1m_tokens"]) if data.get("price_input_per_1m_tokens") is not None else None,
            price_output_per_1m_tokens=float(data["price_output_per_1m_tokens"]) if data.get("price_output_per_1m_tokens") is not None else None,
            price_cache_read_per_1m_tokens=float(data["price_cache_read_per_1m_tokens"]) if data.get("price_cache_read_per_1m_tokens") is not None else None,
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "provider": self.provider,
            "priority": self.priority,
            "provider_kind": self.provider_kind,
            "api_format": self.api_format,
            "requires_api_key": self.requires_api_key,
            "base_url": self.base_url,
            "base_url_config_key": self.base_url_config_key,
            "base_url_template": self.base_url_template,
            "api_key_env": self.api_key_env,
            "default_model": self.default_model,
            "default_models": list(self.default_models),
            "default_model_config_key": self.default_model_config_key,
            "supports": list(self.supports),
            "docs_url": self.docs_url,
            "requires_workspace_id": self.requires_workspace_id,
            "supports_cache": self.supports_cache,
            "context_window_tokens": self.context_window_tokens,
            "usage_field_mapping": dict(self.usage_field_mapping),
            "price_input_per_1m_tokens": self.price_input_per_1m_tokens,
            "price_output_per_1m_tokens": self.price_output_per_1m_tokens,
            "price_cache_read_per_1m_tokens": self.price_cache_read_per_1m_tokens,
        }
        if self.brand is not None:
            result["brand"] = self.brand
        return result


class ModelProviderRegistry:
    """In-memory collection of model-provider entries, sorted by priority."""

    def __init__(self, entries: Iterable[ModelProviderEntry]):
        self._entries = {entry.provider: entry for entry in entries}
        if not self._entries:
            raise ValueError("model provider registry must contain at least one provider")

    def get(self, provider: str) -> ModelProviderEntry:
        try:
            return self._entries[provider]
        except KeyError as exc:
            raise KeyError(f"unknown model provider: {provider}") from exc

    def providers(self) -> tuple[str, ...]:
        return tuple(sorted(self._entries))

    def ordered_providers(self) -> tuple[ModelProviderEntry, ...]:
        """Return entries sorted by priority (ascending). Ties broken by provider name."""
        return tuple(
            sorted(self._entries.values(), key=lambda e: (e.priority, e.provider))
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": MODEL_PROVIDER_REGISTRY_SCHEMA_VERSION,
            "providers": [entry.to_dict() for entry in self.ordered_providers()],
        }


def missing_provider_config_fields(
    entry: ModelProviderEntry,
    provider_config: Mapping[str, Any],
    *,
    has_api_key: bool,
    require_enabled: bool = False,
) -> tuple[str, ...]:
    """Return required provider config fields missing for model execution."""
    missing: list[str] = []
    if require_enabled and not bool(provider_config.get("enabled", False)):
        missing.append("enabled")
    if entry.requires_api_key and not has_api_key:
        missing.append("api_key")
    if entry.base_url_config_key and not str(provider_config.get("base_url") or "").strip():
        missing.append("base_url")
    if entry.requires_workspace_id and not str(provider_config.get("workspace_id") or "").strip():
        missing.append("workspace_id")
    has_model = (
        bool(str(provider_config.get("default_model") or "").strip())
        or bool(entry.default_models)
        or bool(str(entry.default_model or "").strip())
    )
    if not has_model:
        missing.append("default_model")
    return tuple(missing)


def load_model_provider_registry(
    path_or_records: str | Path | Iterable[Mapping[str, Any]],
) -> ModelProviderRegistry:
    if isinstance(path_or_records, str | Path):
        payload = json.loads(Path(path_or_records).read_text(encoding="utf-8"))
    else:
        payload = {"providers": list(path_or_records)}
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict) and isinstance(payload.get("providers"), list):
        records = payload["providers"]
    else:
        raise ValueError("model provider registry must be a JSON array or {\"providers\": [...]}")
    return ModelProviderRegistry(ModelProviderEntry.from_dict(record) for record in records)


def build_sanitized_provider_status(
    registry: ModelProviderRegistry,
    *,
    producer_version: str = "v33",
) -> dict[str, Any]:
    """Emit frontend-facing sanitized provider status (no secrets).

    Exposes the api_key_env *name* (so the frontend knows which env var to
    configure), but never the key value itself. Includes pricing/context
    metadata for telemetry estimation fallback.
    """
    providers = []
    for entry in registry.ordered_providers():
        providers.append({
            "provider": entry.provider,
            "brand": entry.brand,
            "priority": entry.priority,
            "provider_kind": entry.provider_kind,
            "api_format": entry.api_format,
            "requires_api_key": entry.requires_api_key,
            "api_key_env": entry.api_key_env,
            "base_url": entry.base_url,
            "base_url_config_key": entry.base_url_config_key,
            "base_url_template": entry.base_url_template,
            "default_model": entry.default_model,
            "default_models": list(entry.default_models),
            "default_model_config_key": entry.default_model_config_key,
            "supports": list(entry.supports),
            "docs_url": entry.docs_url,
            "requires_workspace_id": entry.requires_workspace_id,
            "supports_cache": entry.supports_cache,
            "context_window_tokens": entry.context_window_tokens,
            "usage_field_mapping": dict(entry.usage_field_mapping),
            "price_input_per_1m_tokens": entry.price_input_per_1m_tokens,
            "price_output_per_1m_tokens": entry.price_output_per_1m_tokens,
            "price_cache_read_per_1m_tokens": entry.price_cache_read_per_1m_tokens,
        })
    return {
        "schema_version": SANITIZED_PROVIDER_STATUS_SCHEMA_VERSION,
        "producer_version": producer_version,
        "providers": providers,
    }
