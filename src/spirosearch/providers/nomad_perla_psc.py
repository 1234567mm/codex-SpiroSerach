from __future__ import annotations

import json
import hashlib
from typing import Any, Callable, Mapping

from spirosearch.providers.base import ProviderResponse
from spirosearch.source_registry import SourceRateLimiter, SourceRegistry, SourceRegistryEntry


JSONPostTransport = Callable[[str, bytes, Mapping[str, str]], Mapping[str, Any]]

# Synonym expansion for common HTL names
_HTL_SYNONYMS: dict[str, list[str]] = {
    "spiro-ometad": ["Spiro-OMeTAD", "spiro-OMeTAD", "spiroometad", "spiro-omeTAD"],
    "ptaa": ["PTAA", "poly[bis(4-phenyl)(2,4,6-trimethylphenyl)amine]"],
    "pedot:pss": ["PEDOT:PSS", "pedot-pss"],
    "meo-2pacz": ["MeO-2PACz", "meo-2pacz"],
    "nio_x": ["NiOx", "NiO_x", "NiO"],
}


def _expand_htl_synonyms(htl_name: str) -> list[str]:
    """Return expanded search terms including synonyms."""
    key = htl_name.casefold().strip()
    terms = [htl_name]
    synonyms = _HTL_SYNONYMS.get(key, [])
    terms.extend(synonyms)
    return terms


def _htl_list_contains(htl_name: str, htl_list: Any) -> tuple[bool, bool]:
    """Check if htl_list contains exact or synonym match.

    Returns (exact_hit, synonym_hit).
    """
    if htl_list is None:
        return False, False
    if isinstance(htl_list, str):
        # Fallback: treat single string as a one-element list
        htl_list = [htl_list]
    if not isinstance(htl_list, list):
        return False, False
    query_lower = htl_name.casefold().strip()
    for item in htl_list:
        if item is None:
            continue
        item_lower = str(item).casefold().strip()
        if item_lower == query_lower:
            return True, False
    # No exact match — check synonyms
    synonyms = _HTL_SYNONYMS.get(query_lower, [])
    synonym_lower = [s.casefold() for s in synonyms]
    for item in htl_list:
        if item is None:
            continue
        item_lower = str(item).casefold().strip()
        if item_lower in synonym_lower and item_lower != query_lower:
            return False, True
    return False, False


