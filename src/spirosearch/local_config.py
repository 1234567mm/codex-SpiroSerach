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

VALIDATION_STATES = ("missing", "configured", "validation_failed", "validated")
ALLOWED_PROVIDER_CONFIG_FIELDS = ("enabled", "base_url", "default_model", "workspace_id")
SECRET_CONFIG_FIELD_TOKENS = ("api_key", "secret", "token", "password", "credential")


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
        lines = [f"{provider}={value}" for provider, value in secrets.items()]
        self.path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def get_secret(self, provider: str) -> str | None:
        return self._read_all().get(provider)

    def set_secret(self, provider: str, value: str) -> None:
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

    def remove_api_key(self, provider: str) -> None:
        self.secret_store.remove_secret(provider)

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
