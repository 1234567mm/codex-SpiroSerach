# V35 Execution Status And Next Slices

Status: active execution checkpoint  
Branch: `codex-v35-data-source-p0`  
Latest implementation HEAD before this status update: `e410a4c`
Date: 2026-07-24

## Goal

V35 upgrades SpiroSearch toward a Go plus TypeScript architecture while keeping
Python scientific/ML paths as bounded bridge services until there is parity
evidence. The goal is not reduced: Go owns deterministic runtime contracts and
TypeScript owns AtomReasonX workbench surfaces; Python remains only where the
scientific ecosystem is still the validated implementation.

## Completed Commits

The current branch contains these V35 execution commits:

| Commit | Slice | Result |
| --- | --- | --- |
| `069d216` | PubChem Go shadow parity | Go provider response parity for identity lookup. |
| `05be7a1` | Go read-only provider cache/backend readers | P1 read-side foundation for provider cache and local backend. |
| `2cdc323` | TypeScript source profile workbench surfaces | P2 source profile/status/settings display baseline. |
| `b3b0d86` | HOPV15 and OPV-DB Go snapshot parity | Local snapshot readers and provider response guardrails. |
| `e762cd6` | Materials Project Go shadow parity | First-wave live provider with API-key redaction boundary. |
| `ef17208` | NOMAD PERLA Go shadow parity | Search/archive query parity, fallback review markers, and HTL-focused fields. |
| `2d44a67` | PubChemQC and Materials Cloud snapshot foundation | Local snapshot contracts, manifests, quarantine enforcement, metadata-only Materials Cloud. |
| `2417dfc` | AtomReasonX workbench read adapter | Fixture-backed read adapter, no-op local transport facade, workspace loading/error/ready store. |
| `f9e478c` | Go run artifact read-only validation | Manifest-discovered artifact repository with safe relative paths, junction/symlink rejection, duplicate kind rejection, byte/hash checks, JSON/JSONL parsing, and `spiroctl run-artifacts validate`. |
| `72ecd86` | Go readonly run envelope foundation | V11-shaped read-only envelopes for `manifest`, `artifact_index`, and `artifact_by_kind`, plus `spiroctl readonly-run validate` over existing fixture runs. |
| `5cf3680` | Go readonly run surface expansion | V11-shaped read-only envelopes for `scoring_view`, `review_summary`, and `provider_lineage`; CLI validation now covers six readonly surfaces and every manifest artifact. |
| `338f508` | AtomReasonX Go readonly transport facade | TypeScript GET-only transport for V11 readonly run envelopes, with fail-closed envelope validation and no command-shaped methods. |
| `b01f0fd` | Go readonly sidecar HTTP delivery | Loopback-only `spiroctl readonly-run serve <output-dir> [--addr <addr>]`, private startup JSON with `base_url`, `run_id`, and one-time readonly token, token-protected six-route GET surface, manifest run-id binding, unsafe segment rejection, write-shaped route rejection, no-side-effect guard, import guard, and TypeScript readonly token support. |
| `a764b60` | AtomReasonX readonly sidecar launch bridge | Tauri launches the loopback Go sidecar through a fixed command shape, validates private startup JSON, keeps executable selection out of the WebView, passes the readonly token only into the GET transport, exposes process-id stop, tightens run-id mismatch handling, and limits CSP fetches to loopback. |
| `71ee063` | AtomReasonX readonly run workspace adapter | TypeScript projects Go readonly envelopes for manifest, artifact index, scoring view, review summary, and provider lineage into `AtomReasonXWorkspaceState`, fails closed on unavailable surfaces, preserves fixture fallback when no readonly output directory is configured, disposes sidecar sessions, and withholds command dispatchers in readonly mode. |
| `c33727b` | V35 read validation regression gate | Adds `scripts/check-v35-read-validation.ps1` to run Go read/validation packages plus CLI fixture checks for source registry, V35 source snapshots, provider cache/index, run artifacts, and readonly run envelopes. |
| `4d417ce` | AtomReasonX readonly run operator config | Adds a Data Sources settings entry for operator-controlled readonly run output directories, moves readonly output-dir normalization into a side-effect-free TypeScript config module, rebuilds the runtime read adapter from React state, keeps command dispatch unavailable in readonly mode, and preserves an error-state settings path so a bad directory can be cleared without command or credential exposure. |
| `092192b` | AtomReasonX sidecar packaging preflight | Adds an executable packaging preflight for readonly sidecar release boundaries: current `dev_path_only` mode is explicit, future bundled mode must use `bundle.externalBin = ["binaries/spiroctl"]`, `spiroctl` must not be hidden in resources, and WebView/Rust bridges must not expose executable paths or credential-shaped state. |
| `3b58535` | NOMAD perovskite schema reference module | Records the downloaded FAIRmat/NFDI NOMAD perovskite package as a `nomad_perovskite_schema` schema/reference module under `data/lib`, validates its checksum through the Go source snapshot gate, and asserts it is not a data mirror or provider-fact source. |
| `588c9b9` | AtomReasonX readonly run recent directory selector | Adds a read-side recent readonly run output-dir selector for operator workflow, deduplicates and filters recent paths, rejects credential-shaped and executable-looking values, and keeps the setting free of command, token, localStorage, and sidecar executable-path state. |
| `c9e34ab` | AtomReasonX sidecar release build policy | Adds a repository-owned PowerShell build path for the Go `spiroctl` Tauri sidecar, writes the Tauri-required `spiroctl-<target-triple>[.exe]` artifact plus checksum and manifest, smoke-tests the host artifact, ignores generated binaries, and extends packaging preflight with production artifact manifest/hash checks. |
| `752a399` | AtomReasonX bundled spiroctl sidecar enablement | Enables Tauri `bundle.externalBin = ["binaries/spiroctl"]`, routes `tauri:build` through sidecar build and preflight first, adds Rust-side bundled sidecar path resolution without exposing a WebView executable-path surface or shell plugin, and commits a Tauri `Cargo.lock` for reproducible desktop packaging inputs. |
| `53bb44f` | P3 source closure readiness gate | Adds `spiroctl source-closure validate <source-manifest>` with a stable JSON readiness report, separates fixture/integrity validation from production/scientific closure, and blocks current PubChemQC and Materials Cloud fixtures from being claimed as closure-ready. |
| `909034a` | P3 source closure requirements backlog | Adds `spiroctl source-closure requirements <source-id>` as a machine-readable input checklist for PubChemQC and Materials Cloud real-data closure, without downloading data or widening provider/scoring write paths. |
| `314005d` | P1 source closure requirements schema contract | Adds a versioned JSON schema for the requirements report, Go report validation, schema drift tests, and V35 gate coverage so TypeScript/agent readers have a stable contract. |
| `7705579` | P1 Materials Project source-provider probe contract | Adds a sanitized read-only `spiroctl source-provider test-connection materials_project` report over registry/key/live probe state, with missing-key no-network behavior and schema/gate coverage. |
| `afe45e4` | P2 AtomReasonX Materials Project probe command contract | Adds the TypeScript result contract and settings Test-button command payload for the Materials Project source-provider probe, keeps source settings separate from model settings, and allowlists non-secret probe input to `formula` only. |
| `38ed17f` | P1/P2 V35 probe checkpoint coverage | Updates the V35 checkpoint and regression test coverage so the Materials Project Go package/probe CLI contract is part of the durable validation surface. |
| `3802fe5` | P2 backend Materials Project probe command bridge | Connects Python `ConfigCommandPlane` source `test_connection` results to the V35 Materials Project probe report shape, with missing-key no-runner behavior, backend-owned secret source tracking, fixed Go `spiroctl` runner support, sanitized output artifacts, and idempotent replay of prior probe artifacts without a second live runner call. |
| `afc8d42` | P3 Materials Cloud single-record scientific closure contract | Adds a record-specific Materials Cloud scientific import admission path gated by parser, unit, checksum, license, citation, and manifest-listed validation evidence; metadata-only fixtures remain blocked, unknown scientific fields still fail closed, and `source-closure` readiness gains a schema-pinned JSON contract. |
| `a67ef09` | Agent verification workflow optimization | Makes broad gates milestone evidence, adds targeted review-fix reverification rules, discovery/test budget guidance, and verification-scope reporting without changing runtime behavior. |
| `febabe3` | P3 Materials Cloud report-body closure hardening | Adds schema-pinned Materials Cloud parser/unit report bodies and fail-closed validation for `status=pass`, accepted scientific fields, and expected units before any single-record scientific bundle can pass closure or load as provider facts. |
| `11404b6` | P3 PubChemQC Python bridge report-body closure hardening | Adds schema-pinned PubChemQC Python oracle and Go-vs-Python parser parity reports, requiring `status=pass`, oracle/parser identity, record-count agreement, and accepted-field coverage before a ready snapshot can pass closure. |
| `e38687d` | Agent targeted verification guardrails | Adds hygiene sentinels and documents milestone-gate/targeted-reverification rules so review fixes rerun the affected checks without shrinking the V35 goal. |
| `1ffa0c3` | P2 Materials Project operator command transport | Routes AtomReasonX source config commands through a fixed Tauri bridge to Python `ConfigCommandPlane`, while non-config workflow actions remain queued and read-only/runtime writer boundaries stay separate. |
| `e410a4c` | P1 AtomReasonX source-settings command projection | Projects accepted source config command results into the UI-local workbench state, preserves readonly/no-command mode, ignores rejected/queued/non-source/stale results, and keeps source-setting projection secret-free. |
| current slice | P1 AtomReasonX workflow operator task queue | Converts known NOMAD/import/workflow commands into explicit UI-local `workflow_command_task` artifacts with `writes_authorized=false` and `execution_started=false`; unknown commands remain `transport_pending`, and no provider cache, SQLite, scoring, experiment, download, or live provider write path is invoked. |

