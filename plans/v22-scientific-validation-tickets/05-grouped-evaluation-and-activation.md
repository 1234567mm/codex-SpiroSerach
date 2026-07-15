# T22-05 Grouped evaluation and activation

Status: pending
Source plan: `plans/v22-independent-data-and-scientific-validation-spec.md`

## What to build

Persist grouped baseline/model/calibration/replay artifacts and a model activation decision report.

## Acceptance criteria

- Grouped evaluation records split policy, baselines, calibration metrics, replay status, and activation reasons.
- Failed calibration, regressing model quality, tampered replay, or insufficient independent data disables model activation.
- Disabled model state is explicit and consumable by downstream V24 admission.
- Existing model evaluation behavior remains deterministic and manifest-discovered.

## Blocked by

- T22-03.
- T22-04.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_model_evaluation tests.test_v22_model_activation -v
```
