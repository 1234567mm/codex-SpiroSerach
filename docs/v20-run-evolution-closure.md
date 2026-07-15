# V20 Run Evolution Closure

Status: closed for `codex/v20-run-evolution` at integration HEAD `d1f21ff01d12c26eafca42b8a3ffff3ecb6b737c` before the T20-08 closure commit.

## Scope

V20 adds manifest-native project evolution without changing the command plane:

- project run index schema, two-run fixture, repository, and read-only project API
- backend-owned run compatibility and persisted run delta
- exported read-only project envelopes and bundle/envelope parity
- frontend ProjectStore, run selector, candidate history, and project diagnostics

## Closure fixture

Committed fixture: `tests/fixtures/v20_project_evolution/`

The fixture contains:

- two valid runs: `run-001`, `run-002`
- one declared comparison: `run-001` to `run-002`
- one non-comparable dimension: `score_rank` with `DATASET_SNAPSHOT_CHANGED`
- local degraded/unavailable paths covered by tests through copied temporary fixtures

Readers discover artifacts from `project-run-index.json`, per-run `run-manifest.json`, and declared comparison paths. No reader guesses delta filenames or scans directories at read time.

## Migration and read policy

V19 single-run bundles remain readable through the existing `RunDataStore` and manifest-first bundle input.

V20 project bundles are additive:

- a project bundle must include exactly one `project-run-index.json`
- every run is loaded through the existing single-run `RunDataStore`
- failed project loads clear project state instead of retaining stale project/run comparison state
- source/target run selection does not mutate committed run snapshots
- project comparison display consumes backend compatibility and delta payloads only

Out of scope remains unchanged: no provider calls, review writes, scoring mutation, model training, experiment dispatch, fuzzy candidate joins, or scientific external-validation claims.

## Verification evidence

Focused V20 and read-plane gate:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v20_project_evolution_contracts tests.test_v20_project_index_tracer tests.test_v20_run_compatibility_policy tests.test_v20_run_delta_builder tests.test_v20_readonly_envelope_parity tests.test_artifact_viewer tests.test_artifact_repository tests.test_readonly_api tests.test_artifact_validation -v
```

Result: `Ran 81 tests ... OK`.

Latest integration full gate before this closure document:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

Result: `Ran 441 tests ... OK (skipped=3)`.

Headless browser smoke:

```powershell
& 'C:\Program Files\Google\Chrome\Application\chrome.exe' --headless=new --disable-gpu --no-first-run --disable-extensions --dump-dom "file:///D:/tmp/spiro-v20-p8-closure/frontend/artifact-viewer/index.html" | Select-String -Pattern "Project Run Selector|Candidate History|Run bundle directory"
```

Result: Chrome rendered the static viewer DOM and exposed the run bundle input, Project Run Selector, and Candidate History panels.

## Hygiene review

- `uv.lock` is generated locally by `uv run` and removed before commit.
- No `outputs/`, private data, local browser dumps, cache files, or manual envelopes are part of the V20 closure.
- The closure remains read-plane only. Project APIs and frontend adapters do not create provider, scoring, review, recompute, model, or experiment side effects.

