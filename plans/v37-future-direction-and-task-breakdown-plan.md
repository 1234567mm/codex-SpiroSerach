# V37 Future Direction And Task Breakdown Plan

> Status: active_planning  
> Date: 2026-08-12  
> Previous phase: V36 (active; first slice A1+B3 and V36.1 delivered, closure pending)  
> Source: 09 project progress review (`plans/qorder_plan/09-project-progress-and-direction-review-2026-08-12.md`)  
> Scope: V36 closure prerequisites, V37 milestone task breakdown, V38+ direction

## Phase Summary

V35 delivered the Go+TypeScript architecture layer and V36 delivered the first
production-activation slice (closure promotion CLI + OQMD client + local source
closure). The project stands at the shadow-readiness → production-activation
transition. This plan:

1. defines the V36 closure prerequisites that must land before V37 work is
   admitted;
2. breaks V37 into five milestones sized by task load (Small/Medium/Large per
   the roadmap §6.2 ticket-size rules);
3. records V38+ directions that stay admission-gated.

## 1. V36 Closure Prerequisites (before V37.1)

These items must close before V37 implementation tickets are admitted. They are
small (document/verification work plus a bounded Go/TypeScript slice) but they
are the difference between "V36 half-done" and "V36 closed".

| ID | Item | Effort | Owner domain | Acceptance evidence |
|----|------|--------|--------------|---------------------|
| C0-1 | V36 A1 writer authorization fields verified | Small | Go + schema | `operator-task-promotion` schema shows all four writer fields (`provider_cache_written`, `local_backend_written`, `scoring_written`, `experiment_written`) with a passing schema-drift test |
| C0-2 | V36 A1 TypeScript promotion surface | Small | TypeScript | Workbench task row renders `promotion_blocked` / `promoted_to_cache` / `promoted_to_scoring` from backend state, frontend fixture updated |
| C0-3 | band_gap_ev screening-eligibility policy decision | Small | Science doc | Decision document records how missing `band_gap_ev` affects screening eligibility (admit-with-review vs block); closes the 5-audit open item |
| C0-4 | V36 closure document + closure HEAD SHA | Small | Doc | `plans/v36-...closure.md` records closure evidence and integration HEAD SHA, V36 plan Status: closed |

Effort note: C0-1..C0-4 together are one Small-to-Medium slice (roughly 2–4
engineering days) and can be executed as a single V36.2 closure slice.

## 2. V37 Milestone Breakdown (by task load)

Task size rules (roadmap §6.2): Small ≤1 day, Medium 2–3 days, Large 4–5 days.
Work larger than 5 days is split. WIP: one version in implementation; next
version audit/spec only.

### V37.1 — Production Activation: Live Providers + Performance Baseline (P0)

Focus: make Go the live executor for the two lowest-risk providers and give the
Go read/validation path a measurable baseline.

| ID | Task | Size | Depends on | Acceptance evidence |
|----|------|------|-----------|---------------------|
| T37-01 | PubChem Go live provider (A2.1) | Medium | C0-1 | Identity lookup switches from test transport to real HTTP with rate limiter, provider cache integration, ProviderResponse contract; Python path marked deprecated for PubChem |
| T37-02 | Materials Project Go live provider (A2.2) | Medium | T37-01 | API key managed through source settings/key store; live lookups route through Go; Python path marked deprecated |
| T37-03 | E3 performance baseline | Small | — | `internal/providercache` lookup latency, `internal/readonlyserver` envelope delivery, `spiroctl` startup time benchmarked; thresholds recorded for V37 optimization |
| T37-04 | E2 Python bridge deprecation tracking start | Small | T37-01, T37-02 | Migrated sources marked deprecated in Python provider/cache/sync/tests with oracle-reference note |

V37.1 size: ~1 Medium + 2 Small + 1 Small ≈ Medium. Impact: High.

### V37.2 — NOMAD Official API Alignment + CEPDB Snapshot (P1)

Focus: align the NOMAD Go client with the official OpenAPI spec, and bring the
largest OPV molecular dataset (CEPDB, 2.3M) into the local snapshot pipeline.

| ID | Task | Size | Depends on | Acceptance evidence |
|----|------|------|-----------|---------------------|
| T37-05 | Fetch and diff NOMAD OpenAPI spec (A3.1) | Small | — | `openapi.json` from `nomad-lab.eu/prod/v1/api/v1/openapi.json` compared against current Go query/archive builders; gap list recorded |
| T37-06 | Replace `nomadperla.SearchBody` with spec-aligned query structs (A3.2) | Large | T37-05 | Go client uses documented endpoints/schema; ProviderResponse contract unchanged; parity tests pass |
| T37-07 | Review-promotion paths for rate-limited/archive-unavailable/unrecognized cases (A3.3) | Medium | T37-06 | Explicit review/blocking paths replace mixed-in execution code |
| T37-08 | CEPDB local snapshot importer (B1) | Large | — | `data/lib/cepd/` importer following HOPV15/OPV-DB pattern; checksum/license/citation gates; 2.3M-record subset fixture test |

