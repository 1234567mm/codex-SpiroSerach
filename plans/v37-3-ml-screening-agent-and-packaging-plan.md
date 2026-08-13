# V37.3 ML Screening Agent + Desktop Packaging Plan

> Status: draft_for_approval (reference-informed)
> Date: 2026-08-12
> Source: `plans/v37-future-direction-and-task-breakdown-plan.md` (T37-09..T37-16)
> + `plans/layered-screening-platform-plan.md`
> User decisions: Tauri updater full-auto; no code signing this phase.
> Reference repos consulted (user-provided, recorded in AGENTS.md):
>   - https://github.com/esengine/DeepSeek-Reasonix (MIT, Go)
>   - https://github.com/CherryHQ/cherry-studio (AGPL-3.0, Electron)
>   - https://github.com/openai/codex (Apache-2.0, Rust)

## 1. Borrowed Experience (mapped to our tasks)

| Ref | Borrowed pattern | Where we apply it |
|-----|------------------|-------------------|
| Reasonix | Config-driven providers/agent/tools in one TOML, no hardcoded models | Already homologous (`model_provider_registry` + `config_command`); keep screening-agent config declarative, not code |
| Reasonix | executor + planner as two models in separate cache-stable sessions | Screening agent keeps analysis-model calls separate from deterministic engine steps (fast-screen/scoring stay code) |
| Reasonix | per-turn checkpoints, plan mode, permissions, workspace sandbox | Our admission ledger + `writes_authorized` + review gates already mirror this; T37-10 extends the same discipline to `run_htl_screening` |
| Reasonix | cache-aware context maintenance (stable env summary, stale-output pruning) | Agent context passed to the model is bounded: only selected candidates + provenance, never raw snapshots |
| Reasonix | Extension Protocol v1 sidecars contribute providers/UI | Long-term direction for `ScreeningModule` registry (plugins register layers); not this slice |
| Cherry Studio | Ollama / LM Studio local model support alongside cloud providers | Register a `local_llm` provider kind later (open decision from V34); not blocking V37.3 |
| Cherry Studio | Knowledge-base import workflow (files/folders/URL → vectorize → cite) | Module B follow-up for paper-vault import UI; not this slice |
| Cherry Studio | electron-builder.yml + dev-app-update.yml static release manifest | T37-15: Tauri updater static endpoints config mirrors this manifest shape |
| Codex | standalone install scripts (install.ps1) + multi-platform release archives + fallback from primary host to GitHub Releases | T37-14/15: release artifacts get SHA256SUMS + install script + updater endpoint fallback |
| Reasonix | Windows installers signed via SignPath.io free OSS certificate (SignPath Foundation) | T37-16: record as the zero-cost signing path for a later phase (user: no signing this phase) |
| Reasonix | CGO_ENABLED=0 single binary, six-target cross compile, prebuilt archives per release | spiroctl already matches; formalize release artifact checklist in T37-14 |

License note: Cherry Studio is AGPL-3.0 — we borrow architecture shapes only,
never code; all our implementation stays original.

## 2. CEPDB Dependency Adjustment

T37-10 lists T37-08 (CEPDB) as a dependency. CEPDB is deferred by the user
(2026-08-12). Decision: `run_htl_screening` data-source selection is a task
parameter (default `hopv15` + `opv_db` local snapshots, which already have
180-record HOPV15 snapshots in the ignored `snapshots/`), so CEPDB becomes an
additional selectable source later without changing the task contract.

## 3. Task Breakdown (T37-09..T37-16)

### Phase 1 — V37.3 investigation + bridge decision

- Read `surrogate.py` fully (6 BoTorch stubs) and the sklearn bridge surface
  (`model_evaluation.py`, `v4.py`) to pick the Python-side reuse point.
- Decide the Go↔Python bridge: JSON process bridge (stdin/stdout, no resident
  server) preferred; no new long-lived services. Fixture fake bridge for
  offline Go tests.
- Write the T37-09 design section (interface + provenance contract).

### Phase 2 — T37-09 ML surrogate bridge (Large) — DONE 2026-08-13

- Python `spirosearch.surrogate_bridge.py`: line-JSON stdio protocol
  (`v37.surrogate_bridge.v1`); fit/predict/uncertainty/acquisition over the
  existing `SklearnSurrogate`; provenance per response; fail-closed errors.
- Go `internal/surrogatebridge`: `ProcessBridge` (child process, env
  passthrough, large-line scanner, stderr diagnostics) + `FakeBridge` for
  offline tests; cross-process e2e against the repo venv python.
