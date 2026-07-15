"""V22 scientific-validation adapters.

These helpers keep provider facts as lineage-bearing evidence records. They do
not make scoring or scientific-closure decisions.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping

from spirosearch.providers.base import ProviderResponse


_SUPPORTED_PROPERTIES = {"homo", "lumo", "band_gap"}
_REFERENCE_SCALES = {"vacuum", "ferrocene", "sce", "ag_agcl"}


def adapt_provider_response_energy(
    response: ProviderResponse,
    *,
    canonical_targets: Iterable[Mapping[str, Any]],
    review_blockers: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Adapt complete provider energy facts to V22 snapshot-shaped records.

    The adapter only joins facts to explicit canonical targets. Incomplete facts
    remain diagnostics and cannot clear stale energy blockers.
    """

    targets = [_target_key(target) for target in canonical_targets]
    target_by_key = {target["key"]: target["record"] for target in targets if target["key"]}
    diagnostics: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []

    facts = response.normalized_result.get("energy_facts", ())
    if not isinstance(facts, list):
        return {
            "records": [],
            "diagnostics": [{
                "reason_code": "energy_facts_invalid",
                "message": "ProviderResponse normalized_result.energy_facts must be a list.",
                "provider_response_id": response.response_id,
            }],
            "cleared_blocking_review_ids": [],
        }

    for index, fact in enumerate(facts):
        if not isinstance(fact, Mapping):
            diagnostics.append(_diagnostic("energy_fact_invalid", response, index))
            continue
        key = (
            _text(fact.get("material_id")),
            _text(fact.get("use_instance_id")),
            _text(fact.get("property_name")),
        )
        target = target_by_key.get(key)
        if target is None:
            diagnostics.append(_diagnostic("canonical_target_not_matched", response, index))
            continue

        missing = _missing_policy_fields(fact)
        if missing:
            diagnostics.extend(_diagnostic(code, response, index, target) for code in missing)
            continue

        evidence_id = _text(target.get("energy_evidence_id")) or (
            f"v22:{response.response_id}:{key[0]}:{key[1]}:{key[2]}"
        )
        records.append({
            "record_id": f"v22-record:{response.response_id}:{evidence_id}",
            "candidate_id": _text(target.get("candidate_id")),
            "material_id": key[0],
            "use_instance_id": key[1],
            "source_id": _text(fact.get("source_id")),
            "license_id": response.license_hint,
            "identity": {
                "stable_identity_id": _text(target.get("stable_identity_id")) or _text(target.get("candidate_id")),
                "identity_review_state": "accepted",
            },
            "energy_evidence": [{
                "evidence_id": evidence_id,
                "property_name": key[2],
                "value_ev": float(fact["value_ev"]),
                "unit": _text(fact.get("unit")),
                "method": _text(fact.get("method")),
                "reference_scale": _text(fact.get("reference_scale")),
            }],
            "lineage": {
                "source_ledger_id": _text(target.get("source_ledger_id")) or "pending-source-ledger",
                "provider_response_id": response.response_id,
                "raw_hash": _prefixed_hash(response.raw_hash),
                "retrieved_at": response.retrieved_at,
                "source_url": response.source_url,
                "provider": response.provider,
                "trust_level": response.trust_level,
                "curation_status": _text(fact.get("curation_status")),
                "source_artifact_kinds": ["provider_cache"],
            },
        })

    cleared = _cleared_blockers(records, review_blockers)
    return {
        "records": sorted(records, key=lambda item: item["record_id"]),
        "diagnostics": sorted(diagnostics, key=lambda item: (item["reason_code"], item.get("record_index", -1))),
        "cleared_blocking_review_ids": cleared,
    }


