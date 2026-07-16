from __future__ import annotations

from typing import Any


def _blocked(status_payload: dict[str, Any], status_key: str) -> bool:
    return status_payload.get(status_key) == "blocked"


def build_v25_release_checklist(
    *,
    release_profile: dict[str, Any],
    migration_policy: dict[str, Any],
    security_audit: dict[str, Any],
    performance_budget: dict[str, Any],
    recovery_runbook: dict[str, Any],
    final_gate: dict[str, str],
) -> dict[str, Any]:
    reason_codes: list[str] = []
    upstream = [
        ("migration_policy", migration_policy, "policy_status"),
        ("security_audit", security_audit, "audit_status"),
        ("performance_budget", performance_budget, "budget_status"),
        ("recovery_runbook", recovery_runbook, "recovery_status"),
    ]
    for name, payload, key in upstream:
        if _blocked(payload, key):
            reason_codes.append(f"upstream_blocked:{name}")

    if not final_gate.get("command") or not final_gate.get("result"):
        reason_codes.append("final_gate_missing")

    return {
        "schema_version": "v25.release_checklist.v1",
        "release_checklist_id": "v25-release-checklist",
        "reproducibility_bundle_id": "v25-reproducibility-bundle",
        "release_profile_id": release_profile.get("profile_id"),
        "release_status": "blocked" if reason_codes else "pass",
        "reason_codes": reason_codes,
        "evidence": {
            "migration_policy_id": migration_policy.get("policy_id"),
            "security_audit_id": security_audit.get("security_audit_id"),
            "performance_budget_id": performance_budget.get("performance_budget_id"),
            "recovery_runbook_id": recovery_runbook.get("recovery_runbook_id"),
            "final_gate": final_gate,
        },
        "claims": {
            "external_scientific_validation_claimed": False,
            "direct_lab_dispatch_claimed": False,
            "new_provider_or_model_family_claimed": False,
        },
        "signed_by": "release-owner-stub",
    }
