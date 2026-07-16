# T24-04 Human-approved handoff export and observation import

Status: pending
Source plan: `plans/v24-auditable-active-learning-experiment-handoff-spec.md`

## What to build

Add a human-approved experiment handoff export format and a validated
observation import path.

## Acceptance criteria

- Handoff export requires explicit human approval metadata.
- Export is deterministic and contains no autonomous dispatch instruction.
- Observation import validates request identity, measurement fields, and
  provenance.
- Invalid observations fail closed and do not update posterior or evidence.

## Blocked by

- T24-03.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v24_handoff_observations -v
```
