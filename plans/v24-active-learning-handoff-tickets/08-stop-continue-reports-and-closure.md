# T24-08 Stop/continue reports and V24 closure

Status: pending
Source plan: `plans/v24-auditable-active-learning-experiment-handoff-spec.md`

## What to build

Emit stop/continue reports based on discovery efficiency and scientific gates,
then close V24 with focused/full verification and a closure document.

## Acceptance criteria

- Reports explain stop/continue status without inventing scientific success.
- Scientific gates remain authoritative.
- One offline or partner-assisted round can be reproduced from input artifacts
  through observation integration.
- Closure doc records scope, verification, hygiene, and remaining V25 risks.

## Blocked by

- T24-07.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v24_admission tests.test_v24_loop_state tests.test_v24_recommendations tests.test_v24_handoff_observations tests.test_v24_observation_projection tests.test_v24_loop_controls tests.test_v24_project_evolution -v
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```