def build_v22_quality_reports(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Build deterministic V22 quality and zero-leakage reports."""

    snapshot_id = _text(snapshot.get("snapshot_id")) or "unknown-snapshot"
    records = [record for record in snapshot.get("records", []) if isinstance(record, Mapping)]
    records = sorted(records, key=lambda item: (_text(item.get("record_id")), _text(item.get("candidate_id"))))
    duplicate_ids = _duplicate_values(records, "record_id")
    duplicate_records = [
        _report_item(record, "duplicate_record_id")
        for record in records
        if _text(record.get("record_id")) in duplicate_ids
    ]
    duplicate_record_ids = {_text(item.get("record_id")) for item in duplicate_records}

    rejected_records = sorted(
        [
            {
                "record_id": _text(item.get("record_id")),
                "reason_code": _text(item.get("reason_code")) or "record_rejected",
            }
            for item in snapshot.get("rejected_records", [])
            if isinstance(item, Mapping) and _text(item.get("record_id"))
        ],
        key=lambda item: item["record_id"],
    )
    blocked_records = [
        _report_item(record, "identity_blocked")
        for record in records
        if _identity_state(record) == "blocked"
    ]
    ambiguous_records = [
        _report_item(record, f"identity_{_identity_state(record) or 'ambiguous'}")
        for record in records
        if _identity_state(record) not in {"accepted", "blocked"}
    ]
    conflicting_records = _conflicting_material_records(records)
    accepted_record_ids = sorted({
        _text(record.get("record_id"))
        for record in records
        if _identity_state(record) == "accepted"
        and _text(record.get("record_id"))
        and _text(record.get("record_id")) not in duplicate_record_ids
    })
    if duplicate_record_ids:
        accepted_record_ids.extend(sorted(duplicate_record_ids))
        accepted_record_ids = sorted(set(accepted_record_ids))

    quality_blockers = rejected_records or blocked_records or duplicate_records or conflicting_records or ambiguous_records
    quality_report = {
        "schema_version": "v22.quality_report.v1",
        "snapshot_id": snapshot_id,
        "closure_gate_status": "blocked" if quality_blockers else "pass",
        "accepted_record_ids": accepted_record_ids,
        "rejected_records": rejected_records,
        "blocked_records": sorted(blocked_records, key=lambda item: item["record_id"]),
        "duplicate_records": sorted(duplicate_records, key=lambda item: (item["record_id"], item.get("candidate_id", ""))),
        "conflicting_records": sorted(conflicting_records, key=lambda item: (item.get("material_id", ""), item["record_id"])),
        "ambiguous_records": sorted(ambiguous_records, key=lambda item: item["record_id"]),
    }

    checks = [_leakage_check(records, dimension) for dimension in (
        "doi",
        "source_id",
        "material_id",
        "candidate_id",
        "group_id",
    )]
    zero_leakage_report = {
        "schema_version": "v22.zero_leakage_report.v1",
        "snapshot_id": snapshot_id,
        "closure_gate_status": "blocked" if any(check["status"] == "blocked" for check in checks) else "pass",
        "checks": checks,
    }
    return {
        "quality_report": quality_report,
        "zero_leakage_report": zero_leakage_report,
    }


def build_v22_independent_snapshot_report(
    production_snapshot: Mapping[str, Any],
    independent_snapshot: Mapping[str, Any],
    *,
    source_ledger: Mapping[str, Any],
    minimum_retained_records: int,
) -> dict[str, Any]:
    """Remove production overlaps from an independent snapshot report."""

    production_records = [
        record for record in production_snapshot.get("records", ())
        if isinstance(record, Mapping)
    ]
    independent_records = sorted(
        [
            record for record in independent_snapshot.get("records", ())
            if isinstance(record, Mapping)
        ],
        key=lambda item: _text(item.get("record_id")),
    )
    diagnostics = []
    if not _source_is_approved(_text(independent_snapshot.get("source_id")), source_ledger):
        diagnostics.append({
            "reason_code": "source_approval_missing",
            "message": "Independent snapshot source is absent from the approved source ledger.",
        })

    production_index = {
        dimension: _records_by_dimension(production_records, dimension)
        for dimension in ("doi", "source_id", "material_id", "candidate_id")
    }
    removed = []
    retained = []
    for record in independent_records:
        overlaps = []
        for dimension in ("doi", "source_id", "material_id", "candidate_id"):
            value = _text(record.get(dimension))
            production_ids = production_index[dimension].get(value, set()) if value else set()
            if production_ids:
                overlaps.append({
                    "record_id": _text(record.get("record_id")),
                    "dimension": dimension,
                    "value": value,
                    "production_record_ids": sorted(production_ids),
                })
        if overlaps:
            removed.extend(overlaps)
        else:
            retained.append(_text(record.get("record_id")))

    retained = sorted(record_id for record_id in retained if record_id)
    removed.sort(key=lambda item: (item["record_id"], item["dimension"], item["value"]))
    if len(retained) < minimum_retained_records:
        diagnostics.append({
            "reason_code": "independent_set_below_minimum",
            "message": "Retained independent records are below the declared minimum.",
        })
    return {
        "schema_version": "v22.independent_snapshot_report.v1",
        "production_snapshot_id": _text(production_snapshot.get("snapshot_id")) or "unknown-production",
        "independent_snapshot_id": _text(independent_snapshot.get("snapshot_id")) or "unknown-independent",
        "closure_gate_status": "blocked" if diagnostics else "pass",
        "external_validation_claimed": False,
        "retained_record_ids": retained,
        "removed_overlaps": removed,
        "diagnostics": sorted(diagnostics, key=lambda item: item["reason_code"]),
    }


def _target_key(target: Mapping[str, Any]) -> dict[str, Any]:
    key = (
        _text(target.get("material_id")),
        _text(target.get("use_instance_id")),
        _text(target.get("property_name")),
    )
    return {"key": key if all(key) else None, "record": target}


def _identity_state(record: Mapping[str, Any]) -> str:
    identity = record.get("identity", {})
    return _text(identity.get("identity_review_state")) if isinstance(identity, Mapping) else ""


def _source_is_approved(source_id: str, source_ledger: Mapping[str, Any]) -> bool:
    approved = {"licensed", "approved_public"}
    for source in source_ledger.get("sources", ()):
        if not isinstance(source, Mapping) or _text(source.get("source_id")) != source_id:
            continue
        license_info = source.get("license", {})
        return isinstance(license_info, Mapping) and _text(license_info.get("status")) in approved
    return False


def _records_by_dimension(records: Iterable[Mapping[str, Any]], dimension: str) -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for record in records:
        value = _text(record.get(dimension))
        record_id = _text(record.get("record_id"))
        if value and record_id:
            index.setdefault(value, set()).add(record_id)
    return index


def _report_item(record: Mapping[str, Any], reason_code: str) -> dict[str, Any]:
    item = {
        "record_id": _text(record.get("record_id")),
        "reason_code": reason_code,
    }
    for key in ("candidate_id", "material_id", "source_id"):
        value = _text(record.get(key))
        if value:
            item[key] = value
    return item


def _duplicate_values(records: Iterable[Mapping[str, Any]], field: str) -> set[str]:
    counts: dict[str, int] = {}
    for record in records:
        value = _text(record.get(field))
        if value:
            counts[value] = counts.get(value, 0) + 1
    return {value for value, count in counts.items() if count > 1}


def _conflicting_material_records(records: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    values: dict[tuple[str, str], set[float]] = {}
    members: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for record in records:
        material_id = _text(record.get("material_id"))
        for evidence in record.get("energy_evidence", []):
            if not isinstance(evidence, Mapping):
                continue
            property_name = _text(evidence.get("property_name"))
            value = evidence.get("value_ev")
            if not material_id or not property_name or not isinstance(value, (int, float)):
                continue
            key = (material_id, property_name)
            values.setdefault(key, set()).add(float(value))
            members.setdefault(key, []).append(record)
    conflicts = []
    for key, observed_values in values.items():
        if len(observed_values) <= 1:
            continue
        for record in members.get(key, []):
            item = _report_item(record, "conflicting_energy_value")
            item["material_id"] = key[0]
            item["property_name"] = key[1]
            conflicts.append(item)
    return conflicts


def _leakage_check(records: Iterable[Mapping[str, Any]], dimension: str) -> dict[str, Any]:
    by_value: dict[str, dict[str, set[str]]] = {}
    for record in records:
        value = _text(record.get(dimension))
        split = _text(record.get("group_id"))
        record_id = _text(record.get("record_id"))
        if not value or not split or not record_id:
            continue
        entry = by_value.setdefault(value, {"splits": set(), "record_ids": set()})
        entry["splits"].add(split)
        entry["record_ids"].add(record_id)
    overlaps = [
        {
            "value": value,
            "splits": sorted(entry["splits"]),
            "record_ids": sorted(entry["record_ids"]),
        }
        for value, entry in by_value.items()
        if len(entry["splits"]) > 1
    ]
    overlaps.sort(key=lambda item: item["value"])
    return {
        "dimension": dimension,
        "status": "blocked" if overlaps else "pass",
        "overlaps": overlaps,
    }


def _missing_policy_fields(fact: Mapping[str, Any]) -> list[str]:
    missing = []
    if _text(fact.get("unit")) != "eV":
        missing.append("unit_missing")
    if not _text(fact.get("method")):
        missing.append("method_missing")
    if _text(fact.get("reference_scale")) not in _REFERENCE_SCALES:
        missing.append("reference_scale_missing")
    if not _text(fact.get("curation_status")):
        missing.append("curation_status_missing")
    if not _text(fact.get("source_id")):
        missing.append("source_id_missing")
    if _text(fact.get("property_name")) not in _SUPPORTED_PROPERTIES:
        missing.append("property_not_supported")
    if not isinstance(fact.get("value_ev"), (int, float)):
        missing.append("value_ev_missing")
    return missing


def _cleared_blockers(records: Iterable[Mapping[str, Any]], blockers: Iterable[Mapping[str, Any]]) -> list[str]:
    admitted = {
        (
            _text(record.get("candidate_id")),
            _text(record.get("material_id")),
            _text(record.get("use_instance_id")),
            _text((record.get("energy_evidence") or [{}])[0].get("property_name")),
        )
        for record in records
    }
    cleared = []
    for blocker in blockers:
        key = (
            _text(blocker.get("candidate_id")),
            _text(blocker.get("material_id")),
            _text(blocker.get("use_instance_id")),
            _text(blocker.get("property_name")),
        )
        if _text(blocker.get("reason_code")) == "energy_levels_missing" and key in admitted:
            review_id = _text(blocker.get("review_item_id"))
            if review_id:
                cleared.append(review_id)
    return sorted(set(cleared))


def _diagnostic(
    reason_code: str,
    response: ProviderResponse,
    record_index: int,
    target: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    diagnostic = {
        "reason_code": reason_code,
        "message": "Provider energy fact is not admissible for V22 scientific evidence.",
        "provider_response_id": response.response_id,
        "record_index": record_index,
    }
    if target is not None:
        diagnostic["candidate_id"] = _text(target.get("candidate_id"))
    return diagnostic


def _prefixed_hash(value: str) -> str:
    return value if value.startswith("sha256:") else f"sha256:{value}"


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
