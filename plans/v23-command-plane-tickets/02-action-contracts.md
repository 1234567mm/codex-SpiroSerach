# T23-02 ActionRequest and ActionResult contracts

Status: pending
Source plan: `plans/v23-controlled-review-recompute-command-plane-spec.md`

## What to build

Define typed contracts and schemas for review-decision and recompute
`ActionRequest` / `ActionResult` payloads.

## Acceptance criteria

- Requests require actor, role, reason, action type, idempotency key, expected
  source run/hash, and optimistic concurrency fields.
- Results distinguish accepted, rejected, conflict, timeout, cancelled,
  partial_failure, and replayed states.
- Schemas reject missing actor/role/reason/idempotency and unknown action types.
- Contracts do not embed provider calls, model training, or experiment dispatch.

## Blocked by

- T23-01.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v23_action_contracts -v
```