def _normalize_psc_device(
    search_entry: Mapping[str, Any],
    archive_entry: Mapping[str, Any] | None,
    htl_name: str,
) -> tuple[dict[str, Any], float]:
    """Extract PSC device fields from NOMAD search + archive payloads.

    Search response contains summary data in results.properties.optoelectronic.solar_cell.
    Archive response contains detailed data in
    data.perovskite_solar_cell_database.device.SolarCell.

    Returns (normalized_dict, confidence).
    """
    normalized: dict[str, Any] = {}

    # Entry-level metadata (available in both search and archive)
    _put_optional(normalized, "entry_id", search_entry.get("entry_id"), str)
    _put_optional(normalized, "upload_id", search_entry.get("upload_id"), str)
    _put_optional(normalized, "htl_name", htl_name, str)

    # --- Try search response data first (results.properties.optoelectronic.solar_cell) ---
    results = dict(search_entry.get("results", {}))
    material = dict(results.get("material", {}))
    properties = dict(results.get("properties", {}))
    optoelectronic = dict(properties.get("optoelectronic", {}))
    solar_cell = dict(optoelectronic.get("solar_cell", {}))

    # HTL from search (list type, e.g. ["Spiro-OMeTAD"])
    htl_from_search = solar_cell.get("hole_transport_layer")

    # Device stack from search (list type, e.g. ["SLG","ITO",...])
    device_stack_search = solar_cell.get("device_stack")
    if device_stack_search is not None:
        if isinstance(device_stack_search, list):
            device_stack_str = "/".join(str(s) for s in device_stack_search)
        else:
            device_stack_str = str(device_stack_search)
        _put_optional(normalized, "device_stack", device_stack_str, str)

    # Metrics from search response
    _put_optional(normalized, "pce_percent", solar_cell.get("efficiency"), float)
    _put_optional(normalized, "voc_v", solar_cell.get("open_circuit_voltage"), float)
    _put_optional(normalized, "fill_factor", solar_cell.get("fill_factor"), float)

    # Jsc from search: in A/m^2 (e.g. 235.0), convert to mA/cm^2 (x0.1)
    jsc_search = solar_cell.get("short_circuit_current_density")
    if jsc_search is not None:
        jsc_converted = _convert_jsc_search(jsc_search)
        _put_optional(normalized, "jsc_ma_cm2", jsc_converted, float)

    # Chemical formula from search results
    chemical_formula = material.get("chemical_formula_reduced") or material.get("chemical_formula_hill")
    _put_optional(normalized, "chemical_formula", chemical_formula, str)

    # --- Try archive data for richer fields (if available) ---
    psc_device = {}
    archive_metadata = {}
    if archive_entry is not None:
        archive = dict(archive_entry.get("archive", archive_entry))
        archive_data = dict(archive.get("data", {}))
        archive_meta = dict(archive.get("metadata", {}))

        # Deep path: data.perovskite_solar_cell_database.device.SolarCell
        psc_db = dict(archive_data.get("perovskite_solar_cell_database", {}))
        device_section = dict(psc_db.get("device", {}))
        psc_device = dict(device_section.get("SolarCell", {}))
        archive_metadata = archive_meta

    # Archive provides more detailed fields — override search where archive has data
    if psc_device:
        # HTL name from archive (string, e.g. "Spiro-OMeTAD")
        htl_from_archive = psc_device.get("hole_transport_layer_name")
        if htl_from_archive is not None and htl_from_search is None:
            htl_from_search = htl_from_archive

        # Device stack from archive (string, e.g. "ITO/SnO2/MAPbI3/Spiro-OMeTAD/Au")
        archive_device_stack = psc_device.get("device_stack")
        if archive_device_stack is not None and "device_stack" not in normalized:
            _put_optional(normalized, "device_stack", archive_device_stack, str)

        # PCE from archive (already percent, e.g. 21.3)
        archive_pce = psc_device.get("power_conversion_efficiency") or psc_device.get("efficiency")
        if archive_pce is not None and "pce_percent" not in normalized:
            _put_optional(normalized, "pce_percent", archive_pce, float)

        # Voc from archive
        archive_voc = psc_device.get("open_circuit_voltage")
        if archive_voc is not None and "voc_v" not in normalized:
            _put_optional(normalized, "voc_v", archive_voc, float)

        # Jsc from archive: already in mA/cm² (e.g. 23.5), no conversion needed
        archive_jsc = psc_device.get("short_circuit_current_density")
        if archive_jsc is not None and "jsc_ma_cm2" not in normalized:
            _put_optional(normalized, "jsc_ma_cm2", archive_jsc, float)

        # FF from archive
        archive_ff = psc_device.get("fill_factor")
        if archive_ff is not None and "fill_factor" not in normalized:
            _put_optional(normalized, "fill_factor", archive_ff, float)

        # Perovskite composition from archive
        archive_perovskite = psc_device.get("perovskite_composition")
        _put_optional(normalized, "perovskite_composition", archive_perovskite, str)

        # Chemical formula from archive
        archive_formula = archive_metadata.get("chemical_formula") or psc_device.get("chemical_formula")
        if archive_formula is not None and "chemical_formula" not in normalized:
            _put_optional(normalized, "chemical_formula", archive_formula, str)

    # Perovskite composition: also try from search if archive didn't provide it
    if "perovskite_composition" not in normalized and psc_device:
        # Already tried above; skip
        pass
    # If no archive at all, no perovskite_composition from search alone

    # DOI and license from datasets/references (both search and archive)
    datasets = search_entry.get("datasets", [])
    if not datasets and archive_metadata:
        datasets = archive_metadata.get("datasets", [])
    source_doi = _extract_doi_from_datasets(datasets)
    if source_doi is None:
        source_doi = _extract_doi_from_references(search_entry.get("references"))
    if source_doi is None and archive_metadata:
        source_doi = _extract_doi_from_references(archive_metadata.get("references"))
    if source_doi is None and psc_device:
        source_doi = _extract_doi_from_references(psc_device.get("DOI_number"))

    license_value = _extract_license_from_datasets(datasets)
    if license_value is None and archive_metadata:
        license_value = _value_or_raw(archive_metadata.get("license"))
    _put_optional(normalized, "source_doi", source_doi, str)
    _put_optional(normalized, "license", license_value, str)

    # --- Confidence computation ---
    # Determine HTL match: check both search (list) and archive (string)
    htl_for_match = htl_from_search
    exact_hit, synonym_hit = _htl_list_contains(htl_name, htl_for_match)
    psc_section_present = bool(solar_cell) or bool(psc_device)

    has_pce = "pce_percent" in normalized
    has_voc = "voc_v" in normalized
    has_jsc = "jsc_ma_cm2" in normalized
    has_ff = "fill_factor" in normalized
    metric_count = sum([has_pce, has_voc, has_jsc, has_ff])

    if exact_hit and metric_count == 4:
        base_confidence = 0.85
    elif exact_hit and metric_count >= 2:
        base_confidence = 0.55
    elif exact_hit and metric_count == 0:
        base_confidence = 0.35
    elif not exact_hit and psc_section_present:
        base_confidence = 0.30
    else:
        base_confidence = 0.15

    if synonym_hit:
        base_confidence = max(0.0, base_confidence - 0.10)

    return normalized, base_confidence


