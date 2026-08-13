# Layered Screening Platform Plan — Architecture, Module Tasks, Data Acquisition

> Status: approved_architecture / awaiting_cepdb_download
> Date: 2026-08-12
> Baseline HEAD: `8f351c6` (docs: verify V37.1 delivery and plan V37.2 slice)
> Trigger for next wave: user confirms local CEPDB download finished
> Source of truth: this document + `plans/v37-future-direction-and-task-breakdown-plan.md`
> + `plans/v37-2-nomad-openapi-alignment-and-cepdb-snapshot.md`

## 1. Confirmed Overall Architecture (user-approved, 2026-08-12)

1. **Layered screening platform**: screening is organized by device layer
   (htl / etl / perovskite / electrode / interface). Spiro-OMeTAD replacement
   screening is ONE registered module of the `htl` layer, replaceable and
   extensible — not a core hard-coded feature.
2. **Classified knowledge base**: all open data-source interfaces live inside
   the shippable desktop app as a knowledge base grouped by category
   (`source_family`, `acquisition_mode`, trust/curation status); local
   `data/lib` is the on-disk store (git tracks only skeleton + manifests).
3. **Fast screening + check backend**: backend supports fast property-range
   filtering (band_gap / HOMO / LUMO windows) with check gates
   (PASS/DEFER/REJECT) and audit trails.
4. **Codex-like model integration**: the platform links mainstream model
   endpoints AND user-configured third-party endpoints for data analysis;
   models are execution infrastructure, never evidence sources.
5. **Shippable desktop software** as the final deliverable.

Existing architecture boundaries (AGENTS.md) remain: providers emit
`ProviderResponse` facts, `EvidenceQualityPolicy` is the admission gate to
`ScoringView`, review items block silently bad data, model outputs never
enter scoring directly.

## 2. Module Task Breakdown (A–F)

### A. Layered Screening Framework (Large) — first to implement — DONE 2026-08-12

Delivered in `c91bfae`:
- `src/spirosearch/screening_modules.py`: `DeviceLayer` enum (htl/etl/
  perovskite/electrode/interface), `ScreeningModule` parameterized profile,
  validation (monotonic windows, weights sum to 1), registration registry
  (`register/get/list`), sanitized summary for read surfaces, built-in ETL
  example module (`sn02_replacement_conventional_nip_v1`, approximate
  scientific parameters for engine-generality proof).
- `screening_policy.py`: `ScreeningPolicy(module=...)` — module supplies
  windows/weights/band-gap filters; default no-arg construction keeps the
  historical HTL behavior via registered `spiro_replacement_conventional_nip_v1`
  (single-sourced from the HTL constants); `ScreeningGateResult` carries
  `module_id`/`layer`; optional `band_gap_max` hard filter (`BAND_GAP_TOO_HIGH`).
- Schema: screening-input-view candidate gains additive `module_id`/`layer`.
- Tests: `tests/test_screening_modules.py` (14) + existing suites green.

Remaining sub-items for A (later wave):
- screening entry (`--layer <name>`) wiring into `ScreeningInputViewArtifactEmitter`
  and workflow-task/CLI surfaces (framework API is ready; emitter keeps HTL default).
- More registered modules per layer as research needs them.

### B. Knowledge Base Wiring (Medium)

- Backend: category browse/search API by `source_family` / `acquisition_mode`
  (read side, via Go readonly path).
- Frontend: AtomReasonX Knowledge Library view switches from fixture to real
  read state; shows per-category sources, snapshot status, fixture vs missing.
- Show local import reality: `data/lib` fixtures (git) vs downloaded raw data
  and `snapshots/` imports (local only).

### C. Fast Screening Check Backend (Medium) — slice 1 DONE 2026-08-12, slice 2 pending

Slice 1 delivered (fast filter):
- `internal/fastscreen`: read-only window filter over local snapshot records
  (homo/lumo/band_gap ranges, nil = unconstrained), audit counts for missing
  and out-of-window records (gaps never silently dropped), benchmark
  1000 records ≈ 93 µs/op (< 5 ms initial threshold).
- `spiroctl fast-screen <source-dir> [--homo-min/max] [--lumo-min/max]
  [--band-gap-min/max] [--json]` — human report or JSON hits, validated
  windows, real `data/lib/hopv15` fixture end-to-end test.
- 6 package tests + 5 CLI integration tests; `go test ./...` green.

