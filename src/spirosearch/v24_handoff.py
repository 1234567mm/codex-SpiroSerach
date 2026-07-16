from __future__ import annotations

from typing import Any, Iterable, Mapping

from spirosearch.orchestrator_contracts import stable_hash


HANDOFF_SCHEMA_VERSION = "v24.handoff_export.v1"
OBSERVATION_IMPORT_SCHEMA_VERSION = "v24.observation_import.v1"


def build_v24_handoff_export(
    experiment_requests: Mapping[str, Any],
    *,
    approval: Mapping[str, Any],
) -> dict[str, Any]:
    _require_approval(approval)
    requests = [dict(item) for item in experiment_requests.get("requests", ()) if isinstance(item, Mapping)]
    payload = {
        "schema_version": HANDOFF_SCHEMA_VERSION,
        "export_status": "approved_for_handoff",
        "request_set_id": _text(experiment_requests.get("request_set_id")),
        "loop_state_id": _text(experiment_requests.get("loop_state_id")),
        "project_id": _text(experiment_requests.get("project_id")),
        "round_id": _text(experiment_requests.get("round_id")),
        "approval": {
            "approver_id": _text(approval.get("approver_id")),
            "approved_at": _text(approval.get("approved_at")),
            "reason": _text(approval.get("reason")),
        },
        "requests": requests,
    }
    payload["handoff_id"] = stable_hash(payload)[:16]
    return payload


def validate_v24_observation_import(
    experiment_requests: Mapping[str, Any],
    *,
    observations: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    requests_by_id = {
        _text(item.get("request_id")): item
        for item in experiment_requests.get("requests", ())
        if isinstance(item, Mapping) and _text(item.get("request_id"))
    }
    accepted = []
    rejected = []
    for observation in observations:
        item = dict(observation)
        reason = _observation_rejection_reason(item, requests_by_id)
        if reason:
            rejected.append({"request_id": _text(item.get("request_id")), "reason_code": reason})
            continue
        request = requests_by_id[_text(item.get("request_id"))]
        accepted.append({
            "request_id": _text(item.get("request_id")),
            "candidate_id": _text(item.get("candidate_id")),
            "metrics": dict(item.get("metrics", {})),
            "provenance": dict(item.get("provenance", {})),
            "lineage": {
                "request_set_id": _text(experiment_requests.get("request_set_id")),
                "loop_state_id": _text(experiment_requests.get("loop_state_id")),
                "model_version": _text(request.get("lineage", {}).get("model_version")),
            },
        })
    payload = {
        "schema_version": OBSERVATION_IMPORT_SCHEMA_VERSION,
        "import_id": "",
        "request_set_id": _text(experiment_requests.get("request_set_id")),
        "status": "invalid" if rejected else "valid",
        "accepted_observations": accepted,
        "rejected_observations": rejected,
        "posterior_updates": [],
        "evidence_updates": [],
    }
    payload["import_id"] = stable_hash(payload)[:16]
    return payload


def _require_approval(approval: Mapping[str, Any]) -> None:
    missing = [key for key in ("approver_id", "approved_at", "reason") if not _text(approval.get(key))]
    if missing:
        raise ValueError(f"approval missing required fields: {', '.join(missing)}")


def _observation_rejection_reason(item: Mapping[str, Any], requests_by_id: Mapping[str, Mapping[str, Any]]) -> str:
    request_id = _text(item.get("request_id"))
    if request_id not in requests_by_id:
        return "request_not_found"
    request = requests_by_id[request_id]
    if _text(item.get("candidate_id")) != _text(request.get("candidate_id")):
        return "candidate_identity_mismatch"
    metrics = item.get("metrics")
    if not isinstance(metrics, Mapping) or not metrics:
        return "metrics_missing"
    provenance = item.get("provenance")
    if not isinstance(provenance, Mapping) or not _text(provenance.get("observer_id")):
        return "provenance_missing"
    return ""


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
