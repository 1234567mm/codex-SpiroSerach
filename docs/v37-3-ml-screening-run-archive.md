# V37.3 ML Screening Agent — Run Archive

> Date: 2026-08-13
> Branch: main
> Source: `plans/v37-3-ml-screening-agent-and-packaging-plan.md`
> Integration HEAD: `305d395` (T37-13) + packaging verification commit
> Baseline: `c4aeb80` (plan) / `6569b25` (phase 1 design)

## 1. Delivered

| Slice | Delivery | Evidence |
|-------|----------|----------|
| Phase 1 | Bridge design (stdio long-lived process bridge) | `6569b25` design doc |
| T37-09 | surrogate stdio bridge (Go ProcessBridge/FakeBridge + Python surrogate_bridge) | `05ec941`, `db40ada`; 5 Go + 6 Python tests; real sklearn fit→predict→uncertainty→acquisition chain; cross-process e2e |
| T37-10/11 | `run_htl_screening` operator task + `v37.screening_result.v1` artifact | `73f9b63`, `10c924f`; 4 execution tests; real HOPV15 end-to-end (180 records → 1 hit, score 0.529) |
| T37-12 | AtomReasonX ScreeningView + contract + fixture | `5db2ba2`, `1adbc27`, `01948fb`; 64 Vitest green |
| T37-13 | Go→JSON Schema generation + TS drift guard | `305d395`; schemagen (3 tests), generated schema validated 0 errors, dual drift guards |
| Packaging | tauri:build:app full chain verified | sidecar 10.9MB + preflight PASS + Rust release `atomreasonx.exe` 3.1MB; direct invocation exit=0 |

## 2. CEPDB Data Layer (T37-08 completed alongside)

- 49.28GB SQL dump imported: 332,347,818 rows across 10 tables (2h15m).
- Analysis layer decision (measured): DuckDB + zstd Parquet — window query
  0.90s vs SQLite 19.2s (~21x), 0.56GB vs 33GB (~59x), counts identical
  (1,711,218). Doc: `plans/cepd-data-layer-architecture.md`.
- HTL subset: B3LYP/TZVP single point, Hartree→eV, HTL window
  (homo -5.6~-5.0, lumo -2.6~-1.8, gap≥2.0 eV) → 1,711,218 candidates
  (`data/lib/cepd/snapshots/htl-subset-v1/`, 576MB records.json).
- Verified end-to-end: `run_htl_screening` admitted → executed →
  `screening_result_written` with `--authorize-scoring-write`
  (scoring_written=true), 1,711,218 records processed, review_required=false.
- Imports/extraction tooling: `cepd_import.py`, `cepd_sqlite_import.py`
  (line-based 4.3MB/s), `cepd_subset.py` (inspect/extract).

## 3. Verification Gates

- `go test ./...` — all packages green (incl. new schemagen/surrogatebridge).
- Python full suite: all pass except the pre-existing
  `test_live_enrichment_uses_cache_before_fetching_provider` (reproduced on
  clean HEAD before this wave; unrelated to V37.3 changes).
- Frontend: 64 Vitest tests green, `tsc && vite build` green.
- Packaging: `tauri:build:app` chain PASS (sidecar build + preflight +
  MSVC + Rust release). Note: npm wrapper reported exit 1 on stderr
  informational output; direct invocation exit=0, artifacts complete.
- Repository agent hygiene: PASS (uv.lock removed after runs).

## 4. Pitfalls & Decisions

- SQLite window queries needed a covering index (modelchem + homo/lumo/gap);
  still 19s → DuckDB columnar selected by measurement, not assumption.
- CEPD energy values are Hartree (×27.2114 → eV); best B3LYP single point is
  `BP86/SVP//B3LYP/TZVP` (4.99M rows).
- `data_molgraph.inchi_str` is empty for all rows; SMILES + mol_graph_id are
  the identity.
- PowerShell `@'...'@` here-strings do not interpolate variables; python -c
  with nested quotes is fragile — use temp script files.
- gofmt on Windows can flip CRLF → LF in unchanged files (revert before
  commit to avoid noise).
- `.gitignore` extended: `*.sqlite3`, `*.sqlite3-shm/wal`, `*.tbz` (already),
  sidecar binaries remain ignored.

## 5. Remaining Work

- Install/uninstall smoke test of the produced installers (operator action —
  modifies the system, requires admin; no code signing this phase per user
  decision, SignPath free-OSS path recorded for later).
- First formal release: configure `TAURI_SIGNING_PRIVATE_KEY(_PASSWORD)` in
  GitHub Secrets and publish `latest.json` + `.sig` artifacts via
  `release.yml` (tag v*).
- Frontend update UI (check-updates entry / preview channel toggle) deferred;
  the updater mechanism layer (plugin, keypair, endpoints, signing env) is
  complete.
- Model-assisted extraction stays behind `model_assisted_authorized`
  (fail-closed); C1 screening-agent model analysis hook is the bridge entry.
- CEPDB SQLite intermediate (33GB) can be removed once Parquet is the
  confirmed analysis layer.

## 6. Packaging Closure (T37-14/15 completed 2026-08-13)

- T37-15 updater: `tauri-plugin-updater` registered, signing keypair in the
  user profile (never committed), `tauri.conf.json` updater config (pubkey +
  GitHub Releases latest.json endpoint + passive install + createUpdaterArtifacts),
  `release.yml` signing env. Commit `8481ade`.
- T37-14: `tauri build` produced both Windows installers with updater
  signatures — `bundle\msi\AtomReasonX_0.1.0_x64_en-US.msi` (7MB, +.sig) and
  `bundle\nsis\AtomReasonX_0.1.0_x64-setup.exe` (5.4MB, +.sig). WiX/NSIS are
  Tauri's cached build tools under `%LOCALAPPDATA%\tauri\` (not system PATH;
  no `wix` command exists — tools are `light.exe`/`makensis.exe`). NSIS was
  pre-seeded into the cache because Tauri's own download step exceeded its
  global timeout; subsequent builds reuse the cache. Local signing requires
  `TAURI_SIGNING_PRIVATE_KEY` = private key CONTENT (not path) +
  `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`.
- Deferred: installer smoke test (operator), NSIS retry not needed.