def _convert_jsc_search(raw: Any) -> float | None:
    """Convert Jsc from search response: stored in A/m^2, convert to mA/cm^2 (x0.1).

    Probe confirmed search response values like 235.0, 228.0 are in A/m^2.
    Conversion: 1 A/m^2 = 0.1 mA/cm^2.
    """
    value = _value_or_raw(raw)
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v * 0.1


def _extract_doi_from_datasets(datasets: Any) -> str | None:
    """Extract DOI from datasets list (search or archive metadata)."""
    if not isinstance(datasets, list) or not datasets:
        return None
    first = datasets[0]
    if isinstance(first, Mapping):
        doi = first.get("doi")
        if doi:
            return str(doi)
    return None


def _extract_doi_from_references(references: Any) -> str | None:
    """Extract a DOI from a reference field or list of reference strings."""
    if references is None:
        return None
    values = references if isinstance(references, list) else [references]
    for value in values:
        text = str(_value_or_raw(value) or "").strip()
        if not text:
            continue
        marker = "doi.org/"
        marker_index = text.casefold().find(marker)
        if marker_index >= 0:
            return text[marker_index + len(marker):].strip()
        if text.startswith("10.") and "/" in text:
            return text
    return None


def _extract_license_from_datasets(datasets: Any) -> str | None:
    """Extract license from datasets list (search or archive metadata)."""
    if not isinstance(datasets, list) or not datasets:
        return None
    first = datasets[0]
    if isinstance(first, Mapping):
        license_val = first.get("license")
        if license_val:
            return str(license_val)
    return None


def _value_or_raw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return value.get("value")
    return value


def _put_optional(target: dict[str, Any], key: str, value: Any, caster: type) -> None:
    if value is not None:
        target[key] = caster(value)


def _query_hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def _review_reasons_for_device(
    normalized: Mapping[str, Any],
    search_entry: Mapping[str, Any],
    htl_name: str,
    archive_status: str,
) -> list[str]:
    reasons: list[str] = []
    if archive_status in {"empty", "unavailable"}:
        reasons.append("archive_unavailable")
    if not search_entry:
        return reasons

    solar_cell = _search_solar_cell(search_entry)
    exact_hit, synonym_hit = _htl_list_contains(
        htl_name,
        solar_cell.get("hole_transport_layer"),
    )
    if not exact_hit and not synonym_hit:
        reasons.append("htl_match_missing_or_ambiguous")
    if "device_stack" not in normalized:
        reasons.append("device_stack_missing")
    if "source_doi" not in normalized:
        reasons.append("source_doi_missing")
    if "license" not in normalized:
        reasons.append("license_missing")
    metric_keys = ("pce_percent", "voc_v", "jsc_ma_cm2", "fill_factor")
    if not all(key in normalized for key in metric_keys):
        reasons.append("device_metrics_incomplete")
    return reasons


def _search_solar_cell(search_entry: Mapping[str, Any]) -> Mapping[str, Any]:
    results = dict(search_entry.get("results", {}))
    properties = dict(results.get("properties", {}))
    optoelectronic = dict(properties.get("optoelectronic", {}))
    solar_cell = optoelectronic.get("solar_cell", {})
    return dict(solar_cell) if isinstance(solar_cell, Mapping) else {}


