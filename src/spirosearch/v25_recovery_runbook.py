from __future__ import annotations

from typing import Any


BACKUP_SCOPE = ["run-manifest.json", "artifacts", "schemas", "command_outputs", "handoff_artifacts"]


def build_v25_recovery_runbook(
    *,
    release_profile: dict[str, Any],
    migration_policy: dict[str, Any],
    restored_artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    reason_codes: list[str] = []
    if migration_policy.get("policy_status") == "blocked":
        reason_codes.append("migration_policy_blocked")

    restore_checks: list[dict[str, Any]] = []
    for artifact in restored_artifacts:
        kind = artifact.get("kind", "")
        status = "pass"
        if artifact.get("expected_sha256") != artifact.get("actual_sha256"):
            status = "blocked"
            reason_codes.append(f"restore_hash_mismatch:{kind}")
        if not artifact.get("schema_ref"):
            status = "blocked"
            reason_codes.append(f"restore_schema_missing:{kind}")
        restore_checks.append(
            {
                "kind": kind,
                "path": artifact.get("path"),
                "schema_ref": artifact.get("schema_ref"),
                "status": status,
            }
        )

    return {
        "schema_version": "v25.recovery_runbook.v1",
        "recovery_runbook_id": "v25-recovery-runbook",
        "release_profile_id": release_profile.get("profile_id"),
        "migration_policy_id": migration_policy.get("policy_id"),
        "recovery_status": "blocked" if reason_codes else "pass",
        "reason_codes": reason_codes,
        "backup_scope": BACKUP_SCOPE,
        "external_credentials_required": False,
        "restore_checks": restore_checks,
    }
