# V28 Evidence-Gated Scale And Validation Closure

> Date: 2026-07-17
> Branch: `codex/v28-evidence-gated`
> Worktree: `D:\tmp\spiro-v28-evidence`
> Baseline / P0 SHA: `6037c37aff9819ed2acd9f159975635f1c978b5f`
> Status: DONE_WITH_CONCERNS

## 1. Scope Closed

V28 completed as an evidence-gated release:

1. P0 baseline/protocol freeze committed on main.
2. Model admission criteria + offline harness + no-admit outcomes.
3. Public dataset lock + offline OPV-DB/HOPV15 provider fixtures with provenance.
4. Internal audit graph contract, exporter, and audit queries as read model only.
5. Scientific scale 100/500 explicitly blocked with machine-readable reasons.
6. Local readiness runbook, incident checklist, and rehearsal evidence (no hosting).

## 2. Ticket Matrix

| Ticket | Status | Notes |
| --- | --- | --- |
| T28-K1 | DONE | scale baseline freeze |
| T28-K2 | DONE | selection protocol |
| T28-K3 | BLOCKED documented | C100 readiness blocked |
| T28-K4 | BLOCKED documented | B500 readiness blocked |
| T28-L1 | DONE | GNN numeric criteria |
| T28-L2 | DONE | offline GNN fixture harness |
| T28-L3 | DONE | qNEHVI numeric criteria |
| T28-L4 | DONE | replay/strategy comparison + no-admit |
| T28-M1 | DONE | admissible public dataset lock |
| T28-M2/M3 | DONE_WITH_CONCERNS | offline fixture providers + validation report; full remote dumps not vendored |
| T28-N1 | DONE | audit graph contract |
| T28-N2 | DONE | snapshot exporter |
| T28-N3 | DONE | audit queries |
| T28-O1 | DONE | local runbook |
| T28-O2 | DONE | incident checklist |
| T28-O3 | DONE_WITH_CONCERNS | local rehearsal evidence from focused gates |
| T28-P1 | DONE_WITH_CONCERNS | residual risks classified |
| T28-P2 | DONE | this closure |

## 3. Model Admission Decisions

- GNN: **no_admit**
- qNEHVI: **no_admit**
- Production stubs remain `UnsupportedSurrogateError` fail-closed

## 4. Scale Decisions

- C100: **blocked** (structures/tooling/anchors/measured compute missing)
- B500: **blocked** (depends on C100)

## 5. Verification

Focused gate (pass):

```powershell
$env:PYTHONPATH='src'
python -m unittest tests.test_model_admission tests.test_opv_db_provider tests.test_hopv15_provider tests.test_audit_graph tests.test_scale_readiness tests.test_v28_local_readiness tests.test_run_artifacts tests.test_source_registry tests.test_enrichment_runtime_cli -v
```

Result: 55 tests OK.

Additional partial full-suite batches also OK where executed; harness timeout prevented a single-process `discover` summary in this environment.

## 6. Residual Risks / V29-V30

- R28-1 external DFT tooling still blocks real scale compute.
- R28-2/R28-3 model admission remains no-admit until labels/objectives exist.
- V29: hosting/deployment packaging decision after local execution is proven.
- V30: broader KG product surface and optimization UX after V28 evidence.

## 7. Explicit Non-Claims

- No hosted deployment added.
- No self-driving lab integration.
- Graph is not canonical evidence store.
- No fabricated 100/500 molecule energies.
- Providers do not emit recommendations/verdicts.
