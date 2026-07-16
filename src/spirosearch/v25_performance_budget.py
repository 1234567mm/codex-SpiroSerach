from __future__ import annotations

from typing import Any


DEFAULT_BUDGETS = {
    "artifact_repository_read_ms": 250,
    "project_summary_ms": 500,
    "viewer_payload_kb": 512,
}


def build_v25_performance_budget_report(
    *,
    release_profile: dict[str, Any],
    measurements: dict[str, float],
    budgets: dict[str, float] | None = None,
) -> dict[str, Any]:
    active_budgets = budgets or DEFAULT_BUDGETS
    reason_codes: list[str] = []
    rows: list[dict[str, Any]] = []

    for name, limit in active_budgets.items():
        if name not in measurements:
            reason_codes.append(f"measurement_missing:{name}")
            rows.append({"name": name, "limit": limit, "actual": None, "status": "blocked"})
            continue
        actual = measurements[name]
        status = "pass" if actual <= limit else "blocked"
        if status == "blocked":
            reason_codes.append(f"budget_exceeded:{name}")
        rows.append({"name": name, "limit": limit, "actual": actual, "status": status})

    return {
        "schema_version": "v25.performance_budget_report.v1",
        "performance_budget_id": "v25-performance-budget",
        "release_profile_id": release_profile.get("profile_id"),
        "budget_status": "blocked" if reason_codes else "pass",
        "reason_codes": reason_codes,
        "measurements": rows,
    }
