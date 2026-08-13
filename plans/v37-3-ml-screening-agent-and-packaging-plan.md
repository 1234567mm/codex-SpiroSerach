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

### Phase 2 — T37-09 ML surrogate bridge (Large)

- Python: surrogate execution entry — sklearn GP fit/predict JSON interface
  returning predictions with provenance (model version, train-set hash,
  feature row); keeps `SURROGATE_EXCLUDED_FEATURE_KEYS` governance.
- Go: bounded bridge caller + `PropertyPredictionReport` contract; fake-bridge
  tests offline.
- Acceptance: Go → Python predict returns provenance; Python unit tests, Go
  bridge tests, cross-process end-to-end test.

### Phase 3 — T37-10 / T37-11 screening agent task + artifacts (Large + Medium)

- `run_htl_screening` action in the operator task queue: admission gates,
  explicit `writes_authorized`, data-source selection (default hopv15/opv_db).
- Execution chain: snapshot records → `fast-screen` HTL windows → surrogate
  predictions → `ScoringView` ranking → screening result artifacts.
- T37-11: `v37.screening_result.v1` schema (candidate list + per-candidate
  provenance back to source records) + validation tests.
- Acceptance: admitted task executes end-to-end and emits the candidate-list
  artifact with full provenance.

### Phase 4 — T37-12 / T37-13 screening view + schema generation (2 Medium)

- AtomReasonX Screening view: score-ranked candidates, per-fact provenance,
  review blockers, Spiro-OMeTAD compare mode; fixture + component tests.
- E1: Go structs → JSON Schema → TypeScript types generation replacing
  hand-maintained pairs; drift tests stay green.

### Phase 5 — Packaging (T37-14/15; T37-16 deferred by user)

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
