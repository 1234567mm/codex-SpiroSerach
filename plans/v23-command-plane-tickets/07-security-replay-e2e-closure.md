# T23-07 Security, replay, and end-to-end closure

Status: pending
Source plan: `plans/v23-controlled-review-recompute-command-plane-spec.md`

## What to build

Close V23 with end-to-end tests, closure evidence, and main merge verification.

## Acceptance criteria

- Duplicate, stale, unauthorized, and replayed commands cannot silently change
  state.
- Every accepted action is attributable and produces manifest-discovered output.
- Security/replay tests cover command and read-only registry separation.
- Closure doc records scope, verification, hygiene, and remaining V24/V25 risks.

## Blocked by

- T23-06.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v23_command_preflight tests.test_v23_action_contracts tests.test_v23_command_authorization tests.test_v23_command_registry tests.test_v23_command_outputs tests.test_v23_command_viewer -v
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```
