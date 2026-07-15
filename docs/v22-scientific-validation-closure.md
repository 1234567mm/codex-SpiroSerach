# V22 Independent Data And Scientific Validation Closure

Status: closed on feature branch

## Scope

V22 adds versioned reports for production snapshot quality, zero leakage,
independent overlap removal, grouped model activation, scientific closure, and
the engineering-only literature benchmark lane.

## Fixture and artifact policy

V22 fixtures are source-shaped and manifest-discovered. Scientific gates read
versioned JSON artifacts from `run-manifest.json`; they do not infer filenames
or use live providers.

## Migration and read policy

Read-only API and MCP surfaces expose V22 reports through
`v22_scientific_reports`. The surface reads local artifacts only and does not
trigger provider calls, scoring mutation, review writes, recompute dispatch,
model training, or experiment dispatch.

## Verification

Focused V22 gate:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v22_scientific_contracts tests.test_v22_quality_reports tests.test_v22_independent_snapshot tests.test_v22_model_activation tests.test_v22_scientific_closure tests.test_artifact_viewer tests.test_readonly_api -v
```

Result: 44 tests OK.

Final full gate:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

Result: 480 tests OK, 3 skipped.

## Hygiene

`uv.lock` and generated local outputs are removed before merge. Temporary
feature worktrees are removed after integration.

## Residual scientific risks

V22 does not claim external validation beyond accepted production and retained
independent datasets. Disabled gates leave models disabled for V24 admission.
The literature benchmark remains engineering support and cannot close
scientific validation. Homogeneous HTL pilot remains parked until ownership,
budget, calibration anchors, runtime, and identity policy are present.
