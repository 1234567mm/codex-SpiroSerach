from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from spirosearch.source_registry import SourceRegistry


def build_provider_capabilities(
    registry: SourceRegistry,
    *,
    producer_version: str,
) -> dict[str, Any]:
    providers = []
    for name in registry.providers():
        entry = registry.get(name)
        provider_data = {
            "provider": entry.provider,
            "base_url": entry.base_url,
            "license_hint": entry.license_hint,
            "trust_level": entry.trust_level,
            "operational_status": entry.operational_status,
            "live_enabled": entry.live_enabled,
            "capabilities": list(entry.capabilities),
            "execution_modes": list(entry.execution_modes),
            "requires_api_key": entry.requires_api_key,
            "api_key_env": entry.api_key_env,
            "cache_ttl_hours": entry.cache_ttl_hours,
            "last_verified_at": entry.last_verified_at,
        }
        providers.append(provider_data)

    return {
        "schema_version": "v12.provider_capabilities.v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "producer_version": producer_version,
        "record_count": None,
        "providers": providers,
    }
