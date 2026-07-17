from __future__ import annotations

from typing import Any


BACKUP_SCOPE = [
    "run-manifest.json",
    "artifacts",
    "schemas",
    "command_outputs",
    "handoff_artifacts",
    "v28_evidence_docs",
]


def build_v28_incident_checklist(
    *,
    release_profile_id: str,
    restore_checks: list[dict[str, Any]],
    dependency_scan_status: str = "not_run",
    rollback_procedure_documented: bool = True,
) -> dict[str, Any]:
    reason_codes: list[str] = []
    normalized_checks: list[dict[str, Any]] = []
    for check in restore_checks:
        status = str(check.get("status") or "blocked")
        kind = str(check.get("kind") or "unknown")
        if status != "pass":
            reason_codes.append(f"restore_check_failed:{kind}")
        normalized_checks.append(
            {
                "kind": kind,
                "status": status,
                "path": check.get("path"),
                "notes": check.get("notes"),
            }
        )
    if dependency_scan_status not in {"pass", "skipped_local_only"}:
        reason_codes.append(f"dependency_scan:{dependency_scan_status}")
    if not rollback_procedure_documented:
        reason_codes.append("rollback_procedure_missing")

    return {
        "schema_version": "v28.incident_checklist.v1",
        "incident_checklist_id": "v28-incident-checklist",
        "release_profile_id": release_profile_id,
        "status": "blocked" if reason_codes else "pass",
        "reason_codes": reason_codes,
        "backup_scope": BACKUP_SCOPE,
        "external_credentials_required": False,
        "hosted_deployment": False,
        "restore_checks": normalized_checks,
        "dependency_scan_status": dependency_scan_status,
        "rollback_procedure_documented": rollback_procedure_documented,
        "steps": [
            "Stop local writes to the affected run directory.",
            "Preserve run-manifest.json and artifact hashes.",
            "Restore from last known-good local backup.",
            "Re-validate schema refs and sha256 values.",
            "Re-run focused unittest gate before continuing scientific work.",
            "Do not open hosted deployment paths during V28 recovery.",
        ],
    }


def build_v28_local_rehearsal_report(
    *,
    start_sha: str,
    install_status: str,
    test_gate_status: str,
    screening_run_path: str | None,
    artifact_validation_status: str,
    viewer_status: str,
    restore_status: str,
    elapsed_minutes: float,
    failures: list[str] | None = None,
) -> dict[str, Any]:
    failures = list(failures or [])
    status = "pass"
    if any(value != "pass" for value in (
        install_status,
        test_gate_status,
        artifact_validation_status,
        viewer_status,
        restore_status,
    )) or failures:
        status = "blocked"
    return {
        "schema_version": "v28.local_rehearsal_report.v1",
        "start_sha": start_sha,
        "status": status,
        "install_status": install_status,
        "test_gate_status": test_gate_status,
        "screening_run_path": screening_run_path,
        "artifact_validation_status": artifact_validation_status,
        "viewer_status": viewer_status,
        "restore_status": restore_status,
        "elapsed_minutes": float(elapsed_minutes),
        "failures": failures,
        "hosted_deployment": False,
        "notes": [
            "Local/DevContainer only.",
            "No credentials or external writes required for core workflow.",
        ],
    }