## Current Data Source Status

| Source | Current state | Next required closure |
| --- | --- | --- |
| PubChem | Go shadow ready; source settings remain separate from model provider settings. | Later live transport hardening and rate-limit telemetry. |
| Materials Project | Go shadow ready; API key is configured through source settings and redacted in backend/runtime outputs; `source-provider test-connection materials_project` exposes a sanitized read-only probe contract; AtomReasonX has the source-scoped command/result contract; Python `ConfigCommandPlane` now emits matching sanitized `provider_probe` artifacts, can hand backend-owned keys to a fixed Go `spiroctl` probe runner without renderer key exposure, the desktop command slice executes config-plane actions through a fixed Tauri bridge with persistent idempotency replay, and AtomReasonX projects accepted source-setting command results back into workbench state without secrets or provider facts. | Next source-provider transport work can add read-only live probe ergonomics and later explicit write-authorized import/execution admission; provider cache, SQLite, scoring, and experiment writes remain out of the current operator-task queue. |
| NOMAD PERLA PSC | Go shadow ready for HTL search/archive parity; archive rate limiting and schema-unrecognized cases route to review. AtomReasonX now records known NOMAD sync controls as local operator tasks, but does not execute downloads or mutate local data. | Keep archive fallback conservative; add live sync execution only behind explicit operator command authorization and a separate data-library write contract. |
| HOPV15 | Go local snapshot parity; still may require Python bridge for larger chemistry parsing/import decisions. | Full snapshot import tooling and dataset-scale validation. |
| OPV-DB | Go local snapshot parity; device metrics remain benchmark facts, not PSC truth. | Full CC-BY attribution/import bundle policy. |
| PubChemQC | Local snapshot foundation plus P3 closure-readiness gate; quarantined; `python_bridge_required=true`; records must be explicit computed facts; ready snapshots now require schema-valid Python oracle and parser parity report bodies. | Full dataset acquisition, real parser parity, Python oracle output, identity join, checksum, license/citation, and storage policy before any non-fixture import. |
| Materials Cloud | Manual archive metadata import plus P3 closure-readiness gate; metadata-only facts remain blocked; a single-record scientific path is now defined only for explicitly allowlisted fields with parser, unit, checksum, license, citation, manifest-listed validation evidence, and schema-valid parser/unit report bodies. | Real operator-selected record DOI/version/file bundle, record-specific parser report body, unit validation body, license/citation review, checksum coverage, and identity evidence before non-fixture scientific facts are admitted. |
| NOMAD perovskite schema package | Schema/reference module; not a data mirror. | Optional deeper schema extraction only if it improves field alias coverage. |
| Crossref/OpenAlex | Existing Python/provider plan surfaces; not part of current Go parity wave. | Future literature metadata Go parity after data-source P3 stabilizes. |
| Custom HTL DFT | Project-generated calculation path; Python bridge retained. | Keep as science bridge until workflow/tooling parity exists. |
| Local paper vault/future extraction | Workbench-visible, deferred extractor path. | P4/P5 knowledge pipeline and model-assisted extraction contracts. |

