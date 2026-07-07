from __future__ import annotations

import json
from typing import Any, Callable, Mapping
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from spirosearch.providers.base import ProviderResponse
from spirosearch.source_registry import ApiKeyManager, SourceRateLimiter, SourceRegistry, SourceRegistryEntry


JSONTransport = Callable[[str], Mapping[str, Any]]
AuthenticatedJSONTransport = Callable[[str, Mapping[str, str]], Mapping[str, Any]]


class NOMADElectronicProvider:
    provider_name = "nomad"

    def __init__(
        self,
        *,
        base_url: str = "https://nomad-lab.eu/prod/v1/api/v1",
        transport: JSONTransport | None = None,
        retrieved_at: str,
        license_hint: str = "NOMAD public data terms",
        registry_entry: SourceRegistryEntry | None = None,
        rate_limiter: SourceRateLimiter | None = None,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ):
        if registry_entry is not None:
            if registry_entry.provider != self.provider_name:
                raise ValueError(f"registry entry must be for {self.provider_name}")
            base_url = registry_entry.base_url
            license_hint = registry_entry.license_hint
        self.base_url = base_url.rstrip("/")
        self.transport = transport or _urllib_json_transport
        self.retrieved_at = retrieved_at
        self.license_hint = license_hint
        self.trust_level = registry_entry.trust_level if registry_entry is not None else "T2_computed_db"
        self.allowed_output_fields = registry_entry.allowed_output_fields if registry_entry is not None else None
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
        transport: JSONTransport | None = None,
        retrieved_at: str,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> "NOMADElectronicProvider":
        return cls(
            transport=transport,
            retrieved_at=retrieved_at,
            registry_entry=registry.get(cls.provider_name),
            rate_limiter=registry.rate_limiter(cls.provider_name, clock=clock, sleeper=sleeper),
            clock=clock,
            sleeper=sleeper,
        )

    def lookup_formula(self, formula: str) -> ProviderResponse:
        query_value = formula.strip()
        if not query_value:
            raise ValueError("formula query is required")
        if self.rate_limiter is not None:
            self.rate_limiter.wait_for_slot()
        url = f"{self.base_url}/entries/archive/query?{urlencode({'formula': query_value})}"
        payload = self._fetch_with_backoff(url)
        normalized, confidence = _normalize_nomad_electronic(payload)
        return ProviderResponse.from_payload(
            provider=self.provider_name,
            query=f"formula:{query_value}",
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


class MaterialsProjectProvider:
    provider_name = "materials_project"

    def __init__(
        self,
        *,
        base_url: str = "https://api.materialsproject.org",
        api_key: str,
        transport: AuthenticatedJSONTransport | None = None,
        retrieved_at: str,
        license_hint: str = "Materials Project API terms",
        registry_entry: SourceRegistryEntry | None = None,
        rate_limiter: SourceRateLimiter | None = None,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ):
        if not api_key.strip():
            raise RuntimeError("Materials Project API key is required")
        if registry_entry is not None:
            if registry_entry.provider != self.provider_name:
                raise ValueError(f"registry entry must be for {self.provider_name}")
            base_url = registry_entry.base_url
            license_hint = registry_entry.license_hint
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.transport = transport or _urllib_authenticated_json_transport
        self.retrieved_at = retrieved_at
        self.license_hint = license_hint
        self.trust_level = registry_entry.trust_level if registry_entry is not None else "T2_computed_db"
        self.allowed_output_fields = registry_entry.allowed_output_fields if registry_entry is not None else None
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
        api_keys: ApiKeyManager,
        transport: AuthenticatedJSONTransport | None = None,
        retrieved_at: str,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> "MaterialsProjectProvider":
        return cls(
            api_key=api_keys.require_key(cls.provider_name),
            transport=transport,
            retrieved_at=retrieved_at,
            registry_entry=registry.get(cls.provider_name),
            rate_limiter=registry.rate_limiter(cls.provider_name, clock=clock, sleeper=sleeper),
            clock=clock,
            sleeper=sleeper,
        )

    def lookup_formula(self, formula: str) -> ProviderResponse:
        query_value = formula.strip()
        if not query_value:
            raise ValueError("formula query is required")
        if self.rate_limiter is not None:
            self.rate_limiter.wait_for_slot()
        fields = (
            "material_id,formula_pretty,band_gap,formation_energy_per_atom,"
            "energy_above_hull,density,symmetry"
        )
        url = f"{self.base_url}/materials/summary?{urlencode({'formula': query_value, 'fields': fields})}"
        headers = {"X-API-KEY": self.api_key}
        payload = self._fetch_with_backoff(url, headers)
        normalized, confidence = _normalize_materials_project_summary(payload)
        return ProviderResponse.from_payload(
            provider=self.provider_name,
            query=f"formula:{query_value}",
            normalized_result=normalized,
            source_url=url,
            retrieved_at=self.retrieved_at,
            license_hint=self.license_hint,
            raw_payload=payload,
            confidence=confidence,
            trust_level=self.trust_level,
            allowed_output_fields=self.allowed_output_fields,
        )

    def _fetch_with_backoff(self, url: str, headers: Mapping[str, str]) -> Mapping[str, Any]:
        try:
            return self.transport(url, headers)
        except Exception:
            if self.rate_limiter is None:
                raise
            self.rate_limiter.wait_for_retry(attempt=1)
            return self.transport(url, headers)


def _normalize_nomad_electronic(payload: Mapping[str, Any]) -> tuple[dict[str, Any], float]:
    record = _first_record(payload)
    normalized: dict[str, Any] = {"computed": True}
    if not record:
        return normalized, 0.2
    results = dict(record.get("results", {}))
    material = dict(results.get("material", {}))
    symmetry = dict(material.get("symmetry", {}))
    electronic = dict(dict(results.get("properties", {})).get("electronic", {}))
    band_structure = dict(electronic.get("band_structure_electronic", {}))
    band_gap = band_structure.get("band_gap")
    method = dict(results.get("method", {}))
    simulation = dict(method.get("simulation", {}))
    dft = dict(simulation.get("dft", {}))

    _put_optional(normalized, "chemical_formula", material.get("chemical_formula_hill") or material.get("chemical_formula_reduced"), str)
    _put_optional(normalized, "space_group", symmetry.get("space_group_symbol"), str)
    _put_optional(normalized, "band_gap_ev", _value_or_raw(band_gap), float)
    _put_optional(normalized, "xc_functional", dft.get("xc_functional"), str)
    confidence = 0.75 if "band_gap_ev" in normalized else 0.35
    return normalized, confidence


def _normalize_materials_project_summary(payload: Mapping[str, Any]) -> tuple[dict[str, Any], float]:
    record = _first_record(payload)
    normalized: dict[str, Any] = {"computed": True}
    if not record:
        return normalized, 0.2
    symmetry = dict(record.get("symmetry", {}))
    _put_optional(normalized, "material_id", record.get("material_id"), str)
    _put_optional(normalized, "formula", record.get("formula_pretty") or record.get("formula"), str)
    _put_optional(normalized, "band_gap_ev", record.get("band_gap"), float)
    _put_optional(normalized, "formation_energy_ev_per_atom", record.get("formation_energy_per_atom"), float)
    _put_optional(normalized, "energy_above_hull", record.get("energy_above_hull"), float)
    _put_optional(normalized, "density", record.get("density"), float)
    _put_optional(normalized, "space_group", symmetry.get("symbol"), str)
    confidence = 0.75 if "band_gap_ev" in normalized else 0.35
    return normalized, confidence


def _first_record(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = payload.get("data", [])
    if isinstance(data, list) and data:
        return dict(data[0])
    return {}


def _value_or_raw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return value.get("value")
    return value


def _put_optional(target: dict[str, Any], key: str, value: Any, caster: type) -> None:
    if value is not None:
        target[key] = caster(value)


def _urllib_json_transport(url: str) -> Mapping[str, Any]:
    with urlopen(url, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _urllib_authenticated_json_transport(url: str, headers: Mapping[str, str]) -> Mapping[str, Any]:
    request = Request(url, headers=dict(headers))
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))
