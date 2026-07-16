from __future__ import annotations

from typing import Any, Mapping

from spirosearch.orchestrator_contracts import stable_hash


OBSERVATION_PROJECTION_SCHEMA_VERSION = "v24.observation_projection.v1"


def build_v24_observation_projection(observation_import: Mapping[str, Any]) -> dict[str, Any]:
    evidence_candidates = []
    review_items = []
    for observation in observation_import.get("accepted_observations", ()):
        if not isinstance(observation, Mapping):
            continue
        evidence = _evidence_candidate(observation)
        evidence_candidates.append(evidence)
        review_reason = _accepted_observation_review_reason(observation)
        if review_reason:
            review_items.append(_review_item(observation, review_reason))
    for rejected in observation_import.get("rejected_observations", ()):
        if isinstance(rejected, Mapping):
            review_items.append(_review_item(rejected, _text(rejected.get("reason_code")) or "observation_rejected"))
    payload = {
        "schema_version": OBSERVATION_PROJECTION_SCHEMA_VERSION,
        "import_id": _text(observation_import.get("import_id")),
        "request_set_id": _text(observation_import.get("request_set_id")),
        "projection_status": "needs_review" if review_items or evidence_candidates else "empty",
        "evidence_candidates": sorted(evidence_candidates, key=lambda item: item["evidence_id"]),
        "review_items": sorted(review_items, key=lambda item: item["review_item_id"]),
        "scoring_updates": [],
    }
    payload["projection_id"] = stable_hash({
        "import_id": payload["import_id"],
        "evidence_ids": [item["evidence_id"] for item in payload["evidence_candidates"]],
        "review_ids": [item["review_item_id"] for item in payload["review_items"]],
    })[:16]
    return payload


def _evidence_candidate(observation: Mapping[str, Any]) -> dict[str, Any]:
    request_id = _text(observation.get("request_id"))
    candidate_id = _text(observation.get("candidate_id"))
    provenance = observation.get("provenance", {}) if isinstance(observation.get("provenance"), Mapping) else {}
    lineage = observation.get("lineage", {}) if isinstance(observation.get("lineage"), Mapping) else {}
    metrics = dict(observation.get("metrics", {})) if isinstance(observation.get("metrics"), Mapping) else {}
    evidence = {
        "evidence_id": stable_hash({"request_id": request_id, "candidate_id": candidate_id, "metrics": metrics})[:16],
        "request_id": request_id,
        "candidate_id": candidate_id,
        "metrics": metrics,
        "curation_status": "needs_review",
        "eligible_for_scoring": False,
        "lineage": {
            "request_id": request_id,
            "request_set_id": _text(lineage.get("request_set_id")),
            "loop_state_id": _text(lineage.get("loop_state_id")),
            "model_version": _text(lineage.get("model_version")),
            "observer_id": _text(provenance.get("observer_id")),
            "observed_at": _text(provenance.get("observed_at")),
            "source_uri": _text(provenance.get("source_uri")),
        },
    }
    return evidence


def _accepted_observation_review_reason(observation: Mapping[str, Any]) -> str:
    metrics = observation.get("metrics", {})
    provenance = observation.get("provenance", {})
    if not isinstance(metrics, Mapping) or "pce" not in metrics:
        return "observation_metrics_incomplete"
    if not isinstance(provenance, Mapping) or not _text(provenance.get("source_uri")):
        return "observation_provenance_incomplete"
    return "observation_requires_curation"


def _review_item(observation: Mapping[str, Any], reason_code: str) -> dict[str, Any]:
    request_id = _text(observation.get("request_id"))
    item = {
        "review_item_id": stable_hash({"request_id": request_id, "reason_code": reason_code})[:16],
        "request_id": request_id,
        "candidate_id": _text(observation.get("candidate_id")),
        "reason_code": reason_code,
        "severity": "medium",
        "assigned_queue": "observation_review",
        "blocking_surface": "scoring",
        "resolution_status": "open",
    }
    return item


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
