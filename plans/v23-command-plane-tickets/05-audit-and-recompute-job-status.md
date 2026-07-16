# T23-05 Append-only audit outputs and recompute job status

Status: pending
Source plan: `plans/v23-controlled-review-recompute-command-plane-spec.md`

## What to build

Persist accepted command outputs as append-only audit/action artifacts and
deterministic recompute job statuses.

## Acceptance criteria

- Accepted review decisions produce attributable audit events.
- Accepted recompute requests produce manifest-discovered job status artifacts.
- Old run artifacts remain immutable.
- Retry, timeout, cancellation, and partial failure are represented without
  silent mutation.

## Blocked by

- T23-04.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_review_runtime tests.test_run_artifacts tests.test_v23_command_outputs -v
```
