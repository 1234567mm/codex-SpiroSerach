from __future__ import annotations

from typing import Any, Mapping

from spirosearch.orchestrator_contracts import stable_hash


STOP_CONTINUE_SCHEMA_VERSION = "v24.stop_continue_report.v1"


def build_v24_stop_continue_report(
    *,
    admission_report: Mapping[str, Any],
    controls_report: Mapping[str, Any],
    project_evolution: Mapping[str, Any],
    minimum_accepted_observations: int = 1,
) -> dict[str, Any]:
    reasons = []
    if admission_report.get("admission_status") != "pass":
        reasons.append("scientific_gate_blocked")
    if controls_report.get("control_status") != "pass":
        reasons.append("loop_controls_blocked")
    accepted_count = int(project_evolution.get("round_efficiency", {}).get("accepted_observation_count", 0))
    if accepted_count < minimum_accepted_observations:
        reasons.append("insufficient_discovery_efficiency")
    payload = {
        "schema_version": STOP_CONTINUE_SCHEMA_VERSION,
        "decision": "stop" if reasons else "continue",
        "reason_codes": sorted(set(reasons)),
        "decision_basis": {
            "admission_status": str(admission_report.get("admission_status", "")),
            "admission_reasons": list(admission_report.get("reason_codes", ())),
            "control_status": str(controls_report.get("control_status", "")),
            "control_reasons": list(controls_report.get("reason_codes", ())),
            "accepted_observation_count": accepted_count,
            "minimum_accepted_observations": minimum_accepted_observations,
        },
        "claims": {
            "scientific_success_claimed": False,
            "autonomous_dispatch_claimed": False,
        },
    }
    payload["stop_continue_id"] = stable_hash(payload)[:16]
    return payload
