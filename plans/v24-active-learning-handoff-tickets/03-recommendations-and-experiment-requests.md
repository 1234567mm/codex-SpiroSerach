# T24-03 Deterministic recommendations and experiment requests

Status: pending
Source plan: `plans/v24-auditable-active-learning-experiment-handoff-spec.md`

## What to build

Emit deterministic V24 recommendation and experiment-request artifacts from
admitted loop state and existing acquisition/ledger seams.

## Acceptance criteria

- Candidate recommendations are reproducible from loop state inputs.
- Experiment requests include lineage, budget, model version, and candidate
  identity references.
- Duplicate candidate selection within a round is blocked.
- Disabled admission produces no experiment requests.

## Blocked by

- T24-02.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v24_recommendations -v
```
