from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from spirosearch.custom_htl_pilot import validate_molecule_index


def build_scale_readiness_report(
    *,
    cohort: str,
    accepted_records: Sequence[Mapping[str, Any]],
    excluded_records: Sequence[Mapping[str, Any]] | None = None,
    tooling: Mapping[str, bool] | None = None,
    calibration_anchors_present: bool = False,
    measured_runtime_minutes: float | None = None,
    success_count: int = 0,
    failure_counts: Mapping[str, int] | None = None,
    storage_bytes: int = 0,
    manifest_bytes: int = 0,
) -> dict[str, Any]:
    """Build an explicit go/no-go readiness report for 100/500 DFT slices.

    Missing structure sets or tooling remain blocked rather than fabricating results.
    """
    accepted = [dict(row) for row in accepted_records]
    excluded = [dict(row) for row in (excluded_records or [])]
    validation = validate_molecule_index(accepted)
    tool_state = {
        "orca": False,
        "xtb": False,
        "rdkit": False,
        "cclib": False,
    }
    if tooling:
        tool_state.update({str(key): bool(value) for key, value in tooling.items()})

    blockers: list[str] = []
    if cohort not in {"C100", "B500"}:
        raise ValueError("cohort must be C100 or B500")
    expected = 100 if cohort == "C100" else 500
    if validation.accepted_count < expected:
        blockers.append("insufficient_verified_structures")
    if validation.rejected_count:
        blockers.append("accepted_projection_failed_validation")
    if not all(tool_state.get(name) for name in ("xtb", "rdkit", "cclib")) and not tool_state.get("orca"):
        blockers.append("compute_tooling_unavailable")
    if not calibration_anchors_present:
        blockers.append("calibration_anchors_missing")
    if measured_runtime_minutes is None and success_count == 0:
        blockers.append("no_measured_compute_evidence")

    failure_counts = dict(failure_counts or {})
    status = "blocked" if blockers else "ready"
    return {
        "schema_version": "v28.scale_readiness_report.v1",
        "cohort": cohort,
        "status": status,
        "expected_count": expected,
        "accepted_count": validation.accepted_count,
        "excluded_count": len(excluded),
        "validation_rejected_count": validation.rejected_count,
        "validation_reasons": {
            material_id: list(reasons)
            for material_id, reasons in validation.reasons_by_material_id.items()
        },
        "tooling": tool_state,
        "calibration_anchors_present": calibration_anchors_present,
        "measured_runtime_minutes": measured_runtime_minutes,
        "success_count": int(success_count),
        "failure_counts": failure_counts,
        "storage_bytes": int(storage_bytes),
        "manifest_bytes": int(manifest_bytes),
        "blockers": blockers,
        "eligible_for_scoring_default": False,
        "notes": [
            "Computed evidence remains fail-closed until calibration metadata is present.",
            "This report must not invent molecules or energies.",
        ],
    }


def load_selection_summary(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("selection summary must be a JSON object")
    return payload
