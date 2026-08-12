# V36 Architecture And Data Pipeline Evolution — Closure

> Status: closed
> Date: 2026-08-12
> Integration HEAD SHA: `9868302` (after V36 closure slice; also includes `6098322`, `7259a14`)
> Source plan: `plans/v36-architecture-and-data-pipeline-evolution.md`
> Closure driver: 09 review (`plans/qorder_plan/09-project-progress-and-direction-review-2026-08-12.md`) + v37 plan C0 slice (`plans/v37-future-direction-and-task-breakdown-plan.md`)

## 1. Scope Delivered

V36 goal: transition from *shadow readiness* to *production activation*:
promote accepted snapshots through the closure pipeline, integrate new public
datasets, and add ML/AI agent workflows.

### 1.1 Delivered Before This Closure (V36 first slice + V36.1)

| Artifact | Status | Evidence |
|----------|--------|----------|
| A1 closure promotion CLI (`source-closure promote`) | ✅ | `b4a9d75` |
| B3 OQMD Go client + CLI + frontend fixture | ✅ | `743ba60`, `bf5b3b7`, `4126e72` |
| V36.1 local source closure (HOPV15/OPV-DB importers + snapshot closure) | ✅ | `281e67d` |
| PubChem connection probe CLI | ✅ | `b509f47` |
| Path-aware compile verification skill | ✅ | `0080160` |
| Release gate fixture contracts | ✅ | `ba78613` |

### 1.2 Delivered In This Closure Slice (C0-1..C0-4)

| Item | Status | Evidence |
|------|--------|----------|
| C0-1 `operator-task-promotion` schema with four writer authorization fields (`provider_cache_written`, `local_backend_written`, `scoring_written`, `experiment_written`) | ✅ | `schemas/operator-task-promotion.schema.json`; Go `OperatorTaskPromotionReport` + validation; Go/Python schema-drift tests |
| C0-2 TypeScript promotion surface (`promotion_blocked` / `promoted_to_cache` / `promoted_to_scoring`) | ✅ | `frontend/atomreasonx/src/components/WorkflowView.tsx` renders promotion state per task row; frontend tests |
| C0-3 `band_gap_ev` screening eligibility policy decision | ✅ | `plans/band-gap-ev-screening-eligibility-policy.md` (missing → DEFER/review; below threshold → REJECT) |
| C0-4 V36 closure document + closure HEAD SHA (this document) | ✅ | `9868302` |

## 2. Closure Gates

- All Go packages pass `go test ./...` (15 packages, ok).
- Frontend: `npm.cmd test` (54 tests) and `npm.cmd run build` pass in
  `frontend/atomreasonx`.
- Python: `tests.test_atomreasonx_contracts` (31) and
  `tests.test_screening_policy` (12) pass; drift tests cover the new promotion
  schema and CLI surface.
- `git diff --check` and repository agent hygiene hook pass.
- `uv.lock` generated during testing was removed before commit.

## 3. Explicit Non-Goals At Closure

V36 closure does not claim production activation. The following remain
forward work in `plans/v37-future-direction-and-task-breakdown-plan.md`:

- A2 live provider enablement (PubChem/Materials Project Go live) — V37.1
- A3 NOMAD official OpenAPI alignment — V37.2
- B1 CEPDB snapshot, B2 PubChemQC subset, B4 JARVIS — V37.2/V38+
- C1 ML/AI autonomous HTL screening agent — V37.3
- D1 screening view, D2 desktop packaging (WiX/MSI, auto-update, signing) — V37.4/V37.5
- E1 Go→TS schema generation, E2 Python bridge deprecation, E3 performance baseline — V37.1/V37.4

Promotion remains `readiness_only`: `source-closure promote` validates
readiness and declares no downstream writer writes. Cache/SQLite/scoring/
experiment writes require a separate explicit writer gate (V37 tracks).

## 4. Residual Items Tracked

| ID | Item | Owner |
|----|------|-------|
| R1 | WiX/MSI installer verification blocked (external WiX toolset acquisition) | V37.5 |
| R2 | V37 implementation not started | V37 plan |

## 5. Verification Command Summary

```powershell
go test ./...
Set-Location frontend/atomreasonx; npm.cmd test; npm.cmd run build
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_atomreasonx_contracts tests.test_screening_policy -v
```
