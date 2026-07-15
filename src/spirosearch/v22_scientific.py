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


def _target_key(target: Mapping[str, Any]) -> dict[str, Any]:
    key = (
        _text(target.get("material_id")),
        _text(target.get("use_instance_id")),
        _text(target.get("property_name")),
    )
    return {"key": key if all(key) else None, "record": target}


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
