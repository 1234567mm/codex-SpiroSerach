# T22-04 Independent snapshot overlap removal

Status: pending
Source plan: `plans/v22-independent-data-and-scientific-validation-spec.md`

## What to build

Add independent NOMAD or approved-alternative snapshot handling only after DOI, material, candidate, and source overlap is removed.

## Acceptance criteria

- Independent snapshot remains `blocked` when source approval/license metadata is absent.
- Overlapping DOI/source/material/candidate identities are excluded with explicit diagnostics.
- Removed-overlap and retained-independent records are reproducible from manifest artifacts.
- No external-validation claim is emitted when the independent set is empty, blocked, or below declared minimums.

## Blocked by

- T22-01.
- T22-03.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v22_independent_snapshot tests.test_paper_cross_ref_store -v
```
