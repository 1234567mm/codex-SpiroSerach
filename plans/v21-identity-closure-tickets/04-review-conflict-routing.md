# T21-04 Review and conflict routing

Status: pending  
Source plan: `plans/v21-candidate-evidence-identity-closure-spec.md`

## What to build

Add read-plane diagnostics for ambiguous, conflicting, merged, split, proposed, or blocked identity links.

## Acceptance criteria

- Blocked/proposed links carry review IDs or stable diagnostic reason codes.
- Conflicting accepted links fail closed for candidate-paper display.
- Merge/split lineage is visible and does not rewrite old run identity.
- Diagnostics are emitted as read artifacts/envelopes only; no review command writes.

## Blocked by

- T21-01
- T21-03

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v21_identity_review_routing -v
```
