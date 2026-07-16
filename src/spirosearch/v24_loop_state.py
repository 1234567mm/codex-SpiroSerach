from __future__ import annotations

from typing import Any, Mapping

from spirosearch.orchestrator_contracts import stable_hash


LOOP_STATE_SCHEMA_VERSION = "v24.loop_state.v1"


def build_v24_loop_state(
    *,
    project_id: str,
    round_id: str,
    predecessor_run: Mapping[str, Any],
    candidate_pool: Mapping[str, Any],
    training_snapshot: Mapping[str, Any],
    model_evaluation: Mapping[str, Any],
    acquisition_policy: Mapping[str, Any],
    budget: Mapping[str, Any],
    ledger: Mapping[str, Any],
    admission_report: Mapping[str, Any],
) -> dict[str, Any]:
    _require_reference("predecessor_run", predecessor_run, ("run_id", "input_hash"))
    _require_reference("candidate_pool", candidate_pool, ("artifact_kind", "snapshot_id"))
    _require_reference("training_snapshot", training_snapshot, ("artifact_kind", "snapshot_id"))
    _require_reference("model_evaluation", model_evaluation, ("artifact_kind", "model_version"))
    _require_reference("acquisition_policy", acquisition_policy, ("policy_id", "strategy"))
    _require_reference("budget", budget, ("max_experiments",))
    _require_reference("ledger", ledger, ("artifact_kind", "ledger_id"))
    _require_reference("admission_report", admission_report, ("admission_id", "admission_status"))

    loop_status = "admitted" if admission_report.get("admission_status") == "pass" else "blocked"
    payload = {
        "schema_version": LOOP_STATE_SCHEMA_VERSION,
        "project_id": str(project_id),
        "round_id": str(round_id),
        "loop_status": loop_status,
        "predecessor_run": dict(predecessor_run),
        "candidate_pool": dict(candidate_pool),
        "training_snapshot": dict(training_snapshot),
        "model_evaluation": dict(model_evaluation),
        "acquisition_policy": dict(acquisition_policy),
        "budget": dict(budget),
        "ledger": dict(ledger),
        "admission": {
            "admission_id": str(admission_report.get("admission_id", "")),
            "admission_status": str(admission_report.get("admission_status", "")),
            "reason_codes": list(admission_report.get("reason_codes", ())),
        },
    }
    payload["loop_state_id"] = stable_hash(payload)[:16]
    return payload


def _require_reference(name: str, value: Mapping[str, Any], keys: tuple[str, ...]) -> None:
    missing = [key for key in keys if value.get(key) in (None, "")]
    if missing:
        raise ValueError(f"{name} missing required reference fields: {', '.join(missing)}")
