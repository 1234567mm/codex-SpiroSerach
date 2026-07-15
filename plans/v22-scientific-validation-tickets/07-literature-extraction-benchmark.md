# T22-07 Literature extraction benchmark

Status: pending
Source plan: `plans/v22-independent-data-and-scientific-validation-spec.md`

## What to build

Admit the V18 literature extraction benchmark as the single V22 supporting lane, if it remains engineering-only and does not claim scientific closure.

## Acceptance criteria

- Benchmark records model/prompt version, quality, cost, latency, failure modes, and review throughput.
- Closed/full-text unavailable cases remain manual/review tasks, not silent exclusions.
- Benchmark output is reported separately from scientific validation closure.
- Homogeneous HTL pilot remains parked unless ownership, budget, calibration anchors, runtime, and identity are present.

## Blocked by

- T22-01.
- Capacity after primary-lane tickets.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v31_knowledge_factory tests.test_v22_literature_benchmark -v
```
