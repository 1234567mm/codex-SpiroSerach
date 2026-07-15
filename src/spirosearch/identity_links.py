from __future__ import annotations

import hashlib
from typing import Any, Iterable, Mapping


IDENTITY_LINK_PROPOSAL_SCHEMA_VERSION = "v21.identity_link_proposals.v1"
IDENTITY_REVIEW_DIAGNOSTICS_SCHEMA_VERSION = "v21.identity_review_diagnostics.v1"
CANDIDATE_IDENTITY_PROJECTION_SCHEMA_VERSION = "v21.candidate_identity_projection.v1"
IDENTITY_HISTORY_DELTA_SCHEMA_VERSION = "v21.identity_history_delta.v1"


def normalize_doi(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
            break
    return normalized.strip() or None


def normalize_inchikey(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().upper()
    return normalized or None


def build_candidate_evidence_link_proposals(
    registry: Mapping[str, Any],
    evidence_records: Iterable[Mapping[str, Any]],
    *,
    source_run_id: str,
) -> dict[str, Any]:
    identity_index = _identity_index(registry)
    proposals: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []

    for evidence in sorted(evidence_records, key=_evidence_sort_key):
        evidence_id = str(evidence.get("evidence_id", ""))
        bases = _proposal_bases(evidence)
        if not bases:
            diagnostics.append(_diagnostic(evidence_id, "candidate_identity_basis_missing"))
            continue

        candidate_matches = _candidate_matches(identity_index, bases)
        if len(candidate_matches) == 0:
            diagnostics.append(_diagnostic(evidence_id, "candidate_identity_not_found"))
            continue
        if len(candidate_matches) > 1:
            diagnostics.append(_diagnostic(evidence_id, "ambiguous_candidate_identity"))
            continue

        candidate = candidate_matches[0]
        proposals.append(_proposal_link(candidate, evidence, bases, source_run_id=source_run_id))

    proposals.sort(key=lambda link: (str(link["evidence_id"]), str(link["candidate_id"]), str(link["link_id"])))
    diagnostics.sort(key=lambda item: (str(item["evidence_id"]), str(item["reason_code"])))
    return {
        "schema_version": IDENTITY_LINK_PROPOSAL_SCHEMA_VERSION,
        "proposals": proposals,
        "diagnostics": diagnostics,
    }


def build_identity_review_diagnostics(
    registry: Mapping[str, Any],
    link_records: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    links = [dict(link) for link in link_records]
    accepted_conflict_keys = _accepted_conflict_keys(links)
    displayable_links: list[dict[str, Any]] = []
    link_diagnostics: list[dict[str, Any]] = []

    for link in sorted(links, key=_link_sort_key):
        state = str(link.get("reviewer_state", ""))
        conflict_key = _accepted_conflict_key(link)
        if state == "accepted" and conflict_key not in accepted_conflict_keys:
            displayable_links.append(dict(link))
            continue
        reason_code = (
            "conflicting_accepted_identity_link"
            if state == "accepted" and conflict_key in accepted_conflict_keys
            else f"identity_link_{state or 'unknown'}"
        )
        link_diagnostics.append(
            {
                "link_id": str(link.get("link_id", "")),
                "candidate_id": str(link.get("candidate_id", "")),
                "evidence_id": str(link.get("evidence_id", "")),
                "reviewer_state": state or "unknown",
                "reason_codes": [reason_code],
                "blocking_review_ids": _string_list(link.get("blocking_review_ids", [])),
            }
        )

    candidate_diagnostics = [_candidate_diagnostic(record) for record in registry.get("records", []) if isinstance(record, Mapping)]
    candidate_diagnostics.sort(key=lambda item: str(item["candidate_id"]))
    link_diagnostics.sort(key=lambda item: (str(item["link_id"]), str(item["evidence_id"])))
    displayable_links.sort(key=_link_sort_key)
    return {
        "schema_version": IDENTITY_REVIEW_DIAGNOSTICS_SCHEMA_VERSION,
        "candidate_diagnostics": candidate_diagnostics,
        "link_diagnostics": link_diagnostics,
        "displayable_links": displayable_links,
    }


def build_candidate_identity_projection(
    registry: Mapping[str, Any],
    link_records: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    diagnostics = build_identity_review_diagnostics(registry, link_records)
    diagnostics_by_candidate = {
        item["candidate_id"]: item
        for item in diagnostics["candidate_diagnostics"]
    }
    accepted_links_by_candidate: dict[str, list[dict[str, Any]]] = {}
    for link in diagnostics["displayable_links"]:
        accepted_links_by_candidate.setdefault(str(link.get("candidate_id", "")), []).append(dict(link))

    candidates: list[dict[str, Any]] = []
    for record in sorted(
        (record for record in registry.get("records", []) if isinstance(record, Mapping)),
        key=lambda item: str(item.get("candidate_id", "")),
    ):
        candidate_id = str(record.get("candidate_id", ""))
        accepted_links = accepted_links_by_candidate.get(candidate_id, [])
        accepted_links.sort(key=_link_sort_key)
        candidate_diagnostics = diagnostics_by_candidate.get(candidate_id, {})
        candidates.append(
            {
                "candidate_id": candidate_id,
                "stable_identity_id": str(record.get("stable_identity_id", "")),
                "accepted_links": accepted_links,
                "identity_diagnostics": {
                    "reviewer_state": candidate_diagnostics.get("reviewer_state", "unknown"),
                    "reason_codes": list(candidate_diagnostics.get("reason_codes", [])),
                    "blocking_review_ids": list(candidate_diagnostics.get("blocking_review_ids", [])),
                },
                "identity_history": [dict(event) for event in record.get("identity_history", []) if isinstance(event, Mapping)],
            }
        )
    return {
        "schema_version": CANDIDATE_IDENTITY_PROJECTION_SCHEMA_VERSION,
        "candidates": candidates,
        "link_diagnostics": diagnostics["link_diagnostics"],
        "scoring_impact": {
            "status": "unchanged",
            "eligible_for_scoring_changed": False,
            "reason": "identity links are read-plane diagnostics only",
        },
    }


def build_identity_history_delta(
    source_registry: Mapping[str, Any],
    target_registry: Mapping[str, Any],
    source_links: Iterable[Mapping[str, Any]],
    target_links: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    source_event_ids = _identity_event_ids(source_registry)
    identity_events_added = [
        dict(event)
        for event in _identity_events(target_registry)
        if str(event.get("event_id", "")) not in source_event_ids
    ]
    identity_events_added.sort(key=lambda event: str(event.get("event_id", "")))

    source_link_ids = {str(link.get("link_id", "")) for link in source_links}
    target_link_ids = {str(link.get("link_id", "")) for link in target_links}
    return {
        "schema_version": IDENTITY_HISTORY_DELTA_SCHEMA_VERSION,
        "identity_events_added": identity_events_added,
        "link_changes": {
            "added": sorted(target_link_ids - source_link_ids),
            "removed": sorted(source_link_ids - target_link_ids),
        },
        "mutation_policy": "old_runs_immutable",
    }


def _identity_index(registry: Mapping[str, Any]) -> dict[tuple[str, str], list[Mapping[str, Any]]]:
    index: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for record in registry.get("records", []):
        if not isinstance(record, Mapping):
            continue
        for source_identity in record.get("source_identities", []):
            if not isinstance(source_identity, Mapping):
                continue
            basis = source_identity.get("basis")
            normalized = source_identity.get("normalized_value")
            if isinstance(basis, str) and isinstance(normalized, str) and normalized:
                index.setdefault((basis, normalized), []).append(record)
        for material_id in record.get("material_ids", []):
            if isinstance(material_id, str) and material_id:
                index.setdefault(("material_id", material_id), []).append(record)
        for use_instance_id in record.get("use_instance_ids", []):
            if isinstance(use_instance_id, str) and use_instance_id:
                index.setdefault(("use_instance_id", use_instance_id), []).append(record)
    return index


def _candidate_diagnostic(record: Mapping[str, Any]) -> dict[str, Any]:
    state = str(record.get("reviewer_state", ""))
    reason_codes = [] if state == "accepted" else [f"identity_state_{state or 'unknown'}"]
    return {
        "candidate_id": str(record.get("candidate_id", "")),
        "stable_identity_id": str(record.get("stable_identity_id", "")),
        "reviewer_state": state or "unknown",
        "reason_codes": reason_codes,
        "blocking_review_ids": _string_list(record.get("blocking_review_ids", [])),
        "identity_history": [dict(event) for event in record.get("identity_history", []) if isinstance(event, Mapping)],
    }


def _identity_events(registry: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    events: list[Mapping[str, Any]] = []
    for record in registry.get("records", []):
        if not isinstance(record, Mapping):
            continue
        for event in record.get("identity_history", []):
            if isinstance(event, Mapping):
                events.append(event)
    return events


def _identity_event_ids(registry: Mapping[str, Any]) -> set[str]:
    return {str(event.get("event_id", "")) for event in _identity_events(registry)}


def _accepted_conflict_keys(links: list[Mapping[str, Any]]) -> set[tuple[str, str]]:
    accepted_counts: dict[tuple[str, str], int] = {}
    for link in links:
        if link.get("reviewer_state") != "accepted":
            continue
        key = _accepted_conflict_key(link)
        accepted_counts[key] = accepted_counts.get(key, 0) + 1
    return {key for key, count in accepted_counts.items() if count > 1}


def _accepted_conflict_key(link: Mapping[str, Any]) -> tuple[str, str]:
    return (str(link.get("candidate_id", "")), str(link.get("evidence_id", "")))


def _link_sort_key(link: Mapping[str, Any]) -> tuple[str, str, str]:
    return (str(link.get("candidate_id", "")), str(link.get("evidence_id", "")), str(link.get("link_id", "")))


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _proposal_bases(evidence: Mapping[str, Any]) -> list[dict[str, str]]:
    identifiers = evidence.get("identifiers", {})
    identifiers = identifiers if isinstance(identifiers, Mapping) else {}
    bases: list[dict[str, str]] = []

    doi = normalize_doi(_optional_string(identifiers.get("doi")) or _paper_doi(evidence))
    if doi is not None:
        bases.append({"basis_type": "doi", "value": str(identifiers.get("doi") or _paper_doi(evidence)), "normalized_value": doi})

    inchikey = normalize_inchikey(_optional_string(identifiers.get("inchikey")))
    if inchikey is not None:
        bases.append({"basis_type": "inchikey", "value": str(identifiers.get("inchikey")), "normalized_value": inchikey})

    material_id = _optional_string(identifiers.get("material_id"))
    if material_id is not None:
        bases.append({"basis_type": "material_id", "value": material_id, "normalized_value": material_id})

    use_instance_id = _optional_string(identifiers.get("use_instance_id"))
    if use_instance_id is not None:
        bases.append({"basis_type": "use_instance_id", "value": use_instance_id, "normalized_value": use_instance_id})

    return bases


def _candidate_matches(
    identity_index: Mapping[tuple[str, str], list[Mapping[str, Any]]],
    bases: Iterable[Mapping[str, str]],
) -> list[Mapping[str, Any]]:
    by_candidate: dict[str, Mapping[str, Any]] = {}
    for basis in bases:
        basis_type = str(basis.get("basis_type", ""))
        normalized = str(basis.get("normalized_value", ""))
        for candidate in identity_index.get((basis_type, normalized), []):
            candidate_id = candidate.get("candidate_id")
            if isinstance(candidate_id, str):
                by_candidate[candidate_id] = candidate
    return [by_candidate[key] for key in sorted(by_candidate)]


def _proposal_link(
    candidate: Mapping[str, Any],
    evidence: Mapping[str, Any],
    bases: list[dict[str, str]],
    *,
    source_run_id: str,
) -> dict[str, Any]:
    evidence_id = str(evidence.get("evidence_id"))
    candidate_id = str(candidate.get("candidate_id"))
    link_basis = [dict(basis) for basis in bases]
    link_id = _link_id(candidate_id, evidence_id, link_basis)
    return {
        "schema_version": "v21.candidate_evidence_link.v1",
        "link_id": link_id,
        "candidate_id": candidate_id,
        "stable_identity_id": str(candidate.get("stable_identity_id")),
        "evidence_id": evidence_id,
        "evidence_kind": str(evidence.get("evidence_kind", "literature_claim")),
        "paper": _paper_ref(evidence),
        "link_basis": link_basis,
        "confidence_category": "deterministic_proposal",
        "reviewer_state": "proposed",
        "blocking_review_ids": [],
        "lineage": {
            "source_run_id": source_run_id,
            "source_artifact_kinds": ["candidate_identity_registry", "literature_claims"],
            "generated_by": "v21_identity_link_proposal_builder",
        },
    }


def _paper_ref(evidence: Mapping[str, Any]) -> dict[str, str | None]:
    paper = evidence.get("paper", {})
    paper = paper if isinstance(paper, Mapping) else {}
    return {
        "doi": normalize_doi(_optional_string(paper.get("doi"))),
        "source_id": _optional_string(paper.get("source_id")) or "unknown-paper-source",
        "asset_id": _optional_string(paper.get("asset_id")),
        "chunk_id": _optional_string(paper.get("chunk_id")),
    }


def _diagnostic(evidence_id: str, reason_code: str) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "reason_code": reason_code,
        "reviewer_state": "blocked",
        "blocking_review_ids": [],
    }


def _link_id(candidate_id: str, evidence_id: str, bases: Iterable[Mapping[str, str]]) -> str:
    digest = hashlib.sha256()
    digest.update(candidate_id.encode("utf-8"))
    digest.update(b"\0")
    digest.update(evidence_id.encode("utf-8"))
    for basis in sorted(bases, key=lambda item: (item["basis_type"], item["normalized_value"])):
        digest.update(b"\0")
        digest.update(basis["basis_type"].encode("utf-8"))
        digest.update(b"=")
        digest.update(basis["normalized_value"].encode("utf-8"))
    return f"link-proposal-{digest.hexdigest()[:16]}"


def _evidence_sort_key(evidence: Mapping[str, Any]) -> tuple[str, str]:
    return (str(evidence.get("evidence_id", "")), str(evidence.get("evidence_kind", "")))


def _paper_doi(evidence: Mapping[str, Any]) -> str | None:
    paper = evidence.get("paper", {})
    if not isinstance(paper, Mapping):
        return None
    return _optional_string(paper.get("doi"))


def _optional_string(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None