Slice 2 (pending, module C-2): promotion writer unblock
- `scoring_written` explicit authorization moves snapshot facts into the
  scoring path (local backend SQLite + ScoringView-visible), replacing the
  current `readiness_only` promotion. Go promote command + Python scoring
  admission bridge; acceptance = local snapshot → fast filter → scoring view
  end-to-end test.

### D. Model Interface Layer Completion (Medium)

- Settings UI wiring: provider choice, third-party `base_url` / model id / key
  config via `local_config` + `config_command` (no secret leakage).
- Enable model-assisted analysis chain (literature/claim extraction) behind an
  explicit authorization switch, admission-gated.
- Keep the C1 screening-agent hook point (V37.3: `run_htl_screening` agent task
  analyzes candidates via models, models never rank directly).

### E. Data Source Completion (Large; acquisition per §4)

- V37.2: NOMAD official OpenAPI alignment (typed queries + review-promotion
  paths) — planned in `plans/v37-2-nomad-openapi-alignment-and-cepdb-snapshot.md`.
- CEPDB 2.3M-molecule snapshot: local filter to HTL subset (§4, awaiting user
  download).
- PubChemQC B3LYP subset via candidate-CID-driven fetch (no full download).
- V38: JARVIS dual band gap (NIST registration), PERLA (blocked on public
  dataset release).

### F. Desktop Delivery (Medium, partially externally blocked)

- WiX/MSI installer verification (blocked: WiX toolset acquisition),
  auto-update strategy, sidecar signing.
- E1: Go structs → JSON Schema → TypeScript type generation.

Effort: A+B+C+D+E ≈ 15–25 engineering days; F blocked on WiX.
Fastest demonstrable closed loop: A + C + B using HOPV15/OPV-DB + the three
Go live providers, then E widens data.

## 3. Data Acquisition Strategy (per source class)

| Mode | Sources | How |
|---|---|---|
| A: remote filtered query | NOMAD, PubChem, Materials Project, OQMD, JARVIS | query with HTL windows; cache hits locally; never download full DB |
| A+: candidate-driven subset | PubChemQC (86M, >100GB) | derive candidate CID list from PubChem, fetch only those CIDs |
| B: one-shot full dump → local filter → keep subset | CEPDB (2.3M, SQL dump, no filter API) | download once, import SQLite, filter to HTL window, keep subset; archive original dump |
| C: full local (small) | HOPV15 (16.5MB, downloaded), OPV-DB | already local |

Storage decision (user-approved): `data/lib` IS the local store. Git tracks
skeleton/manifests/fixtures only; `.gitignore` covers raw dumps
(`*.tbz`, `*.tar.bz2`, `*.xz`, `*.sqlite`, `*.data`, `*.zip`, …) plus
`raw/`, `snapshots/`, `cache/`, `downloads/` subdirectories. No migration
needed. Quark drive = cold archive backup only, never a daily transfer hop
(agent cannot access it directly).

## 4. CEPDB Download Information (user downloads; agent imports after)

- Official page: `https://www.matter.toronto.edu/basic-content-page/data-download`
- Recommended file: Database 2, 2013 —
  `https://www.cs.toronto.edu/matterlab/cep/cepdb_2013-06-21.sql.tbz`
- Optional geometry archive: `xyz_archive_2013-03-22.tbz`
- Place the downloaded `.tbz` (keep filename, do not extract) at:
  `D:\1-QRS\qorder_pr\codex-SpiroSerach\data\lib\cepd\`
- Size estimate: 2–5 GB compressed, 10–20 GB uncompressed SQL text; reserve
  disk accordingly; use a resumable downloader.
- Note: agent-side TLS probe of cs.toronto.edu failed (exit 35) — if the
  browser also fails, retry from the official page or another network.

## 5. Next-Wave Trigger And Order

CEPDB status: **deferred by user (2026-08-12)** — download too slow; revisit
later. CEPDB no longer gates the remaining modules.

Order:

1. ~~CEPDB import slice~~ deferred (user decision).
2. ~~Module A: layered screening framework~~ DONE (`c91bfae`).
3. Module C: fast filter backend + promotion writer (next).
4. Module B: knowledge base wiring.
5. V37.2 T37-05..07 NOMAD alignment (per v37-2 slice plan).
6. Module D: model interface completion.

## 6. Open Decisions (ask when reached)

- CEPDB: merge DB1 2012 + DB2 2013 or use DB2 only (decide at import slice).
- CEPDB: include xyz geometry archive in scope or defer.
- Which second layer to register as the example module in A (ETL vs
  perovskite) — sensible default: ETL.
- Quark drive archiving of the original CEPDB dump is the user's call.
