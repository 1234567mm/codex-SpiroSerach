# V10 Loop State

> Purpose: persistent memory for V10 execution loops. Update this file at the start and end of each V10 slice.

## Current Status

- Branch: `main`
- Upstream: `origin/main`
- V10 baseline document: `plans/v10-loop-driven-productionization-and-visualization-plan.md`
- Current phase: Phase 0 / Phase 1 boundary
- Current selected slice: `v10-scoring-view-runtime`
- Current selected slice status: implemented and verified in worktree
- Human gate: required before merge, push, deleting worktrees, or changing scoring policy.

## Current Known Dirty State

- `CLAUDE.md` has pre-existing modifications.
- `.claude/`, `.codex/`, `.reasonix/`, and `plans/qorder_plan/` are currently untracked.
- Do not use `git add -A`.
- Keep V10 plan/state edits separate from agent config or skill edits unless explicitly requested.

## Next Slice

```text
Slice: v10-scoring-view-runtime
Goal: scoring and HTL runtime can consume scoring-view.json as the policy-filtered energy read model.
Stop condition:
  - scoring-view energy facts override candidate HOMO/LUMO inputs.
  - missing scoring-view energy facts remain unresolved and do not fall back to stale candidate values.
  - scoring-view quality/trust metadata does not directly change score components or totals.
  - legacy candidate-only scoring calls remain compatible.
  - targeted tests pass.
```

## Suggested Worktree

```powershell
git worktree add D:\tmp\spiro-v10-scoring-view-runtime -b codex/v10-scoring-view-runtime main
```

## Targeted Tests

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest tests.test_scoring tests.test_htl_scoring -v
```

## Full Gate

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

## Open Questions

- Should review queue output both `reason` and `reason_code` for one migration phase?
- Should the next review-router slice accept fixture review events by CLI only, or also by function argument?

## Latest Execution

```text
Worktree: D:\tmp\spiro-v10-scoring-view-artifact
Branch: codex/v10-scoring-view-artifact
Slice: v10-scoring-view-artifact
Implemented:
  - scoring-view.json runtime artifact
  - schemas/scoring-view.schema.json
  - scoring_view manifest kind
  - scoring view artifact emitter
  - static viewer Scoring View panel
  - artifact/schema/runtime/viewer tests
Verification:
  - targeted artifact/schema/runtime/viewer suite: 32 tests OK
  - scoring/provider regression suite: 37 tests OK
  - full suite: 178 tests OK
  - post-merge main full suite: 178 tests OK
Generated files:
  - uv.lock was generated and removed
Next:
  - landed on main as a8ed858 and pushed to origin/main
  - start v10-scoring-view-runtime
```

```text
Worktree: D:\tmp\spiro-v10-scoring-view-runtime
Branch: codex/v10-scoring-view-runtime
Slice: v10-scoring-view-runtime
Implemented:
  - ScoringViewAdapter for dict/path scoring-view inputs
  - evaluate_candidate optional scoring_view input path
  - evaluate_with_pareto and pareto_frontier optional scoring_view input path
  - score_spiro_htl_candidate optional scoring_view input path
  - no fallback from scoring-view gaps to stale candidate HOMO/LUMO values
  - scoring quality/trust metadata remains excluded from direct score math
Verification:
  - baseline full suite in worktree: 178 tests OK
  - red test confirmed before implementation: scoring/HTL rejected scoring_view keyword
  - targeted scoring/HTL suite after implementation: 15 tests OK
  - full suite after implementation: 184 tests OK
Generated files:
  - uv.lock absent after final gate
Next:
  - review diff
  - commit/merge/push after verification
```

## Loop Caps

- `MAX_PARALLEL=2`
- One implementation slice per branch.
- One reviewer pass before merge.
- Stop after two failed full-test attempts and write a blocker note here.
