from __future__ import annotations

from typing import Any, Mapping

from spirosearch.orchestrator_contracts import stable_hash


PROJECT_EVOLUTION_SCHEMA_VERSION = "v24.project_evolution.v1"


def build_v24_project_evolution(
    *,
    loop_state: Mapping[str, Any] | None,
    recommendations: Mapping[str, Any] | None,
    experiment_requests: Mapping[str, Any] | None,
    observation_import: Mapping[str, Any] | None,
    controls_report: Mapping[str, Any] | None,
) -> dict[str, Any]:
    diagnostics = []
    if not loop_state:
        diagnostics.append("loop_state_missing")
    if not recommendations:
        diagnostics.append("recommendations_missing")
    if not experiment_requests:
        diagnostics.append("experiment_requests_missing")
    if not observation_import:
        diagnostics.append("observation_import_missing")
    if not controls_report:
        diagnostics.append("controls_report_missing")
    payload = {
        "schema_version": PROJECT_EVOLUTION_SCHEMA_VERSION,
        "view_status": "degraded" if diagnostics else "available",
        "loop_state_id": _text((loop_state or {}).get("loop_state_id")),
        "round_id": _text((loop_state or {}).get("round_id")),
        "round_efficiency": {
            "recommended_count": len((recommendations or {}).get("items", ())),
            "requested_count": len((experiment_requests or {}).get("requests", ())),
            "accepted_observation_count": len((observation_import or {}).get("accepted_observations", ())),
            "rejected_observation_count": len((observation_import or {}).get("rejected_observations", ())),
        },
        "decisions": {
            "loop_status": _text((loop_state or {}).get("loop_status")),
            "control_status": _text((controls_report or {}).get("control_status")),
            "requested_count": len((experiment_requests or {}).get("requests", ())),
        },
        "model_state_change": {
            "loop_state_id": _text((loop_state or {}).get("loop_state_id")),
            "model_version": _text((loop_state or {}).get("model_evaluation", {}).get("model_version")),
        },
        "diagnostics": diagnostics,
    }
    payload["project_evolution_id"] = stable_hash(payload)[:16]
    return payload


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
