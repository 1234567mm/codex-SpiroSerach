# V10 Loop State

> Purpose: persistent memory for V10 execution loops. Update this file at the start and end of each V10 slice.

## Current Status

- Branch: `main`
- Upstream: `origin/main`
- V10 baseline document: `plans/v10-loop-driven-productionization-and-visualization-plan.md`
- Current phase: Phase 0 / Phase 1 boundary
- Current selected slice: `v10-scoring-view-artifact`
- Current selected slice status: implemented and verified in worktree
- Human gate: required before merge, push, deleting worktrees, or changing scoring policy.

## Current Known Dirty State

- `CLAUDE.md` has pre-existing modifications.
- `.claude/`, `.codex/`, `.reasonix/`, and `plans/qorder_plan/` are currently untracked.
- Do not use `git add -A`.
- Keep V10 plan/state edits separate from agent config or skill edits unless explicitly requested.

## Next Slice

```text
Slice: v10-scoring-view-artifact
Goal: runtime emits scoring-view.json and lists it in run-manifest.json.
Stop condition:
  - scoring-view.json validates against schema.
  - manifest includes scoring_view artifact with hash/bytes/schema metadata.
  - blocking review items and missing reference_scale facts are excluded.
  - provider confidence is absent from scoring-view.json.
  - targeted tests pass.
```

## Suggested Worktree

```powershell
git worktree add D:\tmp\spiro-v10-scoring-view-artifact -b codex/v10-scoring-view-artifact main
```

## Targeted Tests

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest tests.test_scoring_view tests.test_run_artifacts tests.test_artifact_viewer tests.test_provider_cache -v
```

## Full Gate

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

## Open Questions

- Should `canonical-evidence.json` remain the source for Phase 1 scoring view, or should Phase 1 introduce `evidence-snapshot.json` first?
- Should review queue output both `reason` and `reason_code` for one migration phase?
- Should frontend support `scoring_view` in the existing static viewer before any runtime scoring refactor?

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
Generated files:
  - uv.lock was generated and removed
Next:
  - review diff
  - optional commit/merge after human approval
```

## Loop Caps

- `MAX_PARALLEL=2`
- One implementation slice per branch.
- One reviewer pass before merge.
- Stop after two failed full-test attempts and write a blocker note here.
