# V13 Data Closure and Real Baseline Plan

**Goal:** Close the incomplete V12 data-to-decision path and produce one auditable public-data baseline without enabling an unqualified model.

## Delivery Slices

1. Restore deterministic artifact fixtures across fresh checkouts.
2. Make training snapshots row-complete, length-validated, and leakage-safe across shared material or source groups.
3. Add grouped dummy/heuristic/GPR evaluation, calibration metrics, and fail-closed activation status.
4. Close all eleven V12 artifact contracts through schema, writer, manifest, repository, and read-only tests.
5. Add explicit offline CLI operations and a manifest-discovered diagnostic fixture; reads never train, fetch, or write.
6. Verify a CC BY 4.0 public PSC source, commit a bounded normalized snapshot with source row IDs and hashes, and run offline replay.
7. Update V12/V13 status and interface docs from fresh test evidence.

## Gates

- Missing, inconsistent, non-finite, or provenance-free training rows fail closed.
- Shared material or source membership never crosses a fold.
- Provider/extractor confidence never becomes a feature, score, posterior, or acquisition input.
- A model is `eligible` only if grouped aggregate metrics beat dummy and heuristic baselines, calibration is non-degenerate, and replay does not regress; otherwise it is `disabled` with reasons.
- JSON/JSONL remains the external contract; no database, service split, GNN, or generator is added.
- Default, `ml`, and `bo` test gates must pass from a clean worktree; `uv.lock` and generated outputs are not committed.

## Execution

Use isolated worktree `D:\tmp\spiro-v13-closure` on `codex/v13-data-closure`. Apply TDD per slice, commit focused changes, and record exact evidence in `plans/v13-loop-state.md`.
