from __future__ import annotations

import json
from typing import Any, Callable, Mapping
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import urlopen

from spirosearch.providers.base import ProviderResponse
from spirosearch.source_registry import SourceRateLimiter, SourceRegistry, SourceRegistryEntry


PUBCHEM_PROPERTIES = (
    "MolecularFormula",
    "MolecularWeight",
    "CanonicalSMILES",
    "IsomericSMILES",
    "InChI",
    "InChIKey",
    "XLogP",
    "TPSA",
    "HBondDonorCount",
    "HBondAcceptorCount",
)


class PubChemHTTPStatusError(Exception):
    def __init__(self, status_code: int):
        super().__init__(f"PubChem HTTP status {status_code}")
        self.status_code = status_code


class PubChemPUGRestProvider:
    """PubChem PUG REST identity provider.

    DEPRECATED (V37.1, 2026-08-12): the Go live provider is the production
    runtime for PubChem identity lookup. `spiroctl source-provider lookup
    pubchem --name <name> [--cache <path> --authorize-cache-write]` executes
    the same lookup through the Go client (real HTTP, rate limiter, provider
    cache integration, ProviderResponse contract). This Python class is kept
    as the oracle reference for parity testing until the E2 deprecation
    cleanup phase; new PubChem live calls should not start here.
    """

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
        raw_payload: Mapping[str, Any]
        if normalized.get("resolution_status") == "resolved":
            synonyms_url = self._synonyms_url("name", query_value)
            if self.rate_limiter is not None:
                self.rate_limiter.wait_for_slot()
            synonyms_payload = self._fetch_with_backoff(synonyms_url)
            normalized["synonyms"] = _normalize_pubchem_synonyms(
                synonyms_payload,
                cid=int(normalized["cid"]) if "cid" in normalized else None,
            )
            normalized["source_attribution"] = _source_attribution(
                property_url=url,
                synonyms_url=synonyms_url,
                license_hint=self.license_hint,
            )
            raw_payload = {"properties": payload, "synonyms": synonyms_payload}
        else:
            normalized["source_attribution"] = _source_attribution(
                property_url=url,
                synonyms_url=None,
                license_hint=self.license_hint,
            )
            raw_payload = {"properties": payload}
        return ProviderResponse.from_payload(
            provider=self.provider_name,
            query=f"name:{query_value.casefold()}",
            normalized_result=normalized,
            source_url=url,
            retrieved_at=self.retrieved_at,
            license_hint=self.license_hint,
            raw_payload=raw_payload,
            confidence=confidence,
            trust_level=self.trust_level,
            allowed_output_fields=self.allowed_output_fields,
        )

    def _property_url(self, namespace: str, value: str) -> str:
        properties = ",".join(PUBCHEM_PROPERTIES)
        return f"{self.base_url}/compound/{namespace}/{quote(value)}/property/{properties}/JSON"

    def _synonyms_url(self, namespace: str, value: str) -> str:
        return f"{self.base_url}/compound/{namespace}/{quote(value)}/synonyms/JSON"

    def _fetch_with_backoff(self, url: str) -> Mapping[str, Any]:
        try:
            return self.transport(url)
        except Exception as exc:
            if _is_negative_http_error(exc):
                return _empty_property_payload()
            if self.rate_limiter is None:
                raise
            self.rate_limiter.wait_for_retry(attempt=1)
            try:
                return self.transport(url)
            except Exception as retry_exc:
                if _is_negative_http_error(retry_exc):
                    return _empty_property_payload()
                raise


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
    _put_optional(normalized, "isomeric_smiles", record.get("IsomericSMILES"), str)
    _put_optional(normalized, "inchi", record.get("InChI"), str)
    _put_optional(normalized, "inchi_key", record.get("InChIKey"), str)
    _put_optional(normalized, "xlogp", record.get("XLogP"), float)
    _put_optional(normalized, "tpsa", record.get("TPSA"), float)
    _put_optional(normalized, "hbd_count", record.get("HBondDonorCount"), int)
    _put_optional(normalized, "hba_count", record.get("HBondAcceptorCount"), int)
    return normalized, 0.65


def _normalize_pubchem_synonyms(payload: Mapping[str, Any], *, cid: int | None) -> list[str]:
    information = list(dict(payload.get("InformationList", {})).get("Information", []))
    selected: Mapping[str, Any] | None = None
    for item in information:
        record = dict(item)
        if cid is None or int(record.get("CID", -1)) == cid:
            selected = record
            break
    if selected is None:
        return []
    synonyms = selected.get("Synonym", [])
    if not isinstance(synonyms, list):
        return []
    seen: set[str] = set()
    normalized: list[str] = []
    for synonym in synonyms:
        text = str(synonym).strip()
        key = text.casefold()
        if text and key not in seen:
            seen.add(key)
            normalized.append(text)
    return normalized


def _source_attribution(
    *,
    property_url: str,
    synonyms_url: str | None,
    license_hint: str,
) -> dict[str, Any]:
    return {
        "provider": "PubChem",
        "property_url": property_url,
        "synonyms_url": synonyms_url,
        "license_hint": license_hint,
    }


def _put_optional(target: dict[str, Any], key: str, value: Any, caster: type) -> None:
    if value is not None:
        target[key] = caster(value)


def _empty_property_payload() -> Mapping[str, Any]:
    return {"PropertyTable": {"Properties": []}}


def _is_negative_http_error(exc: Exception) -> bool:
    status_code = _http_status_code(exc)
    return status_code in {400, 404}


def _http_status_code(exc: Exception) -> int | None:
    if isinstance(exc, HTTPError):
        return int(exc.code)
    for attr in ("status_code", "code"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    return None
