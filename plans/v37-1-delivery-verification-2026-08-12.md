# V37.1 Delivery Verification Record

> Date: 2026-08-12
> Baseline HEAD: `0cee55303f11f78344a48daf108f753c7327aaf2` (feat: V37.1 production activation)
> Scope: verify T37-01..T37-04 delivery evidence from `plans/v37-future-direction-and-task-breakdown-plan.md`
> Verifier: codex agent (user-approved: verify V37.1 before planning V37.2)

## 1. T37-01 PubChem Go live provider — VERIFIED

- `spiroctl source-provider lookup pubchem --name <name> [--cache <path> --authorize-cache-write]`
  registered in `cmd/spiroctl/main.go` (usage line 118, handler 422+).
- Uses `providercache.ProviderResponse` contract (main.go:489), schema `v37.source_live_lookup.v1`.
- Rate limiter present in `internal/pubchem/client.go` + tests.
- Cache writes require explicit `--authorize-cache-write` (command-plane rule kept).
- Evidence: `go test ./cmd/spiroctl/` (ok, exit=0); `go test ./internal/pubchem/ ./internal/materialsproject/ ./internal/providercache/` (ok, exit=0).

## 2. T37-02 Materials Project Go live provider — VERIFIED

- `spiroctl source-provider lookup materials_project --formula <formula> [--cache ...]` registered.
- API key via `MATERIALS_PROJECT_API_KEY` (client.go:87); missing key -> `missing_api_key`
  probe report, no live call (fail-closed); test proves key travels in header only,
  never leaks into `source_url` (client_test.go:51-55).
- Evidence: same Go test gates as T37-01.

## 3. T37-03 E3 performance baseline — VERIFIED (re-run on this machine)

| Surface | Benchmark | Measured (re-run) | Documented | Threshold |
|---------|-----------|-------------------|------------|-----------|
| provider cache lookup | `BenchmarkProviderCacheLatest` (100 rec) | 945 ns/op | 902 ns/op | < 5 µs/op |
| readonly envelope | `BenchmarkAPIEnvelopeDelivery` (v11 fixture) | 125,513 ns/op (125.5 µs) | 106 µs/op | < 1 ms/op |
| CLI source-registry | `BenchmarkSpiroctlSourceRegistryValidate` (13) | 490,390 ns/op (0.49 ms) | 561 µs/op | < 10 ms/op |
| CLI run-artifacts | `BenchmarkSpiroctlRunArtifactsValidate` (11) | 1,663,512 ns/op (1.66 ms) | 1.60 ms/op | < 25 ms/op |

All values re-produced on this machine and below the recorded thresholds.

## 4. T37-04 E2 Python bridge deprecation tracking — VERIFIED

- `src/spirosearch/providers/pubchem.py:36` — `PubChemPUGRestProvider` DEPRECATED (V37.1, 2026-08-12).
- `src/spirosearch/providers/electronic.py:211` — `MaterialsProjectProvider` DEPRECATED (V37.1).
- `src/spirosearch/htl_workbench.py:782-784` — `refresh_pubchem_identity_cache` DEPRECATED note.
- `tests/test_pubchem_provider.py:5` + `tests/test_electronic_property_providers.py:7` —
  ORACLE REFERENCE (V37.1) header notes.
- Oracle tests keep passing: `uv run python -m unittest tests.test_pubchem_provider tests.test_electronic_property_providers -q`
  -> `Ran 24 tests ... OK` (exit=0).

## 5. Conclusion

V37.1 (T37-01..T37-04) delivery evidence holds. The Go read/lookup path is the live
executor for PubChem and Materials Project; Python paths are deprecated oracle
references; performance baselines are recorded and reproducible.

Next: V37.2 planning (T37-05..T37-08) — NOMAD official OpenAPI alignment + CEPDB
snapshot importer.
