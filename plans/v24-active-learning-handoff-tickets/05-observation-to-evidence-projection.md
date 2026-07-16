# T24-05 Observation-to-evidence projection with review routing

Status: pending
Source plan: `plans/v24-auditable-active-learning-experiment-handoff-spec.md`

## What to build

Project validated observations into evidence/read-model artifacts with lineage
and review routing for incomplete or ambiguous observations.

## Acceptance criteria

- Valid observations produce lineage-preserving evidence candidates.
- Missing provenance, ambiguous identity, or incomplete metrics route to review.
- Projection does not bypass `EvidenceQualityPolicy`.
- Review routing is visible in manifest-discovered artifacts.

## Blocked by

- T24-04.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v24_observation_projection -v
```
