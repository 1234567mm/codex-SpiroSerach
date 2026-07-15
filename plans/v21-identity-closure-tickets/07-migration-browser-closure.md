# T21-07 Migration, browser smoke, and closure

Status: complete
Source plan: `plans/v21-candidate-evidence-identity-closure-spec.md`

## What to build

Document V21 migration/read policy, run browser smoke, complete focused/full gates, and write closure evidence.

## Acceptance criteria

- Legacy runs without V21 identity artifacts remain readable with local unavailable diagnostics.
- V21 fixture renders accepted links and unresolved diagnostics in a real/headless browser.
- Closure doc records scope, fixture, policy, verification, and hygiene.
- `uv.lock` and local/generated outputs are cleaned before merge.

## Blocked by

- T21-06.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v21_identity_contracts tests.test_v21_identity_readonly tests.test_v21_identity_proposals tests.test_v21_identity_review_routing tests.test_v21_identity_projections tests.test_artifact_viewer -v
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```
