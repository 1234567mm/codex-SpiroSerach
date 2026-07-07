from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterator

from spirosearch.providers.base import ProviderResponse, stable_hash
from spirosearch.source_registry import SourceRegistryEntry


class JSONLProviderCache:
    contract_version = "provider-cache-v1"

    def __init__(self, path: Path | str):
        self.path = Path(path)

    @staticmethod
    def key_for(provider: str, query: str) -> str:
        return stable_hash({"provider": provider, "query": query})

    def put(self, response: ProviderResponse) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "contract_version": self.contract_version,
            "cache_key": self.key_for(response.provider, response.query),
            "response": response.to_dict(),
        }
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n")

    def get(
        self,
        provider: str,
        query: str,
        *,
        max_age_hours: int | None = None,
        now: str | datetime | None = None,
    ) -> ProviderResponse | None:
        cache_key = self.key_for(provider, query)
        matched: ProviderResponse | None = None
        cutoff = _cache_cutoff(max_age_hours=max_age_hours, now=now)
        for record in self._records():
            if record["cache_key"] == cache_key:
                response = ProviderResponse.from_dict(record["response"])
                if cutoff is None or _parse_retrieved_at(response.retrieved_at) >= cutoff:
                    matched = response
        return matched

    def get_for_entry(
        self,
        entry: SourceRegistryEntry,
        query: str,
        *,
        now: str | datetime | None = None,
    ) -> ProviderResponse | None:
        return self.get(
            entry.provider,
            query,
            max_age_hours=entry.cache_ttl_hours,
            now=now,
        )

    def index(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(record["cache_key"] for record in self._records()))

    def _records(self) -> Iterator[dict[str, object]]:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    yield json.loads(line)


def _cache_cutoff(*, max_age_hours: int | None, now: str | datetime | None) -> datetime | None:
    if max_age_hours is None:
        return None
    current = _parse_retrieved_at(now) if now is not None else datetime.now(UTC)
    return current - timedelta(hours=max_age_hours)


def _parse_retrieved_at(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
