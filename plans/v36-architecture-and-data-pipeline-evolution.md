# V36 Architecture And Data Pipeline Evolution Plan

> Status: draft_planning  
> Date: 2026-07-25  
> Previous phase: V35 (data source Go+TypeScript migration, merged to main)  
> Scope: next-phase architecture upgrade beyond data-source migration

## Phase Summary

V35 delivered the Go+TypeScript data source architecture layer: all 7 feasible
external providers now have Go shadow clients with typed ProviderResponse
contracts, and the AtomReasonX workbench can discover, admit, execute, and
restore workflow tasks through a read/command boundary. Source closure
readiness gates are machine-checkable.

V36 transitions from *shadow readiness* to *production activation*: promoting
accepted snapshots through the closure pipeline, integrating new public
datasets identified in V35 research, and adding ML/AI agent workflows for
autonomous HTL screening.

## Track A: Production Activation (P0)

### A1. Closure Promotion Pipeline

Current state: `source-closure validate` blocks every non-fixture snapshot.
Next step: add `source-closure promote` to move admitted, validated, and
review-resolved snapshots from quarantine to provider cache, SQLite/local
backend, scoring, and experiment-readiness.

Required sub-steps:

- **A1.1** `spiroctl source-closure promote` CLI command that validates
  readiness, checks authorization scope, and moves snapshot data into the
  next pipeline stage.
- **A1.2** Schema contract: `operator-task-promotion` with explicit writer
  authorization fields (`provider_cache_written`, `local_backend_written`,
  `scoring_written`, `experiment_written`).
- **A1.3** Go writer integration: extend `nomadperla.ExecutionPlan` and
  `workflowtask.Ledger` to accept promotion evidence.
- **A1.4** TypeScript workbench surface: show promotion state per task row
  (`promotion_blocked`, `promoted_to_cache`, `promoted_to_scoring`).

### A2. Live Provider Enablement

Current state: Materials Project and PubChem have `go_shadow_ready` clients
but Python remains the live provider runtime.

Next step: enable Go as the live provider executor for selected sources,
starting with PubChem identity lookup (no API key, lower risk).

- **A2.1** PubChem Go live provider: switch from test transport to real HTTP
  with the existing rate limiter, cache integration, and ProviderResponse
  contract.
- **A2.2** Materials Project Go live provider: add API key management through
  the existing source settings/key store, then route live lookups through Go.
- **A2.3** Python bridge deprecation: keep Python as oracle reference, mark
  Python provider calls as deprecated for migrated sources.

### A3. NOMAD Official API Migration

Current state: Go NOMAD client uses the v1 REST-style API paths
(`/entries/query`, `/entries/archive/query`) but has custom query building.

Next step: align with the official NOMAD OpenAPI specification, using
documented endpoints and schema from the API analysis GUI.

- **A3.1** Fetch the official NOMAD OpenAPI spec from
  `https://nomad-lab.eu/prod/v1/api/v1/openapi.json` and compare against
  current Go query/archive builders.
- **A3.2** Replace custom `nomadperla.SearchBody` with spec-aligned query
  structs, preserving the existing ProviderResponse contract.
- **A3.3** Add explicit review-promotion paths for rate-limited,
  archive-unavailable, and schema-unrecognized cases (currently mixed into
  execution code).

## Track B: New Data Source Integration (P1)

V35 research identified several high-value public datasets.

### B1. CEPDB (Harvard Clean Energy Project)

- **Scale**: 2.3M OPV molecules, HOMO/LUMO/gap at B3LYP/6-31G(d) level
- **License**: academic use, publicly available
- **Integration**: local snapshot importer under `data/lib/cepd/` following
  the HOPV15/OPV-DB pattern
- **Value**: largest OPV-specific molecular property dataset, direct HTL
  candidate screening support
- **Data source**: SQL dump at `matter.toronto.edu` + XYZ archive

### B2. PubChemQC B3LYP/6-31G* (86M molecules)

- **Scale**: 86M molecules, covering 94% of PubChem compounds
- **License**: CC BY 4.0
- **Integration**: extend existing `internal/pubchem/` client or create
  `internal/pubchemqc/` Go reader; local snapshot for queried subsets
- **Value**: most comprehensive computed HOMO/LUMO/gap dataset; SpiroSearch
  can query by CID range for targeted HTL candidate screening
- **Data source**: `nakatamaho.riken.jp` server

### B3. OQMD Band Gap API

- **Scale**: 1.41M materials
- **License**: CC BY 4.0
- **Integration**: Go REST client at `internal/oqmd/` following the
  `internal/materialsproject/` pattern
- **Value**: direct `band_gap` API filtering; complements Materials Project
  for inorganic HTL and contact layer screening
- **API**: `oqmd.org/oqmdapi/formationenergy?filter=band_gap>1`

### B4. JARVIS (NIST) Dual Band Gap

