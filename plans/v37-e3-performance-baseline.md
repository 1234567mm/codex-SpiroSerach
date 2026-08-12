# E3 Go Read/Validation Path Performance Baseline

> Status: baseline recorded
> Date: 2026-08-12
> Source: `plans/v37-future-direction-and-task-breakdown-plan.md` T37-03
> Hardware: 13th Gen Intel(R) Core(TM) i5-13500H, windows/amd64
> Go: 1.95.0

## 1. Purpose

Record a measurable baseline for the Go read/validation path before V37
optimization work. Thresholds below are initial planning targets; they are
fixture-relative and machine-relative, not hard product budgets.

## 2. Benchmarks

| Surface | Benchmark | Measured (this machine) | Initial threshold target |
|---------|-----------|--------------------------|--------------------------|
| provider cache lookup | `BenchmarkProviderCacheLatest` (100 records) | 902 ns/op | < 5 µs/op |
| readonly envelope delivery | `BenchmarkAPIEnvelopeDelivery` (manifest + scoring view, v11 fixture) | 106 µs/op | < 1 ms/op |
| CLI source-registry validate | `BenchmarkSpiroctlSourceRegistryValidate` (13 providers) | 561 µs/op | < 10 ms/op |
| CLI run-artifacts validate | `BenchmarkSpiroctlRunArtifactsValidate` (11 artifacts) | 1.60 ms/op | < 25 ms/op |

## 3. How To Re-run

```powershell
go test ./internal/providercache/ -bench BenchmarkProviderCacheLatest -benchtime 100x -run '^$'
go test ./internal/readonlyapi/ -bench BenchmarkAPIEnvelopeDelivery -benchtime 100x -run '^$'
go test ./cmd/spiroctl/ -bench 'BenchmarkSpiroctl' -benchtime 50x -run '^$'
```

Benchmarks are fixture-backed and read-only; they do not require network,
API keys, or live providers.

## 4. Notes

- Measured values are representative, not CI-pinned. Re-run on the target
  machine before V37 optimization claims.
- The V37 optimization slice should treat the threshold column as the
  decision rule: a change is an optimization only if it holds on the target
  machine below the initial threshold.
- These baselines complement the V25 Python-side performance budget
  (`plans/v25-release-hardening-tickets/04-performance-budget-report.md`);
  they do not replace it.
