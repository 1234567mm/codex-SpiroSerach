from __future__ import annotations

from typing import Any, Iterable, Mapping

from spirosearch.orchestrator_contracts import stable_hash


ADMISSION_SCHEMA_VERSION = "v24.admission_report.v1"
_REQUIRED_SOURCE_KINDS = (
    "v22_scientific_closure_report",
    "v22_model_activation_report",
    "v23_action_results",
)


def build_v24_admission_report(
    *,
    scientific_closure_report: Mapping[str, Any],
    model_activation_report: Mapping[str, Any],
    command_results: Iterable[Mapping[str, Any]] = (),
    command_audit_events: Iterable[Mapping[str, Any]] = (),
    manifest_artifacts: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    artifacts_by_kind = {
        _text(artifact.get("kind")): artifact
        for artifact in manifest_artifacts
        if isinstance(artifact, Mapping) and _text(artifact.get("kind"))
    }
    command_facts = _command_facts(command_results, command_audit_events)
    checks = [
        _scientific_closure_check(scientific_closure_report),
        _model_activation_check(model_activation_report),
        _source_artifact_check(artifacts_by_kind),
    ]
    reason_codes = sorted({
        reason
        for check in checks
        for reason in check["reason_codes"]
        if reason
    })
    report = {
        "schema_version": ADMISSION_SCHEMA_VERSION,
        "admission_status": "blocked" if reason_codes else "pass",
        "source_run_id": _text(scientific_closure_report.get("closure_id")),
        "model_version": _text(model_activation_report.get("model_version")),
        "reason_codes": reason_codes,
        "checks": checks,
        "source_artifacts": _source_artifacts(artifacts_by_kind),
        "command_facts": command_facts,
    }
    report["admission_id"] = stable_hash({
        "source_run_id": report["source_run_id"],
        "model_version": report["model_version"],
        "reason_codes": report["reason_codes"],
        "command_facts": report["command_facts"],
    })[:16]
    return report


def _scientific_closure_check(report: Mapping[str, Any]) -> dict[str, Any]:
    reasons = []
    if _text(report.get("closure_gate_status")) != "pass":
        reasons.append("v22_scientific_closure_blocked")
    if _text(report.get("downstream_impact")) == "models_disabled_for_v24_admission":
        reasons.append("models_disabled_for_v24_admission")
    return {
        "name": "v22_scientific_closure",
        "status": "blocked" if reasons else "pass",
        "reason_codes": sorted(reasons),
    }


def _model_activation_check(report: Mapping[str, Any]) -> dict[str, Any]:
    reasons = []
    disabled = report.get("disabled_model_state", {})
    may_rank = isinstance(disabled, Mapping) and disabled.get("may_rank_candidates") is True
    if _text(report.get("activation_status")) != "eligible" or not may_rank:
        reasons.append("v22_model_activation_disabled")
    reasons.extend(
        _text(reason)
        for reason in report.get("activation_reasons", ())
        if _text(reason)
    )
    return {
        "name": "v22_model_activation",
        "status": "blocked" if reasons else "pass",
        "reason_codes": sorted(set(reasons)),
    }


def _source_artifact_check(artifacts_by_kind: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    reasons = [
        f"source_artifact_missing:{kind}"
        for kind in _REQUIRED_SOURCE_KINDS
        if kind not in artifacts_by_kind
    ]
    return {
        "name": "source_artifacts",
        "status": "blocked" if reasons else "pass",
        "reason_codes": reasons,
    }


def _source_artifacts(artifacts_by_kind: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    artifacts = []
    for kind in _REQUIRED_SOURCE_KINDS + ("v23_command_audit",):
        artifact = artifacts_by_kind.get(kind)
        if not artifact:
            continue
        item = {
            "kind": kind,
            "path": _text(artifact.get("path")),
        }
        if _text(artifact.get("sha256")):
            item["sha256"] = _text(artifact.get("sha256"))
        artifacts.append(item)
    return artifacts


def _command_facts(
    command_results: Iterable[Mapping[str, Any]],
    command_audit_events: Iterable[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    audit_by_request = {
        _text(event.get("request_id")): event
        for event in command_audit_events
        if isinstance(event, Mapping) and _text(event.get("request_id"))
    }
    facts = []
    for result in command_results:
        if not isinstance(result, Mapping):
            continue
        request_id = _text(result.get("request_id"))
        if not request_id:
            continue
        audit = audit_by_request.get(request_id, {})
        facts.append({
            "request_id": request_id,
            "action_type": _text(result.get("action_type")),
            "status": _text(result.get("status")),
            "actor_id": _text(result.get("actor_id")),
            "audit_event_id": _text(audit.get("audit_event_id")),
        })
    return sorted(facts, key=lambda item: item["request_id"])


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
