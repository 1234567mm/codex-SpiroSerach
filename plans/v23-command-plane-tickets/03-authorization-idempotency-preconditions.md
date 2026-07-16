# T23-03 Authorization, idempotency, and optimistic preconditions

Status: pending
Source plan: `plans/v23-controlled-review-recompute-command-plane-spec.md`

## What to build

Implement command validation for actor roles, idempotency, expected source
run/hash, and optimistic concurrency before any action output is written.

## Acceptance criteria

- Unauthorized roles fail closed with a structured rejection.
- Duplicate idempotency keys replay the original result for identical payloads.
- Reused idempotency keys with different payloads fail as conflicts.
- Stale source run/hash or version preconditions fail as conflicts.
- No rejected/conflicting command writes review events or recompute markers.

## Blocked by

- T23-02.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v23_command_authorization -v
```
