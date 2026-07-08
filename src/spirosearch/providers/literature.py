from __future__ import annotations

import json
from typing import Any, Callable, Mapping
from urllib.parse import quote
from urllib.request import urlopen

from spirosearch.providers.base import ProviderResponse
from spirosearch.source_registry import SourceRateLimiter, SourceRegistry, SourceRegistryEntry


class CrossrefWorksProvider:
    provider_name = "crossref"

    def __init__(
        self,
        *,
        base_url: str = "https://api.crossref.org",
        transport: Callable[[str], Mapping[str, Any]] | None = None,
        retrieved_at: str,
        license_hint: str = "Crossref REST API terms",
        registry_entry: SourceRegistryEntry | None = None,
        rate_limiter: SourceRateLimiter | None = None,
        allowed_output_fields: tuple[str, ...] | None = None,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ):
        if registry_entry is not None:
            if registry_entry.provider != self.provider_name:
                raise ValueError(f"registry entry must be for {self.provider_name}")
            base_url = registry_entry.base_url
            license_hint = registry_entry.license_hint
            allowed_output_fields = registry_entry.allowed_output_fields
        self.base_url = base_url.rstrip("/")
        self.transport = transport or _urllib_json_transport
        self.retrieved_at = retrieved_at
        self.license_hint = license_hint
        self.trust_level = registry_entry.trust_level if registry_entry is not None else "T3_literature_machine"
        self.allowed_output_fields = allowed_output_fields
        self.rate_limiter = (
            rate_limiter or SourceRateLimiter(registry_entry, clock=clock, sleeper=sleeper)
            if registry_entry is not None
            else None
        )

    @classmethod
    def from_registry(
        cls,
        registry: SourceRegistry,
        *,
        transport: Callable[[str], Mapping[str, Any]] | None = None,
        retrieved_at: str,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> "CrossrefWorksProvider":
        return cls(
            transport=transport,
            retrieved_at=retrieved_at,
            registry_entry=registry.get(cls.provider_name),
            rate_limiter=registry.rate_limiter(cls.provider_name, clock=clock, sleeper=sleeper),
            clock=clock,
            sleeper=sleeper,
        )

    def search(self, query: str, *, rows: int = 5) -> ProviderResponse:
        query_value = query.strip()
        if not query_value:
            raise ValueError("query is required")
        if rows <= 0:
            raise ValueError("rows must be positive")
        if self.rate_limiter is not None:
            self.rate_limiter.wait_for_slot()
        url = f"{self.base_url}/works?query={quote(query_value, safe='')}&rows={rows}"
        payload = self._fetch_with_backoff(url)
        normalized, confidence = _normalize_crossref_work(payload)
        return ProviderResponse.from_payload(
            provider=self.provider_name,
            query=f"search:{query_value}",
            normalized_result=normalized,
            source_url=url,
            retrieved_at=self.retrieved_at,
            license_hint=self.license_hint,
            raw_payload=payload,
            confidence=confidence,
            trust_level=self.trust_level,
            allowed_output_fields=self.allowed_output_fields,
        )

    def _fetch_with_backoff(self, url: str) -> Mapping[str, Any]:
        try:
            return self.transport(url)
        except Exception:
            if self.rate_limiter is None:
                raise
            self.rate_limiter.wait_for_retry(attempt=1)
            return self.transport(url)


class OpenAlexWorksProvider:
    provider_name = "openalex"

    def __init__(
        self,
        *,
        base_url: str = "https://api.openalex.org",
        transport: Callable[[str], Mapping[str, Any]] | None = None,
        retrieved_at: str,
        license_hint: str = "OpenAlex CC0 data",
        registry_entry: SourceRegistryEntry | None = None,
        rate_limiter: SourceRateLimiter | None = None,
        allowed_output_fields: tuple[str, ...] | None = None,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ):
        if registry_entry is not None:
            if registry_entry.provider != self.provider_name:
                raise ValueError(f"registry entry must be for {self.provider_name}")
            base_url = registry_entry.base_url
            license_hint = registry_entry.license_hint
            allowed_output_fields = registry_entry.allowed_output_fields
        self.base_url = base_url.rstrip("/")
        self.transport = transport or _urllib_json_transport
        self.retrieved_at = retrieved_at
        self.license_hint = license_hint
        self.trust_level = registry_entry.trust_level if registry_entry is not None else "T3_literature_machine"
        self.allowed_output_fields = allowed_output_fields
        self.rate_limiter = (
            rate_limiter or SourceRateLimiter(registry_entry, clock=clock, sleeper=sleeper)
            if registry_entry is not None
            else None
        )

    @classmethod
    def from_registry(
        cls,
        registry: SourceRegistry,
        *,
        transport: Callable[[str], Mapping[str, Any]] | None = None,
        retrieved_at: str,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> "OpenAlexWorksProvider":
        return cls(
            transport=transport,
            retrieved_at=retrieved_at,
            registry_entry=registry.get(cls.provider_name),
            rate_limiter=registry.rate_limiter(cls.provider_name, clock=clock, sleeper=sleeper),
            clock=clock,
            sleeper=sleeper,
        )

    def search(self, query: str, *, per_page: int = 5) -> ProviderResponse:
        query_value = query.strip()
        if not query_value:
            raise ValueError("query is required")
        if per_page <= 0:
            raise ValueError("per_page must be positive")
        if self.rate_limiter is not None:
            self.rate_limiter.wait_for_slot()
        url = f"{self.base_url}/works?search={quote(query_value, safe='')}&per-page={per_page}"
        payload = self._fetch_with_backoff(url)
        normalized, confidence = _normalize_openalex_work(payload)
        return ProviderResponse.from_payload(
            provider=self.provider_name,
            query=f"search:{query_value}",
            normalized_result=normalized,
            source_url=url,
            retrieved_at=self.retrieved_at,
            license_hint=self.license_hint,
            raw_payload=payload,
            confidence=confidence,
            trust_level=self.trust_level,
            allowed_output_fields=self.allowed_output_fields,
        )

    def _fetch_with_backoff(self, url: str) -> Mapping[str, Any]:
        try:
            return self.transport(url)
        except Exception:
            if self.rate_limiter is None:
                raise
            self.rate_limiter.wait_for_retry(attempt=1)
            return self.transport(url)


def _urllib_json_transport(url: str) -> Mapping[str, Any]:
    with urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _normalize_crossref_work(payload: Mapping[str, Any]) -> tuple[dict[str, Any], float]:
    records = list(dict(payload.get("message", {})).get("items", []))
    if not records:
        return {}, 0.1

    record = dict(records[0])
    normalized: dict[str, Any] = {"retraction_flag": _is_crossref_retraction(record)}
    _put_text(normalized, "doi", _normalize_doi(record.get("DOI")))
    _put_text(normalized, "title", _first_text(record.get("title")))
    _put_text(normalized, "journal", _first_text(record.get("container-title")))
    _put_text(normalized, "published_at", _crossref_published_at(record))
    authors = _crossref_authors(record.get("author"))
    if authors:
        normalized["authors"] = authors
    _put_text(normalized, "license", _crossref_license(record.get("license")))
    return normalized, 0.7


def _normalize_openalex_work(payload: Mapping[str, Any]) -> tuple[dict[str, Any], float]:
    records = list(payload.get("results", []))
    if not records:
        return {}, 0.1

    record = dict(records[0])
    normalized: dict[str, Any] = {}
    _put_text(normalized, "openalex_id", _openalex_id(record.get("id")))
    _put_text(normalized, "doi", _normalize_doi(record.get("doi")))
    _put_text(normalized, "title", record.get("title"))
    concepts = _openalex_concepts(record.get("concepts"))
    if concepts:
        normalized["concepts"] = concepts
    open_access = record.get("open_access")
    if isinstance(open_access, Mapping):
        _put_text(normalized, "oa_status", open_access.get("oa_status"))
    if record.get("cited_by_count") is not None:
        normalized["cited_by_count"] = int(record["cited_by_count"])
    return normalized, 0.7


def _put_text(target: dict[str, Any], key: str, value: Any) -> None:
    if isinstance(value, str) and value.strip():
        target[key] = value.strip()


def _first_text(value: Any) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, list | tuple):
        for item in value:
            if isinstance(item, str) and item.strip():
                return item
    return None


def _normalize_doi(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    doi = value.strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if doi.casefold().startswith(prefix):
            doi = doi[len(prefix) :]
            break
    return doi or None


def _crossref_published_at(record: Mapping[str, Any]) -> str | None:
    for key in ("published-print", "published-online", "published"):
        published = record.get(key)
        if not isinstance(published, Mapping):
            continue
        date_parts = published.get("date-parts")
        if not isinstance(date_parts, list) or not date_parts:
            continue
        first = date_parts[0]
        if not isinstance(first, list | tuple) or not first:
            continue
        parts = [int(part) for part in first[:3]]
        if len(parts) == 1:
            return f"{parts[0]:04d}"
        if len(parts) == 2:
            return f"{parts[0]:04d}-{parts[1]:02d}"
        return f"{parts[0]:04d}-{parts[1]:02d}-{parts[2]:02d}"
    return None


def _crossref_authors(value: Any) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    authors = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        name = item.get("name")
        if isinstance(name, str) and name.strip():
            authors.append(name.strip())
            continue
        parts = [str(part).strip() for part in (item.get("given"), item.get("family")) if str(part).strip()]
        if parts:
            authors.append(" ".join(parts))
    return authors


def _crossref_license(value: Any) -> str | None:
    if not isinstance(value, list | tuple):
        return None
    for item in value:
        if isinstance(item, Mapping):
            license_url = item.get("URL") or item.get("url")
            if isinstance(license_url, str) and license_url.strip():
                return license_url
    return None


def _is_crossref_retraction(record: Mapping[str, Any]) -> bool:
    relation = record.get("relation")
    if isinstance(relation, Mapping) and "is-retracted-by" in relation:
        return True
    subtype = record.get("subtype")
    if isinstance(subtype, str) and "retraction" in subtype.casefold():
        return True
    return False


def _openalex_id(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return value.rstrip("/").rsplit("/", 1)[-1] or None


def _openalex_concepts(value: Any) -> list[str]:
    if not isinstance(value, list | tuple):
        return []
    concepts = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        display_name = item.get("display_name")
        if isinstance(display_name, str) and display_name.strip():
            concepts.append(display_name.strip())
    return concepts
