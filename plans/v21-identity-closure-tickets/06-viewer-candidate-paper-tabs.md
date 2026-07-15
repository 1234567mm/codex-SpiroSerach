# T21-06 Viewer candidate paper tabs

Status: pending  
Source plan: `plans/v21-candidate-evidence-identity-closure-spec.md`

## What to build

Add candidate paper/evidence tabs to the static artifact viewer using V21 read-model projections.

## Acceptance criteria

- Tabs render only accepted explicit links.
- Proposed/blocked/conflicting identity states render diagnostics, not paper associations.
- Frontend consumes manifest/read-only payloads through existing store seams.
- No hard-coded output names, directory scans, or fuzzy joins.

## Blocked by

- T21-05.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_artifact_viewer -v
```