## Verification Evidence

Recent gates run during this checkpoint:

- `$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./...` passed.
- `$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./internal/runartifact ./cmd/spiroctl -v` passed for the run artifact slice.
- `$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./internal/readonlyapi ./cmd/spiroctl -v` passed for both readonly envelope slices.
- `$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./internal/readonlyserver ./internal/readonlyapi ./cmd/spiroctl -v` passed for the readonly sidecar slice.
- `npm.cmd test` in `frontend/atomreasonx` passed with 19 Vitest tests.
- `npm.cmd run build` in `frontend/atomreasonx` passed.
- `$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v` passed after both Go read-side slices and again after the sidecar slice; generated root `uv.lock` was removed each time.
- `$env:PYTHONPATH='src'; uv run python -m unittest tests.test_atomreasonx_contracts tests.test_atomreasonx_frontend -v` passed outside sandbox after user-level `uv` cache failed inside sandbox.
- `git diff --check` passed with LF-to-CRLF warnings only.
- `scripts/check-agent-hygiene.ps1` passed.
- `Test-Path uv.lock` was restored to `False` after Python gates generated a local lockfile.
- `npm.cmd test` in `frontend/atomreasonx` passed with 25 Vitest tests after the Tauri bridge slice.
- `npm.cmd run build` in `frontend/atomreasonx` passed after the Tauri bridge slice.
- `$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./...` passed after the Tauri bridge slice.
- `$env:PYTHONPATH='src'; uv run python -m unittest tests.test_atomreasonx_frontend tests.test_atomreasonx_contracts -v` passed outside sandbox with 40 tests after the Tauri bridge slice; sandboxed Python hit local uv trampoline/cache permissions.
- `$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v` passed outside sandbox with 926 tests and 9 skipped after the Tauri bridge slice; generated root `uv.lock` was removed again.
- `git diff --cached --check` passed before committing the Tauri bridge slice.
- Rust-native `rustfmt` and `cargo test` remain environment-blocked on this machine: `rustfmt.exe` is not installed for the stable MSVC toolchain, and MSVC `link.exe` is not on PATH.
- `npm.cmd test` in `frontend/atomreasonx` passed with 28 Vitest tests after the readonly workspace adapter slice.
- `npm.cmd run build` in `frontend/atomreasonx` passed after the readonly workspace adapter slice.
- `$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./...` passed after the readonly workspace adapter slice.
- `$env:PYTHONPATH='src'; uv run python -m unittest discover tests` passed outside sandbox with 927 tests and 9 skipped after the readonly workspace adapter slice; generated root `uv.lock` was removed again.
- `git diff --check` and `scripts/check-agent-hygiene.ps1` passed after the readonly workspace adapter slice.
- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-v35-read-validation.ps1 -RepositoryRoot (git rev-parse --show-toplevel)` passed after the P1 regression gate slice.
- `$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./...` passed after the P1 regression gate slice.
- `$env:PYTHONPATH='src'; uv run python -m unittest tests.test_v35_read_validation_script -v` passed outside sandbox with 1 test after the P1 regression gate slice.
- `$env:PYTHONPATH='src'; uv run python -m unittest discover tests` passed outside sandbox with 928 tests and 9 skipped after the P1 regression gate slice; generated root `uv.lock` was removed again.
- `npm.cmd test` in `frontend/atomreasonx` passed with 30 Vitest tests after the readonly run operator config slice.
- `npm.cmd run build` in `frontend/atomreasonx` passed after the readonly run operator config slice.
- `$env:PYTHONPATH='src'; uv run python -m unittest tests.test_atomreasonx_frontend -v` passed outside sandbox with 17 tests after the readonly run operator config slice.
- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-v35-read-validation.ps1 -RepositoryRoot (git rev-parse --show-toplevel)` passed after the readonly run operator config slice.
- `$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./...` passed after the readonly run operator config slice.
- `$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v` passed outside sandbox with 928 tests and 9 skipped after the readonly run operator config slice; generated root `uv.lock` was removed again.
- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-atomreasonx-sidecar-packaging.ps1 -RepositoryRoot (git rev-parse --show-toplevel)` passed after the sidecar packaging preflight slice with `mode=dev_path_only`.
- `$env:PYTHONPATH='src'; uv run python -m unittest tests.test_atomreasonx_sidecar_packaging -v` passed outside sandbox with 2 tests after the sidecar packaging preflight slice.
- `$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v` passed outside sandbox with 930 tests and 9 skipped after the sidecar packaging preflight slice; generated root `uv.lock` was removed again.
- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-v35-read-validation.ps1 -RepositoryRoot D:\1-QRS\qorder_pr\codex-SpiroSerach` passed after the NOMAD perovskite schema reference module; the source snapshot validator now covers `data/lib/nomad_perovskite_schema/source-manifest.json`.
- `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest discover tests -v` passed outside sandbox with 931 tests and 9 skipped after the NOMAD perovskite schema reference module and again after the readonly run recent directory selector; sandboxed `.venv` Python remained blocked by local trampoline permissions.
- `npm.cmd test` in `frontend/atomreasonx` passed with 32 Vitest tests after the readonly run recent directory selector.
- `npm.cmd run build` in `frontend/atomreasonx` passed after the readonly run recent directory selector.
- `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest tests.test_atomreasonx_contracts tests.test_atomreasonx_frontend -v` passed outside sandbox with 41 tests after the readonly run recent directory selector.
- `git diff --check`, `git diff --cached --check`, and `scripts/check-agent-hygiene.ps1` passed before the readonly run recent directory selector commit.
- `Test-Path uv.lock` was `False` before the readonly run recent directory selector commit.
- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/build-atomreasonx-spiroctl-sidecar.ps1 -RepositoryRoot D:\1-QRS\qorder_pr\codex-SpiroSerach` passed and smoke-tested `spiroctl-x86_64-pc-windows-msvc.exe` with `source-registry validate data/source_registry.json`.
- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-atomreasonx-sidecar-packaging.ps1 -RepositoryRoot D:\1-QRS\qorder_pr\codex-SpiroSerach` passed in explicit `dev_path_only` mode after the release build policy slice.
- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-v35-read-validation.ps1 -RepositoryRoot D:\1-QRS\qorder_pr\codex-SpiroSerach` passed after the release build policy slice.
- `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest tests.test_atomreasonx_sidecar_packaging -v` passed outside sandbox with 4 tests after the release build policy slice; sandboxed `.venv` Python remained blocked by local trampoline permissions.
- `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest discover tests -q` passed outside sandbox with 933 tests and 9 skipped after the release build policy slice.
- `git diff --check`, `git diff --cached --check`, `scripts/check-agent-hygiene.ps1`, and `Test-Path uv.lock` passed before the release build policy commit.
- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-atomreasonx-sidecar-packaging.ps1 -RepositoryRoot D:\1-QRS\qorder_pr\codex-SpiroSerach -RequireBundledSidecar` passed after bundled sidecar enablement.
- `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest tests.test_atomreasonx_sidecar_packaging tests.test_atomreasonx_frontend -v` passed outside sandbox with 22 tests after bundled sidecar enablement.
- `npm.cmd test` in `frontend/atomreasonx` passed with 32 Vitest tests after bundled sidecar enablement.
- `npm.cmd run sidecar:build` in `frontend/atomreasonx` passed and smoke-tested `source-registry validate`.
- `npm.cmd run sidecar:check` in `frontend/atomreasonx` passed in `bundled_external_bin` mode.
- `npm.cmd run build` in `frontend/atomreasonx` passed after bundled sidecar enablement.
- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-v35-read-validation.ps1 -RepositoryRoot D:\1-QRS\qorder_pr\codex-SpiroSerach` passed after bundled sidecar enablement.
- `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest discover tests -q` passed outside sandbox with 934 tests and 9 skipped after bundled sidecar enablement.
- `npm.cmd run tauri:build` proved the release script order by completing `sidecar:build`, `sidecar:check`, and frontend `beforeBuildCommand`; the installer build then failed at Rust compile because MSVC `link.exe` is not installed.
- `cargo fmt --check` remains environment-blocked because `cargo-fmt.exe` is not installed for `stable-x86_64-pc-windows-msvc`.
- `cargo test` remains environment-blocked by crates.io proxy access, and `cargo test --offline` reaches compilation but fails because MSVC `link.exe` is not on PATH.
- `$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./internal/sourcesnapshot ./cmd/spiroctl -v` passed for the P3 source closure readiness gate, including blocked current PubChemQC and Materials Cloud fixtures plus a synthetic PubChemQC ready manifest.
- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-v35-read-validation.ps1 -RepositoryRoot D:\1-QRS\qorder_pr\codex-SpiroSerach` passed with JSON checks proving `source-snapshot validate` accepts current fixtures while `source-closure validate` blocks PubChemQC and Materials Cloud production/scientific closure claims.
- `$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./internal/sourcesnapshot ./cmd/spiroctl -v` passed after adding machine-readable PubChemQC and Materials Cloud `source-closure requirements` reports.
- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-v35-read-validation.ps1 -RepositoryRoot D:\1-QRS\qorder_pr\codex-SpiroSerach` passed after adding JSON schema/source/status checks for the requirements reports.
- `$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./internal/sourcesnapshot ./cmd/spiroctl -v` passed after adding `schemas/source-closure-requirements.schema.json`, runtime report validation, and schema drift checks.
- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-v35-read-validation.ps1 -RepositoryRoot D:\1-QRS\qorder_pr\codex-SpiroSerach` passed after adding explicit schema contract validation for `source-closure requirements`.
- `$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./internal/materialsproject ./cmd/spiroctl -v` passed after adding the Materials Project source-provider probe contract.
- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-v35-read-validation.ps1 -RepositoryRoot D:\1-QRS\qorder_pr\codex-SpiroSerach` passed after adding `source-provider test-connection materials_project` missing-key read-only coverage.
- `npm.cmd test` in `frontend/atomreasonx` passed with 34 Vitest tests after wiring the AtomReasonX Materials Project source-provider probe command contract.
- `npm.cmd run build` in `frontend/atomreasonx` passed after the AtomReasonX probe command contract slice.
- `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest tests.test_atomreasonx_contracts tests.test_atomreasonx_frontend -v` passed outside sandbox with 41 tests after the AtomReasonX probe command contract slice; the sandboxed `.venv` Python path remained blocked by the local `uv` trampoline permission issue.
- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-v35-read-validation.ps1 -RepositoryRoot (git rev-parse --show-toplevel)` passed after the AtomReasonX probe command contract slice.
- `$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v` passed with exit code 0 after the AtomReasonX probe command contract slice; tool output was truncated, and the generated root `uv.lock` was removed.
- `git diff --check`, `git diff --cached --check`, `scripts/check-agent-hygiene.ps1`, and `Test-Path uv.lock` passed before committing the AtomReasonX probe command contract slice.
- `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest tests.test_config_command_plane -v` passed outside sandbox with 26 tests after the initial backend Materials Project probe command bridge; sandboxed `.venv` Python remained blocked by the local `uv` trampoline permission issue.
- `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest tests.test_config_command_plane -v` passed outside sandbox with 27 tests after fixing source probe idempotent replay so repeated `test_connection` requests return the original probe artifact without calling the runner again.
- `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest tests.test_config_command_plane tests.test_atomreasonx_contracts tests.test_v35_read_validation_script -v` passed outside sandbox with 52 tests after the idempotent replay fix.
- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-v35-read-validation.ps1 -RepositoryRoot (git rev-parse --show-toplevel)` passed after the backend Materials Project probe command bridge and idempotent replay fix.
- `$env:PYTHONPATH='src'; uv run python -m unittest discover tests -q` passed with 937 tests and 9 skipped after the backend Materials Project probe command bridge and idempotent replay fix; the generated root `uv.lock` was removed.
- `$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./internal/sourcesnapshot ./cmd/spiroctl -v` passed after the Materials Cloud single-record scientific closure contract, including metadata-only block, synthetic ready bundle, CLI pass report, missing evidence, unknown field, and computed=false regressions.
- `git diff --check -- .codex/skills docs/agent-collaboration-governance.md`, `scripts/check-agent-hygiene.ps1`, and `Test-Path uv.lock` passed for the agent verification workflow optimization. Broader runtime gates were intentionally omitted because the committed change was process documentation only.
- `$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./internal/sourcesnapshot -v` passed after Materials Cloud report-body closure hardening, covering schema drift, parser report `status=fail`, missing accepted fields, mismatched units, and provider loader rejection.
- `$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./internal/sourcesnapshot ./cmd/spiroctl -v` passed after Materials Cloud report-body closure hardening.
- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-v35-read-validation.ps1 -RepositoryRoot (git rev-parse --show-toplevel)` passed after Materials Cloud report-body closure hardening. No Python/frontend/full Go rerun was required because this slice only changed Go source snapshot/closure code, Go CLI fixture tests, source closure schemas, and the V35 validation script.
- `$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./internal/sourcesnapshot -v` passed after PubChemQC Python bridge report-body closure hardening, covering schema drift, failed oracle report, missing parser accepted field, and ready-snapshot loader rejection.
- `$env:GOCACHE=(Join-Path (Get-Location) '.cache\go-build'); go test -count=1 ./internal/sourcesnapshot ./cmd/spiroctl -v` passed after PubChemQC Python bridge report-body closure hardening.
- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-v35-read-validation.ps1 -RepositoryRoot (git rev-parse --show-toplevel)` passed after PubChemQC Python bridge report-body closure hardening. Broader Python/frontend/full Go gates were intentionally omitted because this slice only changed Go source snapshot/closure code, source closure schemas, and V35 schema checks; it does not change Python bridge implementation or AtomReasonX runtime code.
- `npm.cmd test` in `frontend/atomreasonx` passed with 36 Vitest tests after the Materials Project operator command transport slice.
- `npm.cmd run build` in `frontend/atomreasonx` passed after the Materials Project operator command transport slice.
- `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest tests.test_config_command_plane tests.test_atomreasonx_contracts -v` passed outside sandbox with 58 tests after review fixes for the Materials Project command transport slice; sandboxed `.venv` Python remained blocked by local `uv` trampoline permissions.
- `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest tests.test_atomreasonx_contracts -v` passed outside sandbox with 26 tests after a Rust bridge source cleanup that removed obsolete redaction helper code.
- `git diff --check`, `scripts/check-agent-hygiene.ps1`, and `Test-Path uv.lock` passed after the Materials Project command transport review fixes. Broader full-suite reruns were intentionally omitted because the post-review fixes were bounded to config command runtime, source-setting command transport contracts, Tauri bridge source policy, local secret validation, and stage status documentation.
- `cargo fmt --check` remains environment-blocked because `cargo-fmt.exe` is not installed for `stable-x86_64-pc-windows-msvc`.
- `cargo check --offline` remains environment-blocked because MSVC `link.exe` is not on PATH.
- `npm.cmd test` in `frontend/atomreasonx` passed with 40 Vitest tests after the AtomReasonX source-settings command projection slice, including out-of-order stale accepted result regression coverage.
- `npm.cmd run build` in `frontend/atomreasonx` passed after the AtomReasonX source-settings command projection slice.
- `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest tests.test_atomreasonx_contracts -v` passed outside sandbox with 27 tests after the AtomReasonX source-settings command projection slice; sandboxed `.venv` Python remained blocked by local `uv` trampoline permissions.
- Noether found a P1 stale accepted result ordering risk during review; the projection now ignores source effects with `config_version` older than the visible `source_settings.config_version`, and targeted frontend/Python reruns above covered the fix. Broader gates were intentionally omitted because the fix is UI-local TypeScript projection plus source-contract assertions only.
- `npm.cmd test` in `frontend/atomreasonx` passed with 45 Vitest tests after the workflow operator task queue slice, including every fixture workflow action, non-accepted projection rejection, duplicate task rejection, payload-poisoning hardening, and hostile artifact config sanitization.
- `npm.cmd run build` in `frontend/atomreasonx` passed after the workflow operator task queue slice.
- `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest tests.test_atomreasonx_contracts -v` passed outside sandbox with 28 tests after the workflow operator task queue slice; sandboxed `.venv` Python remained blocked by local `uv` trampoline permissions.
- Herschel found no blocking spec issues and suggested low-cost direct behavior coverage; Dalton found P1/P2 boundary hardening issues around loose artifact projection and payload-controlled operator metadata. The fix moved workflow metadata into an allowlist contract, hashes task ids instead of embedding raw idempotency keys, rebuilds safe task config, and fails closed on mismatched schema/status/queue/action/provider/effects. Targeted Vitest, build, and Python contract reruns above covered the review fixes; Dalton re-reviewed and approved the slice.

## Remaining Work

### P3 Provider Closure

1. The P3 closure-readiness gate is now machine-checkable, but real data
   closure remains open. `source-snapshot validate` proves manifest and record
   integrity; `source-closure validate` is the production/scientific admission
   gate and currently blocks PubChemQC and Materials Cloud fixtures.
   `source-closure requirements pubchemqc|materials_cloud` now reports the
   exact operator inputs/evidence still required, and
   `schemas/source-closure-requirements.schema.json` pins that report contract.
2. PubChemQC full snapshot import remains open. Do not claim Go replacement
   until dataset-size handling, parser parity, Python oracle comparison,
   identity join, checksum, license/citation, and storage policy pass the
   readiness gate. The Python oracle and parser parity reports now have
   machine-checkable bodies, but real snapshot acquisition and oracle generation
   are still required. Deferred scientific fields such as geometry, total
   energy, dipole, charge state, or software must fail closed until parser
   parity exists.
3. Materials Cloud scientific import remains open for real data, but the
   admission contract is now explicit for a single record: parser report, unit
   validation, record-specific license/citation review, checksum coverage,
   manifest-listed validation files, schema-valid report bodies, computed=true,
   metadata_only=false, and a closed scientific field allowlist are required.
   The current repository fixture remains metadata-only and closure-blocked.
4. NOMAD PERLA live archive behavior remains conservative. Rate limit,
   archive-unavailable, and schema-unrecognized cases must stay review-routed.
5. Crossref/OpenAlex and literature metadata Go parity are future slices, not
   blockers for current data-source P3.

### P4 Transport And Packaging

1. AtomReasonX now has a controlled operator settings path for configuring a
   readonly run output directory and a read-side recent directory selector.
   A native desktop directory picker remains optional, but must keep the same
   read-adapter-only boundary and must not expose executable paths or tokens.
2. Packaging preflight is executable, the release-owned Go `spiroctl` sidecar
   build policy is available, and Tauri production bundling now declares
   `bundle.externalBin = ["binaries/spiroctl"]`. Installer verification still
   requires a Rust desktop build environment with MSVC `link.exe` and `rustfmt`.
3. Keep read transport side-effect free. Config command transport is now
   separate and idempotent for source/model settings; workflow commands such as
   NOMAD sync and snapshot imports now have an explicit UI-local operator task
   queue, but execution, download, cache write, SQLite write, scoring rebuild,
   and experiment write authorization remain future slices.
4. Go must not become a second SQLite/provider-cache writer until schema
   ownership and write authorization are explicit.

### Scientific Bridge

1. Keep sklearn Gaussian-process surrogate and future BoTorch/GPyTorch work in
   Python until scientific parity exists.
2. Replace deterministic Python modules only after golden JSON, stable hash,
   error-code, and tolerance tests pass on Windows.
3. Go may validate science-bridge outputs before TypeScript or artifacts read
   them, but it must not invent scientific recommendations from raw provider
   payloads.

## Next Executable Slice

Recommended next large stage:

1. Use the P3 closure gate on a real PubChemQC full snapshot acquisition/import
   policy or a single Materials Cloud record-specific import policy.
2. This requires real dataset paths, license/citation decisions, parser parity
   fixtures, Python oracle comparison, and JSON closure reports before
   non-fixture facts are admitted.
3. Keep command transport, provider sync, scoring rebuild, cache writes,
   SQLite writes, and experiment writes out of the same slice.

Alternative if prioritizing operator workflow:

1. Promote the UI-local workflow operator task queue into a backend-owned task
   ledger with explicit write authorization, starting with positive HTL NOMAD
   sync/import admission and data-library staging. The executor must still keep
   provider sync, scoring rebuild, cache write, SQLite write, and experiment
   write surfaces separate until their contracts are reviewed.
2. Full installer verification for bundled sidecar packaging now requires the
   local Rust desktop toolchain closure: install `rustfmt` plus MSVC Build Tools
   with the C++ linker, then rerun `cargo fmt --check`, `cargo test`, and
   `npm.cmd run tauri:build`.
