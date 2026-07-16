from __future__ import annotations

from typing import Any, Iterable, Mapping

from spirosearch.orchestrator_contracts import stable_hash


LOOP_CONTROLS_SCHEMA_VERSION = "v24.loop_controls_report.v1"


def build_v24_loop_controls_report(
    loop_state: Mapping[str, Any],
    recommendations: Mapping[str, Any],
    experiment_requests: Mapping[str, Any],
    *,
    current_model_version: str,
    current_admission_id: str,
    observations: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    checks = [
        _budget_check(loop_state, experiment_requests),
        _duplicate_check(experiment_requests),
        _stale_model_check(experiment_requests, current_model_version),
        _stale_admission_check(loop_state, current_admission_id),
        _leakage_check(experiment_requests, observations),
    ]
    reason_codes = sorted({
        reason
        for check in checks
        for reason in check["reason_codes"]
        if reason
    })
    payload = {
        "schema_version": LOOP_CONTROLS_SCHEMA_VERSION,
        "loop_state_id": _text(loop_state.get("loop_state_id")),
        "recommendation_set_id": _text(recommendations.get("recommendation_set_id")),
        "request_set_id": _text(experiment_requests.get("request_set_id")),
        "control_status": "blocked" if reason_codes else "pass",
        "request_generation_allowed": not reason_codes,
        "reason_codes": reason_codes,
        "replay_hash": stable_hash({
            "loop_state": loop_state,
            "recommendations": recommendations,
            "experiment_requests": experiment_requests,
        }),
        "checks": checks,
    }
    payload["control_report_id"] = stable_hash(payload)[:16]
    return payload


def _budget_check(loop_state: Mapping[str, Any], experiment_requests: Mapping[str, Any]) -> dict[str, Any]:
    budget = loop_state.get("budget", {}) if isinstance(loop_state.get("budget"), Mapping) else {}
    max_cost = float(budget.get("max_cost", 0.0))
    max_experiments = int(budget.get("max_experiments", 0))
    requests = _requests(experiment_requests)
    total_cost = sum(float(item.get("budget", {}).get("estimated_cost", 0.0)) for item in requests)
    reasons = []
    if max_cost and total_cost > max_cost:
        reasons.append("budget_overrun")
    if max_experiments and len(requests) > max_experiments:
        reasons.append("experiment_count_overrun")
    return {"name": "budget", "status": "blocked" if reasons else "pass", "reason_codes": reasons}


def _duplicate_check(experiment_requests: Mapping[str, Any]) -> dict[str, Any]:
    seen = set()
    duplicate = False
    for item in _requests(experiment_requests):
        candidate_id = _text(item.get("candidate_id"))
        if candidate_id in seen:
            duplicate = True
        seen.add(candidate_id)
    reasons = ["duplicate_candidate_request"] if duplicate else []
    return {"name": "duplicates", "status": "blocked" if reasons else "pass", "reason_codes": reasons}


def _stale_model_check(experiment_requests: Mapping[str, Any], current_model_version: str) -> dict[str, Any]:
    reasons = []
    for item in _requests(experiment_requests):
        model_version = _text(item.get("lineage", {}).get("model_version"))
        if model_version and model_version != current_model_version:
            reasons.append("stale_model_version")
            break
    return {"name": "stale_model", "status": "blocked" if reasons else "pass", "reason_codes": reasons}


def _stale_admission_check(loop_state: Mapping[str, Any], current_admission_id: str) -> dict[str, Any]:
    admission_id = _text(loop_state.get("admission", {}).get("admission_id"))
    reasons = ["stale_admission_report"] if admission_id and admission_id != current_admission_id else []
    return {"name": "stale_admission", "status": "blocked" if reasons else "pass", "reason_codes": reasons}


def _leakage_check(experiment_requests: Mapping[str, Any], observations: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    request_ids = {_text(item.get("request_id")) for item in _requests(experiment_requests)}
    leaked = any(
        isinstance(item, Mapping)
        and _text(item.get("request_id")) in request_ids
        and _text(item.get("observed_at"))
        for item in observations
    )
    reasons = ["future_observation_leakage"] if leaked else []
    return {"name": "leakage", "status": "blocked" if reasons else "pass", "reason_codes": reasons}


def _requests(experiment_requests: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [item for item in experiment_requests.get("requests", ()) if isinstance(item, Mapping)]


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
