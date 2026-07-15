from __future__ import annotations

import hashlib
from typing import Any, Iterable, Mapping


IDENTITY_LINK_PROPOSAL_SCHEMA_VERSION = "v21.identity_link_proposals.v1"


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
