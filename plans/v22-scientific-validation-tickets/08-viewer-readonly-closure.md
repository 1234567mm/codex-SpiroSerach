# T22-08 Viewer, read-only surfaces, and closure gates

Status: pending
Source plan: `plans/v22-independent-data-and-scientific-validation-spec.md`

## What to build

Expose V22 reports through read-only surfaces and the artifact viewer, run browser smoke, full gates, and write closure evidence.

## Acceptance criteria

- Read-only API/MCP surfaces expose V22 reports without provider calls, scoring mutation, review writes, recompute, training, or experiment dispatch.
- Viewer displays pass/fail/blocked scientific gates and disabled-model diagnostics from manifest-discovered artifacts.
- Closure doc records scope, fixture, migration/read policy, verification, hygiene, and residual scientific risks.
- `uv.lock` and generated local outputs are removed before merge.

## Blocked by

- T22-06.
- T22-07 if admitted.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v22_scientific_contracts tests.test_v22_quality_reports tests.test_v22_independent_snapshot tests.test_v22_model_activation tests.test_v22_scientific_closure tests.test_artifact_viewer tests.test_readonly_api -v
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```