- Verified: 5 Go tests + 6 Python tests incl. real sklearn
  fit→predict→uncertainty→acquisition chain (`--extra ml`).
- Commits: `05ec941`, `db40ada`.

### Phase 3 — T37-10 / T37-11 screening agent task + artifacts (Large + Medium) — DONE 2026-08-13

- `run_htl_screening` operator task (local scope, `screening_result`
  effects); `ExecuteHtlScreening`: snapshot records → `fast-screen` HTL
  window filter → deterministic window-center ranking → `v37.screening_result.v1`
  artifact (ranked candidates with full provenance, stats, review flags).
- Explicit writes: `scoring_written` only with `--authorize-scoring-write`;
  target-exists and wrong-action fail closed.
- CLI: `spiroctl workflow-task execute --task-id --ledger --source --target
  [--authorize-scoring-write] [--module-id] [window flags]`.
- End-to-end on real data: 180-record HOPV15 snapshot → 1 hit
  (KCTYWEWDJUBVCZ, score 0.529); frontend action allowlist drift test
  updated (TS `local` scope).
- Commits: `73f9b63`, `10c924f`.

### Phase 4 — T37-12 / T37-13 screening view + schema generation

T37-12 DONE 2026-08-13: `ScreeningView` component (ranked candidates,
stats, review flags, unavailable state) mounted in AppShell;
`ScreeningResultState` contract + real fixture snapshot; 4 Vitest tests
(64 frontend green), Python contract assertion, TS build green.
Commits: `5db2ba2`, `1adbc27`, `01948fb`.

T37-13 (E1) DONE 2026-08-13: `internal/schemagen` reflection-based JSON
Schema generator (Go struct = single source of truth); `spiroctl
schema-generate screening-result` emits
`schemas/v37-screening-result.schema.json` (validated against a real
payload, 0 errors); dual drift guards — Go test regenerates and compares
checked-in schema, Python contract test asserts TS interface fields match
the generated schema exactly. Commit: `305d395`.

### Phase 5 — Packaging (T37-14/15)

Packaging app chain VERIFIED 2026-08-13: `tauri:build:app` full chain —
sidecar build (spiroctl 10.9MB, sha256 3609307a), sidecar preflight PASS,
MSVC toolchain auto-detected, frontend build, Rust release compile
(`Built application at ...\atomreasonx.exe`, 3.1MB). Direct invocation
exit=0 (npm wrapper exit 1 was a PowerShell stderr artifact).
T37-14 MSI bundling still needs WiX (external); T37-15 updater integration
pending (full-auto decision recorded).

CEPDB status (completed 2026-08-13): dump imported (3.32B rows), analysis
layer switched to DuckDB+Parquet (measured ~21x faster, ~59x smaller than
SQLite intermediate; see `plans/cepd-data-layer-architecture.md`); HTL
subset extracted (1,711,218 candidates, B3LYP/TZVP window) and verified
end-to-end through `run_htl_screening` (admitted → executed → artifact
with scoring-write authorization, 1,711,218 records processed).

- Run `npm.cmd run tauri:build:app` (sidecar pack + frontend build + Rust
  release, no MSI) to prove the full chain (skill `atomreasonx-tauri-msvc`).
- WiX acquisition + `tauri:build` MSI bundling; install/uninstall smoke check
  recorded. WiX download may need user network help (skill has escalation
  rules).
- Tauri updater integration (full-auto, user decision): generate updater
  signing keypair, configure `tauri.conf.json` updater endpoints (static
  release manifest), publish-version workflow; fallback endpoint per the
  Codex multi-host pattern.
- T37-16 code signing: NOT this phase. Record SignPath.io free OSS signing as
  the future zero-cost path (borrowed from Reasonix) + leave a signing-procedure
  doc slot.

### Phase 6 — Full verification + archive

- Full gates: `go test ./...`, Python full suite, frontend test/build, hygiene.
- Release artifact records (MSI path/hash, install/uninstall results, updater
  manifest, SHA256SUMS) in the run archive.
- Update `layered-screening-platform-plan.md` + V37 plan status; write the
  V37.3/V37.5 run archive.

## 4. Open Decisions (resolve when reached)

- Local Ollama provider kind: add now or later (not blocking).
- Updater hosting: static file hosting vs GitHub Releases as primary endpoint.
- Screening view scope: minimal table vs full compare mode in first cut.

Effort estimate: Phase 1-4 ≈ 2 Large + 3 Medium ≈ 12-20 engineering days;
Phase 5 depends on WiX network and MSVC toolchain checks.
