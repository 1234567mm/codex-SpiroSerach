# T24-02 Project-level loop state

Status: pending
Source plan: `plans/v24-auditable-active-learning-experiment-handoff-spec.md`

## What to build

Add a project-level loop-state artifact referencing predecessor run, candidate
pool, training snapshot, model evaluation, acquisition policy, budget, ledger,
and V24 admission result.

## Acceptance criteria

- Loop state is deterministic and manifest-discovered.
- Predecessor run and input hashes are explicit.
- Missing required references fail validation.
- Loop state remains a read model; it does not dispatch experiments.

## Blocked by

- T24-01.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v24_loop_state -v
```