def _apply_review_markers(
    normalized: dict[str, Any],
    *,
    search_entry: Mapping[str, Any],
    htl_name: str,
    archive_status: str,
    confidence: float,
) -> float:
    reasons = _review_reasons_for_device(normalized, search_entry, htl_name, archive_status)
    normalized["archive_status"] = archive_status
    normalized["review_required"] = bool(reasons)
    normalized["review_reasons"] = reasons
    if reasons:
        return min(confidence, 0.55)
    return confidence


class NomadPerlaPscProvider:
    provider_name = "nomad_perla_psc"

    def __init__(
        self,
        *,
        base_url: str = "https://nomad-lab.eu/prod/v1/api/v1",
        transport: JSONPostTransport | None = None,
        retrieved_at: str,
        license_hint: str = "NOMAD PERLA PSC CC-BY-4.0; preserve original dataset attribution",
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
        self._post_transport = transport or _urllib_json_post_transport
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
        transport: JSONPostTransport | None = None,
        retrieved_at: str,
        clock: Callable[[], float] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> "NomadPerlaPscProvider":
        return cls(
            transport=transport,
            retrieved_at=retrieved_at,
            registry_entry=registry.get(cls.provider_name),
            rate_limiter=registry.rate_limiter(cls.provider_name, clock=clock, sleeper=sleeper),
            clock=clock,
            sleeper=sleeper,
        )

    def lookup_htl(self, htl_name: str) -> ProviderResponse:
        """Look up HTL device data from NOMAD PERLA PSC database."""
        query_value = htl_name.strip()
        if not query_value:
            raise ValueError("htl_name query is required")
        if self.rate_limiter is not None:
            self.rate_limiter.wait_for_slot()

        # Step 1: Search entries matching HTL name
        # Use the correct API path confirmed by probe:
        #   results.properties.optoelectronic.solar_cell.hole_transport_layer:any
        search_url = f"{self.base_url}/entries/query"
        search_terms = _expand_htl_synonyms(query_value)
        search_body = {
            "owner": "public",
            "query": {
                "sections:all": ["nomad.datamodel.results.SolarCell"],
                "results.properties.optoelectronic.solar_cell.hole_transport_layer:any": search_terms,
            },
            "pagination": {"page_size": 25},
        }
        search_body_bytes = json.dumps(search_body).encode("utf-8")
        query_hash = _query_hash(search_body_bytes)
        headers = {"Content-Type": "application/json"}
        search_payload = self._fetch_with_backoff(search_url, search_body_bytes, headers)

        # Extract entry IDs from search results
        entry_ids = []
        first_search_entry = {}
        data_list = search_payload.get("data", [])
        if isinstance(data_list, list):
            for item in data_list:
                if isinstance(item, Mapping):
                    eid = item.get("entry_id")
                    if eid:
                        entry_ids.append(eid)
            if data_list and isinstance(data_list[0], Mapping):
                first_search_entry = dict(data_list[0])

        # Step 2: Fetch archive details (with rate-limit tolerance)
        # Probe confirmed archive endpoint has severe rate limiting (429/500).
        # If archive fails, fall back to search-only data.
        archive_entry = None
        archive_status = "not_requested"
        archive_error: dict[str, str] | None = None
        if entry_ids:
            archive_status = "unavailable"
            try:
                if self.rate_limiter is not None:
                    self.rate_limiter.wait_for_slot()
                archive_url = f"{self.base_url}/entries/archive/query"
                archive_body = {
                    "entry_id": entry_ids[:1],  # Only fetch first entry to reduce rate-limit risk
                    "required": {
                        "metadata": "*",
                        "data": "*",
                    },
                }
                archive_body_bytes = json.dumps(archive_body).encode("utf-8")
                archive_payload = self._fetch_with_backoff(archive_url, archive_body_bytes, headers)
                archive_data_list = archive_payload.get("data", [])
                if isinstance(archive_data_list, list) and archive_data_list:
                    if isinstance(archive_data_list[0], Mapping):
                        archive_entry = dict(archive_data_list[0])
                        archive_status = "available"
                elif isinstance(archive_data_list, list):
                    archive_status = "empty"
            except Exception as exc:
                archive_error = {
                    "type": type(exc).__name__,
                    "message": str(exc),
                }
                archive_entry = None

        # Normalize from search entry + optional archive enrichment
        normalized, confidence = _normalize_psc_device(
            first_search_entry, archive_entry, query_value
        )
        normalized["query_hash"] = query_hash
        confidence = _apply_review_markers(
            normalized,
            search_entry=first_search_entry,
            htl_name=query_value,
            archive_status=archive_status,
            confidence=confidence,
        )

        raw_data = {
            "search": dict(search_payload),
            "archive": dict(archive_entry) if archive_entry is not None else {},
            "archive_status": archive_status,
        }
        if archive_error is not None:
            raw_data["archive_error"] = archive_error

        return ProviderResponse.from_payload(
            provider=self.provider_name,
            query=f"htl:{query_value}",
            normalized_result=normalized,
            source_url=f"{self.base_url}/entries/query",
            retrieved_at=self.retrieved_at,
            license_hint=self.license_hint,
            raw_payload=raw_data,
            confidence=confidence,
            trust_level=self.trust_level,
            allowed_output_fields=self.allowed_output_fields,
        )

    def lookup_htl_page(self, htl_name: str, page_after_value: str) -> ProviderResponse:
        """Paginated HTL lookup using cursor-based pagination."""
        query_value = htl_name.strip()
        if not query_value:
            raise ValueError("htl_name query is required")
        if not page_after_value.strip():
            raise ValueError("page_after_value is required for pagination")
        if self.rate_limiter is not None:
            self.rate_limiter.wait_for_slot()

        search_url = f"{self.base_url}/entries/query"
        search_terms = _expand_htl_synonyms(query_value)
        search_body = {
            "owner": "public",
            "query": {
                "sections:all": ["nomad.datamodel.results.SolarCell"],
                "results.properties.optoelectronic.solar_cell.hole_transport_layer:any": search_terms,
            },
            "pagination": {
                "page_size": 25,
                "page_after_value": page_after_value,
            },
        }
        search_body_bytes = json.dumps(search_body).encode("utf-8")
        query_hash = _query_hash(search_body_bytes)
        headers = {"Content-Type": "application/json"}
        search_payload = self._fetch_with_backoff(search_url, search_body_bytes, headers)

        entry_ids = []
        first_search_entry = {}
        data_list = search_payload.get("data", [])
        if isinstance(data_list, list):
            for item in data_list:
                if isinstance(item, Mapping):
                    eid = item.get("entry_id")
                    if eid:
                        entry_ids.append(eid)
            if data_list and isinstance(data_list[0], Mapping):
                first_search_entry = dict(data_list[0])

        archive_entry = None
        archive_status = "not_requested"
        archive_error: dict[str, str] | None = None
        if entry_ids:
            archive_status = "unavailable"
            try:
                if self.rate_limiter is not None:
                    self.rate_limiter.wait_for_slot()
                archive_url = f"{self.base_url}/entries/archive/query"
                archive_body = {
                    "entry_id": entry_ids[:1],
                    "required": {
                        "metadata": "*",
                        "data": "*",
                    },
                }
                archive_body_bytes = json.dumps(archive_body).encode("utf-8")
                archive_payload = self._fetch_with_backoff(archive_url, archive_body_bytes, headers)
                archive_data_list = archive_payload.get("data", [])
                if isinstance(archive_data_list, list) and archive_data_list:
                    if isinstance(archive_data_list[0], Mapping):
                        archive_entry = dict(archive_data_list[0])
                        archive_status = "available"
                elif isinstance(archive_data_list, list):
                    archive_status = "empty"
            except Exception as exc:
                archive_error = {
                    "type": type(exc).__name__,
                    "message": str(exc),
                }
                archive_entry = None

        normalized, confidence = _normalize_psc_device(
            first_search_entry, archive_entry, query_value
        )
        normalized["query_hash"] = query_hash
        confidence = _apply_review_markers(
            normalized,
            search_entry=first_search_entry,
            htl_name=query_value,
            archive_status=archive_status,
            confidence=confidence,
        )

        raw_data = {
            "search": dict(search_payload),
            "archive": dict(archive_entry) if archive_entry is not None else {},
            "archive_status": archive_status,
        }
        if archive_error is not None:
            raw_data["archive_error"] = archive_error

        return ProviderResponse.from_payload(
            provider=self.provider_name,
            query=f"htl:{query_value}",
            normalized_result=normalized,
            source_url=f"{self.base_url}/entries/query",
            retrieved_at=self.retrieved_at,
            license_hint=self.license_hint,
            raw_payload=raw_data,
            confidence=confidence,
            trust_level=self.trust_level,
            allowed_output_fields=self.allowed_output_fields,
        )

    def search_by_htl(self, htl_name: str, max_results: int = 25) -> ProviderResponse:
        """Search for device data matching a given HTL name, returning multiple entries.

        Returns a ProviderResponse with a normalized_result containing:
        - match_type: "exact", "synonym", or "none"
        - device_count: number of devices found
        - devices: list of individual device dicts with normalized fields
        """
        query_value = htl_name.strip()
        if not query_value:
            raise ValueError("htl_name query is required")
        if max_results < 1:
            raise ValueError("max_results must be positive")
        if self.rate_limiter is not None:
            self.rate_limiter.wait_for_slot()

        search_url = f"{self.base_url}/entries/query"
        search_terms = _expand_htl_synonyms(query_value)
        search_body = {
            "owner": "public",
            "query": {
                "sections:all": ["nomad.datamodel.results.SolarCell"],
                "results.properties.optoelectronic.solar_cell.hole_transport_layer:any": search_terms,
            },
            "pagination": {"page_size": max_results},
        }
        search_body_bytes = json.dumps(search_body).encode("utf-8")
        query_hash = _query_hash(search_body_bytes)
        headers = {"Content-Type": "application/json"}
        search_payload = self._fetch_with_backoff(search_url, search_body_bytes, headers)

        data_list = search_payload.get("data", [])
        if not isinstance(data_list, list):
            data_list = []

        # Determine overall match type from the first entry that has HTL info
        match_type = "none"
        for item in data_list:
            if not isinstance(item, Mapping):
                continue
            results = dict(item.get("results", {}))
            properties = dict(results.get("properties", {}))
            optoelectronic = dict(properties.get("optoelectronic", {}))
            solar_cell = dict(optoelectronic.get("solar_cell", {}))
            htl_list = solar_cell.get("hole_transport_layer")
            exact_hit, synonym_hit = _htl_list_contains(query_value, htl_list)
            if exact_hit:
                match_type = "exact"
                break
            if synonym_hit:
                match_type = "synonym"
                break

        # Normalize each device entry individually
        devices: list[dict[str, Any]] = []
        review_reasons: set[str] = set()
        for item in data_list:
            if not isinstance(item, Mapping):
                continue
            device_normalized, _ = _normalize_psc_device(dict(item), None, query_value)
            review_reasons.update(
                _review_reasons_for_device(
                    device_normalized,
                    dict(item),
                    query_value,
                    "not_requested",
                )
            )
            devices.append(device_normalized)

        # Confidence based on match type
        if match_type == "exact":
            confidence = 0.75
        elif match_type == "synonym":
            confidence = 0.55
        else:
            confidence = 0.2

        normalized: dict[str, Any] = {
            "htl_name": query_value,
            "query_hash": query_hash,
            "match_type": match_type,
            "device_count": len(devices),
            "devices": devices,
            "archive_status": "not_requested",
            "review_required": bool(review_reasons),
            "review_reasons": sorted(review_reasons),
        }
        if review_reasons:
            confidence = min(confidence, 0.55)

        return ProviderResponse.from_payload(
            provider=self.provider_name,
            query=f"htl_search:{query_value}",
            normalized_result=normalized,
            source_url=f"{self.base_url}/entries/query",
            retrieved_at=self.retrieved_at,
            license_hint=self.license_hint,
            raw_payload=dict(search_payload),
            confidence=confidence,
            trust_level=self.trust_level,
            allowed_output_fields=self.allowed_output_fields,
        )

    def _fetch_with_backoff(self, url: str, body: bytes, headers: Mapping[str, str]) -> Mapping[str, Any]:
        try:
            return self._post_transport(url, body, headers)
        except Exception:
            if self.rate_limiter is None:
                raise
            self.rate_limiter.wait_for_retry(attempt=1)
            return self._post_transport(url, body, headers)


def _urllib_json_post_transport(url: str, body: bytes, headers: Mapping[str, str]) -> Mapping[str, Any]:
    from urllib.request import Request, urlopen

    request = Request(url, data=body, headers=dict(headers), method="POST")
    with urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode("utf-8"))
