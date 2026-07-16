# T24-06 Replay, budget, stale-model, duplicate, and leakage controls

Status: pending
Source plan: `plans/v24-auditable-active-learning-experiment-handoff-spec.md`

## What to build

Enforce controls for replay determinism, round budget, duplicate candidates,
stale model/admission state, and leakage from future observations.

## Acceptance criteria

- Replaying the same loop state produces identical recommendations and requests.
- Budget overruns fail closed before handoff export.
- Stale model/admission references block request generation.
- Leakage checks prevent future observations from influencing prior decisions.

## Blocked by

- T24-05.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v24_loop_controls -v
```
