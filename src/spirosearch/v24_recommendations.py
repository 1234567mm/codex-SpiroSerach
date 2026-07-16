from __future__ import annotations

from typing import Any, Iterable, Mapping

from spirosearch.orchestrator_contracts import stable_hash


RECOMMENDATIONS_SCHEMA_VERSION = "v24.recommendations.v1"
EXPERIMENT_REQUESTS_SCHEMA_VERSION = "v24.experiment_requests.v1"
_INELIGIBLE_STATUSES = {"observed", "pending", "quarantine", "rejected"}


def build_v24_recommendation_artifacts(
    loop_state: Mapping[str, Any],
    candidates: Iterable[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    if loop_state.get("loop_status") != "admitted":
        return {
            "recommendations": _recommendations_payload(loop_state, [], status="blocked"),
            "experiment_requests": _requests_payload(loop_state, [], status="blocked"),
        }

    ranked = _rank_candidates(candidates)
    batch_size = int(loop_state.get("acquisition_policy", {}).get("batch_size", 1))
    max_experiments = int(loop_state.get("budget", {}).get("max_experiments", batch_size))
    selected = ranked[: max(0, min(batch_size, max_experiments))]
    recommendations = _recommendations_payload(loop_state, selected, status="ready")
    requests = _requests_payload(loop_state, selected, status="ready")
    return {"recommendations": recommendations, "experiment_requests": requests}


def _rank_candidates(candidates: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    eligible = []
    for candidate in candidates:
        candidate_id = _text(candidate.get("candidate_id"))
        if not candidate_id:
            continue
        if candidate_id in seen:
            raise ValueError(f"duplicate candidate_id selected for V24 round: {candidate_id}")
        seen.add(candidate_id)
        if _text(candidate.get("status")) in _INELIGIBLE_STATUSES:
            continue
        eligible.append(dict(candidate))
    return sorted(
        eligible,
        key=lambda item: (-float(item.get("acquisition_score", 0.0)), _text(item.get("candidate_id"))),
    )


def _recommendations_payload(loop_state: Mapping[str, Any], selected: list[dict[str, Any]], *, status: str) -> dict[str, Any]:
    items = []
    for rank, candidate in enumerate(selected, start=1):
        items.append({
            "rank": rank,
            "candidate_id": _text(candidate.get("candidate_id")),
            "material_id": _text(candidate.get("material_id")),
            "use_instance_id": _text(candidate.get("use_instance_id")),
            "candidate_version": _text(candidate.get("candidate_version")) or "unknown",
            "acquisition_score": float(candidate.get("acquisition_score", 0.0)),
            "estimated_cost": float(candidate.get("estimated_cost", 0.0)),
        })
    payload = {
        "schema_version": RECOMMENDATIONS_SCHEMA_VERSION,
        "status": status,
        "loop_state_id": _text(loop_state.get("loop_state_id")),
        "project_id": _text(loop_state.get("project_id")),
        "round_id": _text(loop_state.get("round_id")),
        "policy_id": _text(loop_state.get("acquisition_policy", {}).get("policy_id")),
        "items": items,
    }
    payload["recommendation_set_id"] = stable_hash(payload)[:16]
    return payload


def _requests_payload(loop_state: Mapping[str, Any], selected: list[dict[str, Any]], *, status: str) -> dict[str, Any]:
    budget = dict(loop_state.get("budget", {}))
    requests = []
    for item in _recommendations_payload(loop_state, selected, status=status)["items"]:
        request = {
            "request_id": stable_hash({
                "loop_state_id": loop_state.get("loop_state_id"),
                "candidate_id": item["candidate_id"],
                "rank": item["rank"],
            })[:16],
            "candidate_id": item["candidate_id"],
            "material_id": item["material_id"],
            "use_instance_id": item["use_instance_id"],
            "candidate_version": item["candidate_version"],
            "rank": item["rank"],
            "budget": {
                "currency": _text(budget.get("currency")) or "unknown",
                "estimated_cost": item["estimated_cost"],
                "max_cost": float(budget.get("max_cost", 0.0)),
            },
            "lineage": {
                "loop_state_id": _text(loop_state.get("loop_state_id")),
                "predecessor_run_id": _text(loop_state.get("predecessor_run", {}).get("run_id")),
                "training_snapshot_id": _text(loop_state.get("training_snapshot", {}).get("snapshot_id")),
                "model_version": _text(loop_state.get("model_evaluation", {}).get("model_version")),
                "policy_id": _text(loop_state.get("acquisition_policy", {}).get("policy_id")),
                "ledger_id": _text(loop_state.get("ledger", {}).get("ledger_id")),
            },
        }
        requests.append(request)
    payload = {
        "schema_version": EXPERIMENT_REQUESTS_SCHEMA_VERSION,
        "status": status,
        "loop_state_id": _text(loop_state.get("loop_state_id")),
        "project_id": _text(loop_state.get("project_id")),
        "round_id": _text(loop_state.get("round_id")),
        "requests": requests,
    }
    payload["request_set_id"] = stable_hash(payload)[:16]
    return payload


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
