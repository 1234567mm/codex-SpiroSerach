# V10 Loop State

> Purpose: persistent memory for V10 execution loops. Update this file at the start and end of each V10 slice.

## Current Status

- Branch: `main`
- Upstream: `origin/main`
- V10 baseline document: `plans/v10-loop-driven-productionization-and-visualization-plan.md`
- Current phase: Phase 0 contract hardening complete / V11 dependency freeze ready
- Current selected slice: `v10-manifest-contract-freeze`
- Current selected slice status: landed on main; V11 dependency-freeze unblocked
- Human gate: required before merge, push, deleting worktrees, or changing scoring policy.

## Current Known Dirty State

- `CLAUDE.md` has pre-existing modifications.
- `.claude/`, `.codex/`, `.reasonix/`, and `plans/qorder_plan/` are currently untracked.
- Do not use `git add -A`.
- Keep V10 plan/state edits separate from agent config or skill edits unless explicitly requested.

## Next Slice

```text
Slice: v11-dependency-freeze
Goal: verify the V10 artifact baseline that V11 repository/API/frontend consumers will use.
Stop condition:
  - enrichment and V4 runtime sample manifests validate against schemas/run-manifest.schema.json.
  - manifest paths exist relative to output directories and hashes/bytes/record_count match files.
  - scoring-view, review closure, provider lineage, and agent trace join keys are listed for V11 Repository/API/frontend use.
  - any remaining blockers are written to plans/v11-loop-state.md before V11 implementation starts.
```

## Suggested Worktree

```powershell
git worktree add D:\tmp\spiro-v11-dependency-freeze -b codex/v11-dependency-freeze main
```

## Targeted Tests

```powershell
$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest tests.test_run_artifacts tests.test_provider_schemas tests.test_enrichment_runtime_cli tests.test_artifact_viewer tests.test_v4_runtime_cli tests.test_scoring_view tests.test_review_runtime -v
```

## Full Gate

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

## Open Questions

- Should review queue output both `reason` and `reason_code` for one migration phase?
- Should the next review-router slice accept fixture review events by CLI only, or also by function argument?
- Current manifest freeze decision: `schema_ref` is explicit and nullable for legacy artifacts without payload schemas.
- Current manifest freeze decision: `join_keys` and `depends_on` come from a central artifact-kind registry.

## Latest Execution

```text
Worktree: D:\tmp\spiro-v10-manifest-contract-freeze
Branch: codex/v10-manifest-contract-freeze
Slice: v10-manifest-contract-freeze
Implemented:
  - schemas/run-artifact.schema.json
  - schemas/run-manifest.schema.json
  - RunArtifact metadata fields: format, schema_ref, record_count, join_keys, depends_on
  - centralized artifact-kind metadata registry for schema refs, join keys, and artifact dependencies
  - JSONL record_count from actual emitted or recorded non-empty lines
  - external provider cache mirror into output/provider-cache.jsonl for manifest-loadable paths without absolute path leakage
  - enrichment and V4 runtime manifest contract coverage for paths, hashes, bytes, schema refs, record counts, and join keys
Verification:
  - red targeted tests confirmed missing RunArtifact fields, missing run schemas, and missing producer manifest metadata
  - external provider cache regression confirms manifest path exists under output and does not leak the external cache path
  - targeted manifest/schema/enrichment/viewer/V4 suite: 42 tests OK
  - full suite in worktree: 194 tests OK
Generated files:
  - .venv was reused from uv setup in the temporary worktree
  - uv.lock was generated and will be removed before commit
Next:
  - landed on main as a4b11ad after post-merge full suite
  - start v11-dependency-freeze
```

```text
Worktree: D:\tmp\spiro-v10-review-closure-viewer
Branch: codex/v10-review-closure-viewer
Slice: v10-review-closure-viewer
Implemented:
  - Review Closure artifact viewer panel
  - manifest-path discovery for review_events, review_summary, and recompute_markers
  - summary/event/marker rendering with review_item_id, review_event_id, marker_id, target_id, and affected_artifacts join keys
  - escaping coverage for review-event reason text
  - reviewer identity redaction in review closure event rendering
Verification:
  - baseline artifact viewer suite: 6 tests OK
  - red viewer tests confirmed missing panel/renderer before implementation
  - targeted artifact viewer suite after implementation: 7 tests OK
  - targeted artifact viewer suite after reviewer redaction fix: 7 tests OK
  - full suite in worktree after reviewer redaction fix: 193 tests OK
Generated files:
  - .venv was created by uv in the temporary worktree
  - uv.lock was generated and removed
Next:
  - landed on main as e76cfba and pushed to origin/main
  - worktree and local feature branch removed
  - start v10-manifest-contract-freeze
```

```text
Worktree: D:\tmp\spiro-v10-human-review-router
Branch: codex/v10-human-review-router
Slice: v10-human-review-router
Implemented:
  - fixture-first HumanReviewRouter
  - CLI --review-events input
  - review-events.jsonl, review-summary.json, and recompute-markers.jsonl artifacts
  - schemas for review events, review summary, and recompute markers
  - canonical evidence writeback before scoring-view generation
  - manifest discovery for review closure artifacts
Verification:
  - red targeted suite confirmed missing router/runtime/CLI/artifact contracts before implementation
  - red review runtime regression confirmed recompute/curation hardening before implementation
  - targeted review/runtime/schema/enrichment suite: 38 tests OK
  - full suite in worktree: 192 tests OK
Generated files:
  - uv.lock was generated and removed
Next:
  - merge to main after review-ship pass
  - run full suite again on main before push
```

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
  - post-merge main full suite: 184 tests OK
Generated files:
  - uv.lock generated by main full gate and removed
Next:
  - landed on main as 77fdbfd and pushed to origin/main
  - start v10-human-review-router
```

## Loop Caps

- `MAX_PARALLEL=2`
- One implementation slice per branch.
- One reviewer pass before merge.
- Stop after two failed full-test attempts and write a blocker note here.
