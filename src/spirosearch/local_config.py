"""Local-only configuration and secret store for the V33 configurable platform.

Stores user provider settings and API keys in local ignored files
(``.spirosearch/local-config.json`` and ``.spirosearch/secrets.env``).
Establishes a clean ``SecretStore`` interface seam so the file-backed
implementation can later be swapped for Windows Credential Manager / OS keyring
without changing command-plane callers.

No raw secrets are ever written to run artifacts, logs, frontend payloads, or
provider capability payloads. Only key fingerprints (sha256[:16]) appear in
sanitized output.
"""
from __future__ import annotations

import hashlib
import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from spirosearch.model_provider_registry import missing_provider_config_fields

CONFIG_SCHEMA_VERSION = "v33.local_config.v1"
SANITIZED_CONFIG_STATUS_SCHEMA_VERSION = "v33.sanitized_config_status.v1"
SANITIZED_SOURCE_CONFIG_STATUS_SCHEMA_VERSION = "v35.sanitized_source_config_status.v1"

VALIDATION_STATES = ("missing", "configured", "validation_failed", "validated")
ALLOWED_PROVIDER_CONFIG_FIELDS = ("enabled", "base_url", "default_model", "workspace_id")
SECRET_CONFIG_FIELD_TOKENS = ("api_key", "secret", "token", "password", "credential")
SECRET_STORE_FORBIDDEN_PROVIDER_CHARS = ("\r", "\n", "\0", "=")
SECRET_STORE_FORBIDDEN_VALUE_CHARS = ("\r", "\n", "\0")


def key_fingerprint(key: str) -> str:
    """Return the first 16 hex chars of SHA-256 of the key.

    This is safe to display in sanitized status — it cannot be reversed
    to recover the original key.
    """
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def secret_config_fields(config: Mapping[str, Any]) -> list[str]:
    """Return config keys that look like inline secrets."""
    return sorted(
        str(key)
        for key in config
        if any(token in str(key).casefold() for token in SECRET_CONFIG_FIELD_TOKENS)
    )


def unsupported_provider_config_fields(config: Mapping[str, Any]) -> list[str]:
    """Return config keys outside the current local config contract."""
    allowed = set(ALLOWED_PROVIDER_CONFIG_FIELDS)
    return sorted(str(key) for key in config if str(key) not in allowed)


def validate_provider_config_fields(config: Mapping[str, Any]) -> None:
    """Validate that local provider config cannot carry secrets or unknown keys."""
    secret_fields = secret_config_fields(config)
    if secret_fields:
        joined = ", ".join(secret_fields)
        raise ValueError(f"secret fields must use SecretStore: {joined}")
    unsupported_fields = unsupported_provider_config_fields(config)
    if unsupported_fields:
        joined = ", ".join(unsupported_fields)
        raise ValueError(f"unsupported provider config fields: {joined}")


def validate_secret_store_entry(provider: str, value: str) -> None:
    """Validate one env-file secret entry before it can be persisted."""
    if not provider.strip():
        raise ValueError("secret provider is required")
    if any(char in provider for char in SECRET_STORE_FORBIDDEN_PROVIDER_CHARS):
        raise ValueError("secret provider cannot contain env-file control characters")
    if any(char in value for char in SECRET_STORE_FORBIDDEN_VALUE_CHARS):
        raise ValueError("secret value cannot contain newline or NUL characters")


class SecretStore(ABC):
    """Abstract interface for secret storage, swappable to OS keyring later."""

    @abstractmethod
    def get_secret(self, provider: str) -> str | None: ...

    @abstractmethod
    def set_secret(self, provider: str, value: str) -> None: ...

    @abstractmethod
    def remove_secret(self, provider: str) -> None: ...


