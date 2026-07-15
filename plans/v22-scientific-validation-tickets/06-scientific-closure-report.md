# T22-06 Scientific closure report

Status: pending
Source plan: `plans/v22-independent-data-and-scientific-validation-spec.md`

## What to build

Emit a versioned V22 scientific closure report with pass/fail/blocked decisions over production snapshot, independent data, leakage, grouping, calibration, replay, and activation gates.

## Acceptance criteria

- Closure report distinguishes software validation from scientific validation.
- Every pass/fail/blocked decision links to manifest-discovered source artifacts.
- Failed gates leave models disabled and explain downstream impact.
- Report schema rejects claims that exceed accepted datasets or disabled gates.

## Blocked by

- T22-03.
- T22-04.
- T22-05.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v22_scientific_closure tests.test_artifact_validation -v
```