V37.2 size: 1 Large + 1 Large + 1 Medium + 1 Small ≈ Large. Impact: High.

### V37.3 — ML/AI Autonomous HTL Screening Prototype (P1)

Focus: first ML/AI agent workflow — query datasets, filter by Spiro-OMeTAD-like
HOMO/LUMO/gap targets, rank through `ScoringView`, emit review-ready summaries.

| ID | Task | Size | Depends on | Acceptance evidence |
|----|------|------|-----------|---------------------|
| T37-09 | ML surrogate adapter (C1.1): Go wrapper around Python sklearn/BoTorch surrogate | Large | C0-1 | Go calls the Python surrogate through the bounded bridge; property prediction returns with provenance |
| T37-10 | `run_htl_screening` agent workflow task (C1.2) | Large | T37-08, T37-09 | New action in operator task queue with explicit `writes_authorized` and data-source selection; admission gates apply |
| T37-11 | Screening result artifacts (C1.3) | Medium | T37-10 | Structured candidate list with provenance back to source records; schema + validation tests |

V37.3 size: 2 Large + 1 Medium ≈ Large. Impact: Very High.

### V37.4 — Screening View + Schema Generation (P2)

Focus: operator-facing screening view in AtomReasonX, and removing the
hand-maintained Go↔TS contract duplication.

| ID | Task | Size | Depends on | Acceptance evidence |
|----|------|------|-----------|---------------------|
| T37-12 | AtomReasonX Screening view (D1) | Medium | T37-11 | Candidate HTL ranked by score; per-fact provenance; review blockers; compare mode Spiro-OMeTAD vs candidate |
| T37-13 | Go→JSON Schema generation (E1) | Medium | — | Schemas generated from Go structs; TypeScript types generated from schemas; drift tests pass |

V37.4 size: 2 Medium ≈ Medium. Impact: High.

### V37.5 — Desktop Packaging Closure (P2)

Focus: finish the release path that has been blocked since V35.

| ID | Task | Size | Depends on | Acceptance evidence |
|----|------|------|-----------|---------------------|
| T37-14 | WiX/MSI installer verification (D2) | Medium | WiX toolset acquisition (external) | Full installer build path verified; MSI installs/uninstalls cleanly |
| T37-15 | Auto-update strategy decision + implementation (D2) | Medium | T37-14 | Update mechanism chosen and implemented for the Tauri desktop app |
| T37-16 | Sidecar code signing for Windows/macOS (D2) | Medium | T37-14 | Signed Go sidecar binaries pass platform checks |

V37.5 size: 3 Medium ≈ Medium. Impact: Medium. External dependency: WiX.

## 3. V37 Timeline Estimate

```
V36.2 (P0, pre-V37): V36 closure prerequisites C0-1..C0-4 (2-4 days)
V37.1 (P0): PubChem/MP Go live + performance baseline + deprecation tracking
V37.2 (P1): NOMAD OpenAPI alignment + CEPDB snapshot
V37.3 (P1): HTL screening agent prototype
V37.4 (P2): Screening view + schema generation
V37.5 (P2): Desktop packaging closure (WiX-dependent)
```

## 4. V38+ Direction (admission-gated)

These are not scheduled versions. Each requires a proposal tied to quantitative
evidence (per roadmap §9).

| Direction | Track | Gate | Notes |
|-----------|-------|------|-------|
| JARVIS dual band gap (B4) | V36 Track B | NIST registration + OPTIMADE client | 80K+ materials, two band gap values for cross-validation |
| PERLA integration (C2) | V36 Track C | Public dataset release (arXiv:2601.17807) | Post-2021 PSC data, SAM-based HTL coverage |
| PubChemQC B3LYP subset (B2) | V36 Track B | Dataset access (`nakatamaho.riken.jp`) | 86M molecules, query by CID range |
| Production knowledge graph | Parked | New proposal + evidence | Not automatically authorized |
| GNN / generative property model | Parked | New proposal + evidence | Needs model admission criteria |
| Molecule generation / optimization | Parked | New proposal + evidence | Needs admission gate |
| Self-driving laboratory control | Parked | New proposal + evidence | Needs experiment-handoff admission |

## 5. Task-Load Summary

| Milestone | Tasks | Size mix | Total estimate |
|-----------|-------|----------|----------------|
| V36.2 closure | 4 (C0-1..C0-4) | 4 Small | Small-Medium (2-4 days) |
| V37.1 | 4 (T37-01..04) | 1 Medium + 3 Small | Medium |
| V37.2 | 4 (T37-05..08) | 2 Large + 1 Medium + 1 Small | Large |
| V37.3 | 3 (T37-09..11) | 2 Large + 1 Medium | Large |
| V37.4 | 2 (T37-12..13) | 2 Medium | Medium |
| V37.5 | 3 (T37-14..16) | 3 Medium | Medium |

Per roadmap §6.4, each milestone reserves 60% implementation / 25% tests+full
gates / 15% integration repair. WIP limits and stop-and-replan rules from
roadmap §6.3/§6.5 apply.