class FileSecretStore(SecretStore):
    """File-backed secret store using a simple ``PROVIDER=key`` env-file format.

    The file is NOT JSON so that secret values are never accidentally
    serialized into config snapshots or logs. It is ignored by ``.gitignore``.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._ensure()

    def _ensure(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def _read_all(self) -> dict[str, str]:
        result: dict[str, str] = {}
        if not self.path.exists():
            return result
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            provider, _, value = line.partition("=")
            result[provider.strip()] = value.strip()
        return result

    def _write_all(self, secrets: Mapping[str, str]) -> None:
        for provider, value in secrets.items():
            validate_secret_store_entry(str(provider), str(value))
        lines = [f"{provider}={value}" for provider, value in secrets.items()]
        self.path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def get_secret(self, provider: str) -> str | None:
        return self._read_all().get(provider)

    def set_secret(self, provider: str, value: str) -> None:
        validate_secret_store_entry(provider, value)
        secrets = self._read_all()
        secrets[provider] = value
        self._write_all(secrets)

    def remove_secret(self, provider: str) -> None:
        secrets = self._read_all()
        secrets.pop(provider, None)
        self._write_all(secrets)


@dataclass
class LocalConfigStore:
    """Local config storage with secret isolation and versioning.

    Config (enabled state, base URLs, model choices, workspace IDs) lives in
    a JSON file. Secrets (API keys) live in a separate env-style file via the
    ``SecretStore`` interface. The two files are never mixed.
    """

    config_path: str | Path
    secret_store: SecretStore
    _config_version: int = field(default=0, repr=False)

    def __post_init__(self) -> None:
        self.config_path = Path(self.config_path)
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._load()
        if not self.config_path.exists():
            self._save()

    # -- internal config file I/O --

    def _load(self) -> None:
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                data = {}
        else:
            data = {}
        self._config_version = int(data.get("config_version", 0))
        providers: dict[str, dict[str, Any]] = {}
        for provider, config in dict(data.get("providers", {})).items():
            if not isinstance(config, Mapping):
                raise ValueError(f"provider config must be an object: {provider}")
            validate_provider_config_fields(config)
            providers[str(provider)] = dict(config)
        self._providers = providers

    def _save(self) -> None:
        payload = {
            "schema_version": CONFIG_SCHEMA_VERSION,
            "config_version": self._config_version,
            "providers": self._providers,
        }
        self.config_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    # -- public config API --

    @property
    def config_version(self) -> int:
        return self._config_version

    def get_provider_config(self, provider: str) -> dict[str, Any]:
        return dict(self._providers.get(provider, {}))

    def set_provider_config(self, provider: str, config: Mapping[str, Any]) -> None:
        validate_provider_config_fields(config)
        self._config_version += 1
        self._providers[provider] = dict(config)
        self._save()

    # -- secret delegation --

    def get_api_key(self, provider: str) -> str | None:
        return self.secret_store.get_secret(provider)

    def set_api_key(self, provider: str, value: str) -> None:
        self.secret_store.set_secret(provider, value)
        self._config_version += 1
        self._save()

    def remove_api_key(self, provider: str) -> None:
        self.secret_store.remove_secret(provider)
        self._config_version += 1
        self._save()

    def key_fingerprint(self, provider: str) -> str | None:
        key = self.get_api_key(provider)
        if not key:
            return None
        return key_fingerprint(key)


def build_sanitized_config_status(
    store: LocalConfigStore,
    registry: Any,
    *,
    producer_version: str = "v33",
) -> dict[str, Any]:
    """Emit frontend-facing sanitized config status.

    For each provider in the model provider registry, reports:
    - ``validation_state``: one of ``missing`` / ``configured`` /
      ``validation_failed`` / ``validated``.
    - ``key_fingerprint``: sha256[:16] of the API key, or ``None``.
    - ``has_api_key``: boolean (without revealing the value).
    - Provider config fields (enabled, base_url, model, workspace_id).

    Never includes raw secret values.
    """
    providers_status: list[dict[str, Any]] = []
    for entry in registry.ordered_providers():
        cfg = store.get_provider_config(entry.provider)
        has_key = bool(store.get_api_key(entry.provider))
        fp = store.key_fingerprint(entry.provider)

        missing = missing_provider_config_fields(
            entry,
            cfg,
            has_api_key=has_key,
            require_enabled=False,
        )
        if missing:
            validation_state = "missing"
        else:
            validation_state = "configured"

        providers_status.append({
            "provider": entry.provider,
            "brand": entry.brand,
            "priority": entry.priority,
            "provider_kind": entry.provider_kind,
            "requires_api_key": entry.requires_api_key,
            "has_api_key": has_key,
            "key_fingerprint": fp,
            "validation_state": validation_state,
            "enabled": cfg.get("enabled", False),
            "base_url": cfg.get("base_url"),
            "default_model": cfg.get("default_model"),
            "workspace_id": cfg.get("workspace_id"),
        })

    return {
        "schema_version": SANITIZED_CONFIG_STATUS_SCHEMA_VERSION,
        "producer_version": producer_version,
        "config_version": store.config_version,
        "providers": providers_status,
    }


def build_sanitized_source_config_status(
    store: LocalConfigStore,
    source_registry: Any,
    *,
    producer_version: str = "v35",
) -> dict[str, Any]:
    """Emit frontend-facing source-provider config status without secrets."""
    sources_status: list[dict[str, Any]] = []
    for provider_id in source_registry.providers():
        entry = source_registry.get(provider_id)
        api_key = _source_api_key(store, entry)
        has_key = bool(api_key)
        if entry.requires_api_key and not has_key:
            validation_state = "missing"
        else:
            validation_state = "configured"
        sources_status.append(
            {
                "provider_id": entry.provider,
                "provider_scope": "source",
                "provider_kind": _source_provider_kind(entry),
                "status": entry.operational_status,
                "v35_slice": entry.v35_slice,
                "acquisition_mode": entry.acquisition_mode,
                "distribution_policy": entry.distribution_policy,
                "requires_api_key": entry.requires_api_key,
                "key_requirement": "required" if entry.requires_api_key else "none",
                "api_key_env": entry.api_key_env,
                "has_api_key": has_key,
                "key_fingerprint": key_fingerprint(api_key) if api_key else None,
                "validation_state": validation_state,
                "data_library_path": entry.data_library_path,
                "execution_modes": list(entry.execution_modes),
                "capabilities": list(entry.capabilities),
            }
        )
    return {
        "schema_version": SANITIZED_SOURCE_CONFIG_STATUS_SCHEMA_VERSION,
        "producer_version": producer_version,
        "config_version": store.config_version,
        "sources": sources_status,
    }


def _source_api_key(store: LocalConfigStore, entry: Any) -> str | None:
    key = store.get_api_key(entry.provider)
    if key:
        return key
    if entry.requires_api_key and entry.api_key_env:
        return os.environ.get(str(entry.api_key_env))
    return None


def _source_provider_kind(entry: Any) -> str:
    if entry.v35_slice == "p0_schema_module" or entry.acquisition_mode == "schema_fixture":
        return "schema_module"
    if entry.acquisition_mode == "manual_archive_import":
        return "archive_import"
    if entry.local_dataset:
        return "local_dataset"
    return "provider_api"
