# T22-03 Quality and zero-leakage reports

Status: pending
Source plan: `plans/v22-independent-data-and-scientific-validation-spec.md`

## What to build

Produce identity, unit, rejection, conflict, and zero-leakage reports for the production snapshot.

## Acceptance criteria

- Reports list accepted, rejected, blocked, duplicate, conflicting, and ambiguous records.
- Leakage checks cover DOI, source id, material identity, candidate identity, and grouped split membership.
- Any unresolved identity/unit/conflict/leakage finding blocks scientific closure and is manifest-discovered.
- Reports are deterministic under input ordering changes.

## Blocked by

- T22-01.
- T22-02 for provider-adapted records.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v22_quality_reports tests.test_v21_identity_projections -v
```
