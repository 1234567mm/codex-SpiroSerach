# V28 Scientific Scale Readiness Report

> Date: 2026-07-17
> Tickets: T28-K3, T28-K4

## Decision

| Cohort | Status |
| --- | --- |
| C100 | **blocked** |
| B500 | **blocked** |

### C100

```json
{
  "schema_version": "v28.scale_readiness_report.v1",
  "cohort": "C100",
  "status": "blocked",
  "expected_count": 100,
  "accepted_count": 0,
  "excluded_count": 0,
  "validation_rejected_count": 0,
  "validation_reasons": {},
  "tooling": {
    "orca": false,
    "xtb": false,
    "rdkit": false,
    "cclib": false
  },
  "calibration_anchors_present": false,
  "measured_runtime_minutes": null,
  "success_count": 0,
  "failure_counts": {},
  "storage_bytes": 0,
  "manifest_bytes": 0,
  "blockers": [
    "insufficient_verified_structures",
    "compute_tooling_unavailable",
    "calibration_anchors_missing",
    "no_measured_compute_evidence"
  ],
  "eligible_for_scoring_default": false,
  "notes": [
    "Computed evidence remains fail-closed until calibration metadata is present.",
    "This report must not invent molecules or energies."
  ]
}
```

### B500

```json
{
  "schema_version": "v28.scale_readiness_report.v1",
  "cohort": "B500",
  "status": "blocked",
  "expected_count": 500,
  "accepted_count": 0,
  "excluded_count": 0,
  "validation_rejected_count": 0,
  "validation_reasons": {},
  "tooling": {
    "orca": false,
    "xtb": false,
    "rdkit": false,
    "cclib": false
  },
  "calibration_anchors_present": false,
  "measured_runtime_minutes": null,
  "success_count": 0,
  "failure_counts": {},
  "storage_bytes": 0,
  "manifest_bytes": 0,
  "blockers": [
    "insufficient_verified_structures",
    "compute_tooling_unavailable",
    "calibration_anchors_missing",
    "no_measured_compute_evidence"
  ],
  "eligible_for_scoring_default": false,
  "notes": [
    "Computed evidence remains fail-closed until calibration metadata is present.",
    "This report must not invent molecules or energies."
  ]
}
```

No fabricated molecules/energies. `eligible_for_scoring` remains false by default.
