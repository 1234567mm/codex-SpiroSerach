# V13 Data Closure and Real Baseline

V13 closes the incomplete V12 artifact and model-evaluation path while preserving JSON/JSONL contracts and the modular monolith.

## Offline Commands

```powershell
$env:PYTHONPATH='src'

uv run python -m spirosearch.cli dataset-import `
  --source D:\data\device_attributes_combined.json `
  --source-manifest data\baselines\figshare-25868737-v2\source-manifest.json `
  --output outputs\public-device-snapshot.json

uv run python -m spirosearch.cli acquisition-replay `
  --input replay-input.json `
  --output-dir outputs\replay

uv run python -m spirosearch.cli model-evaluate `
  --snapshot training-snapshot.json `
  --objective pce `
  --model heuristic `
  --model-version heuristic-v1 `
  --replay-report outputs\replay\acquisition-breakdown.json `
  --output-dir outputs\model-evaluation
```

All commands are offline. `model-evaluate --model sklearn` requires the `ml` extra. qLogNEHVI is available through `spirosearch.botorch_adapter.score_qlognehvi` with the `bo` extra and is not the default V4 strategy.

## Artifact Contract

The V13 diagnostic bundle at `tests/fixtures/artifact_viewer/v13_algorithm_run` contains all eleven planned kinds:

- Provider and literature intake: `provider_capabilities`, `literature_search_results`, `source_assets`, `literature_claims`, `device_evidence`, `extraction_evaluation`.
- Screening: `conflict_report`, `screening_input_view`.
- Prediction: `training_snapshot`, `model_evaluation`, `acquisition_breakdown`.

Every entry is manifest-discovered and includes schema reference, SHA-256, byte count, record count, join keys, and dependencies.

## Public Baseline

- Source: Figshare article `25868737`, file `46458169`, DOI `10.6084/m9.figshare.25868737.v2`.
- License: CC0. The earlier V12 fixture incorrectly described this source as CC BY 4.0.
- Source file: 4,665,284 bytes; MD5 `5a55853502d45bb501d3640ed76f8d37`; SHA-256 `c10fc32cc23c1d9136e4f56fc49a9196366fa8d77c28ae09018dc7fd2bb1e3dc`.
- Source rows: 3,164. The committed deterministic snapshot contains 24 records with original row IDs.
- Limitation: the source contains device attributes but no PCE or stability targets. It is therefore `descriptive_only`; model activation remains `disabled` with reason `no_performance_targets`.

## Activation Rules

A model is eligible only when aggregate and every grouped fold beat dummy and heuristic RMSE, uncertainty coverage is non-degenerate, and a matching offline replay reports no regression. Callers cannot self-declare replay success; `model-evaluate` accepts only a validated replay report with the same model version.

Missing optional dependencies, unknown strategies, malformed snapshots, non-finite values, duplicate candidates, mismatched hashes, and missing replay evidence fail closed.

## Verification

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
$env:PYTHONPATH='src'; uv run --extra ml python -m unittest tests.test_sklearn_surrogate tests.test_model_evaluation -v
$env:PYTHONPATH='src'; uv run --extra bo python -m unittest tests.test_botorch_adapter tests.test_acquisition_replay -v
```

On Windows without MSVC, BoTorch falls back to its pure-Python qLogEHVI kernel. Results remain valid but optional BO tests run more slowly.
