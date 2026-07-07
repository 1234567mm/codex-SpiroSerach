from __future__ import annotations

import json
from typing import Any, Callable, Mapping
from urllib.parse import quote
from urllib.request import urlopen

from spirosearch.providers.base import ProviderResponse
from spirosearch.source_registry import SourceRateLimiter, SourceRegistry, SourceRegistryEntry


PUBCHEM_PROPERTIES = (
    "MolecularFormula",
    "MolecularWeight",
    "CanonicalSMILES",
    "InChIKey",
    "XLogP",
    "TPSA",
    "HBondDonorCount",
    "HBondAcceptorCount",
)


class PubChemPUGRestProvider:
    provider_name = "pubchem"

    def __init__(
        self,
        *,
        base_url: str = "https://pubchem.ncbi.nlm.nih.gov/rest/pug",
        transport: Callable[[str], Mapping[str, Any]] | None = None,
        retrieved_at: str,
        license_hint: str = "PubChem data terms; cite NCBI PubChem",
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
        self.trust_level = registry_entry.trust_level if registry_entry is not None else "T3_literature_machine"
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
        transport: Callable[[str], Mapping[str, Any]] | None = None,
        retrieved_at: str,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> "PubChemPUGRestProvider":
        return cls(
            transport=transport,
            retrieved_at=retrieved_at,
            registry_entry=registry.get(cls.provider_name),
            rate_limiter=registry.rate_limiter(cls.provider_name, clock=clock, sleeper=sleeper),
            clock=clock,
            sleeper=sleeper,
        )

    def lookup_name(self, name: str) -> ProviderResponse:
        query_value = name.strip()
        if not query_value:
            raise ValueError("name query is required")
        if self.rate_limiter is not None:
            self.rate_limiter.wait_for_slot()
        url = self._property_url("name", query_value)
        payload = self._fetch_with_backoff(url)
        normalized, confidence = _normalize_pubchem_properties(payload)
        return ProviderResponse.from_payload(
            provider=self.provider_name,
            query=f"name:{query_value.casefold()}",
            normalized_result=normalized,
            source_url=url,
            retrieved_at=self.retrieved_at,
            license_hint=self.license_hint,
            raw_payload=payload,
            confidence=confidence,
            trust_level=self.trust_level,
            allowed_output_fields=self.allowed_output_fields,
        )

    def _property_url(self, namespace: str, value: str) -> str:
        properties = ",".join(PUBCHEM_PROPERTIES)
        return f"{self.base_url}/compound/{namespace}/{quote(value)}/property/{properties}/JSON"

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


def _normalize_pubchem_properties(payload: Mapping[str, Any]) -> tuple[dict[str, Any], float]:
    records = list(dict(payload.get("PropertyTable", {})).get("Properties", []))
    if not records:
        return {
            "resolution_status": "not_found",
            "ambiguity_flag": True,
            "ambiguous_cids": [],
        }, 0.1
    if len(records) > 1:
        return {
            "resolution_status": "ambiguous",
            "ambiguity_flag": True,
            "ambiguous_cids": [int(record["CID"]) for record in records if "CID" in record],
        }, 0.35

    record = dict(records[0])
    normalized = {
        "resolution_status": "resolved",
        "ambiguity_flag": False,
        "ambiguous_cids": [],
    }
    _put_optional(normalized, "cid", record.get("CID"), int)
    _put_optional(normalized, "molecular_formula", record.get("MolecularFormula"), str)
    _put_optional(normalized, "molecular_weight", record.get("MolecularWeight"), float)
    _put_optional(normalized, "canonical_smiles", record.get("CanonicalSMILES"), str)
    _put_optional(normalized, "inchi_key", record.get("InChIKey"), str)
    _put_optional(normalized, "xlogp", record.get("XLogP"), float)
    _put_optional(normalized, "tpsa", record.get("TPSA"), float)
    _put_optional(normalized, "hbd_count", record.get("HBondDonorCount"), int)
    _put_optional(normalized, "hba_count", record.get("HBondAcceptorCount"), int)
    return normalized, 0.65


def _put_optional(target: dict[str, Any], key: str, value: Any, caster: type) -> None:
    if value is not None:
        target[key] = caster(value)