- **Scale**: 80K+ materials
- **License**: NIST open data (registration required)
- **Integration**: Go REST/OPTIMADE client
- **Value**: two band gap values (OptB88vdW + TB-mBJ) for cross-validation
- **API**: OPTIMADE REST API

## Track C: ML/AI Agent Workflow (P2)

### C1. Autonomous HTL Screening Pipeline

Current state: SpiroSearch finds Spiro-OMeTAD replacements through manual
data source querying and scoring.

Next step: add an ML/AI agent that can:
- Query CEPDB/PubChemQC/Perovskite Database for HTL candidates
- Filter by computed HOMO/LUMO/gap ranges matching Spiro-OMeTAD-like targets
- Rank candidates using the existing `ScoringView` and `EvidenceQualityPolicy`
- Generate review-ready candidate summaries

Required:
- **C1.1** ML surrogate model adapter: Go wrapper around Python sklearn
  GP/BoTorch surrogate for property prediction
- **C1.2** Agent workflow task: new `run_htl_screening` action in the
  operator task queue, with explicit `writes_authorized` and data source
  selection
- **C1.3** Screening result artifacts: structured candidate list with
  provenance back to source records

### C2. PERLA Integration

The PERLA dataset (Shabih et al., arXiv:2601.17807, 2026) covers post-2021
PSC device data extracted via LLM + physics validation. This fills the gap
left by the Perovskite Database Project (which stopped at 2021).

- Monitor PERLA for public dataset release
- When available: add as `data/lib/perla/` local snapshot following
  Materials Cloud metadata pattern
- HTL coverage: expected to include SAM-based HTLs (MeO-2PACz etc.)

## Track D: Operator Workflow Refinement (P2)

### D1. AtomReasonX Screening View

Current state: AtomReasonX has workflow task queue, execution, restore, and
6-state handoff model.

Next step: add a dedicated Screening view that shows:
- Candidate HTL materials ranked by score
- Source provenance per fact (which provider, which snapshot)
- Review blockers and resolution status
- Compare mode: side-by-side Spiro-OMeTAD vs candidate metrics

### D2. Desktop Packaging

- **WiX/MSI installer**: acquire WiX toolset, verify full installer build
  path (blocked since V35)
- **Auto-update**: decide on update strategy for the Tauri desktop app
- **Sidecar signing**: code signing for Windows/macOS Go sidecar binary

## Track E: Cross-Cutting (P3)

### E1. Go -> TypeScript Schema Generation

Current state: Go structs and TypeScript types are hand-maintained in
parallel, with drift detection tests.

Next step: add JSON Schema generation from Go structs, then generate
TypeScript types from schemas, reducing drift risk and manual duplication.

### E2. Python Bridge Deprecation Tracking

For each source that reaches `go_owned` status, mark the corresponding
Python provider, cache, sync job, and test as deprecated. Keep them as
oracle references until removed in a later cleanup phase.

### E3. Performance Baseline

Benchmark current Go read/validation path throughput:
- `internal/providercache`: record lookup latency
- `internal/readonlyserver`: envelope delivery
- `cmd/spiroctl`: CLI command startup time
- Set target thresholds for V37 optimization

## V36 Priority Matrix

| Item | Track | Effort | Impact | Dependencies |
|------|-------|--------|--------|-------------|
| A1 Closure promotion | A | Medium | High | V35 closure gates |
| A2 PubChem Go live | A | Small | Medium | V35 PubChem client |
| A3 NOMAD API alignment | A | Medium | High | OpenAPI spec fetch |
| B1 CEPDB integration | B | Medium | High | Dataset download |
| B2 PubChemQC B3LYP | B | Medium | High | Dataset access |
| B3 OQMD Go client | B | Small | Medium | None |
| B4 JARVIS Go client | B | Small | Low | NIST registration |
| C1 HTL screening agent | C | Large | Very High | A1, B1, B2, sklearn bridge |
| C2 PERLA integration | C | Small | Medium | Dataset release |
| D1 Screening view | D | Medium | High | A1, C1 |
| D2 Desktop packaging | D | Medium | Medium | WiX acquisition |
| E1 Schema generation | E | Small | Medium | None |
| E2 Python bridge tracking | E | Small | Low | A2 |
| E3 Performance baseline | E | Small | Low | None |

## Recommended First Slice

**A1 + B3**: Closure promotion CLI + OQMD Go client

Rationale:
- A1 unlocks the entire closure pipeline that V35 prepared
- B3 is the smallest new data source (REST API, no dataset download needed)
- Both are Go work, building on V35 patterns
- Independent of real-dataset availability for PubChemQC/CEPDB

Alternative: **C1** (HTL screening agent) if ML workflow is the priority.

## Timeline Estimate

```
V36.1 (P0): Closure promotion + OQMD client + PubChem Go live
V36.2 (P1): CEPDB snapshot + NOMAD API alignment
V36.3 (P1): HTL screening agent prototype
V36.4 (P2): Screening view + PubChemQC B3LYP integration
V36.5 (P2): Desktop packaging + PERLA + schema generation
```
