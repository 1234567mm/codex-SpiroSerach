from __future__ import annotations

from typing import Any

from .artifacts import ARTIFACT_KIND_METADATA


def build_v25_migration_policy(
    *,
    release_profile: dict[str, Any],
    manifest_artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    reason_codes: list[str] = []
    checked: list[dict[str, Any]] = []

    for artifact in manifest_artifacts:
        kind = artifact.get("kind", "")
        expected_schema_ref = ARTIFACT_KIND_METADATA.get(kind, {}).get("schema_ref")
        actual_schema_ref = artifact.get("schema_ref")
        status = "pass"

        if expected_schema_ref and not actual_schema_ref:
            status = "blocked"
            reason_codes.append(f"missing_schema_ref:{kind}")
        elif expected_schema_ref and actual_schema_ref != expected_schema_ref:
            status = "blocked"
            reason_codes.append(f"unsupported_schema_ref:{kind}")

        checked.append(
            {
                "kind": kind,
                "expected_schema_ref": expected_schema_ref,
                "actual_schema_ref": actual_schema_ref,
                "status": status,
            }
        )

    return {
        "schema_version": "v25.migration_policy.v1",
        "policy_id": "v25-migration-policy",
        "release_profile_id": release_profile.get("profile_id"),
        "policy_status": "blocked" if reason_codes else "pass",
        "reason_codes": reason_codes,
        "supported_artifact_kinds": sorted(ARTIFACT_KIND_METADATA),
        "checked_artifacts": checked,
    }
