# T21-05 V19/V20 identity projections

Status: pending  
Source plan: `plans/v21-candidate-evidence-identity-closure-spec.md`

## What to build

Project accepted and unresolved identity-link state into V19 candidate read models and V20 run-history diagnostics without mutating old run artifacts.

## Acceptance criteria

- Candidate projections include accepted paper/evidence links only when explicit accepted link records exist.
- Unresolved identity appears as blocking diagnostics.
- V20 history can show identity merge/split/link changes between runs.
- Score/rank/scoring eligibility remains unchanged by link confidence.

## Blocked by

- T21-02
- T21-04

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v21_identity_projections tests.test_v20_run_delta_builder -v
```
