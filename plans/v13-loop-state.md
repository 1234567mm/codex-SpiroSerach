# V13 Loop State

## Goal

Execute `plans/v13-data-closure-and-real-baseline-plan.md` from `main@82303f1`.

## Current State

- Branch: `codex/v13-data-closure`
- Worktree: `D:\tmp\spiro-v13-closure`
- Baseline divergence: `main...origin/main = 0 0`
- V12 review: 315 existing tests passed in the original checkout, but V12 Tasks 10-13 lack their planned tests and runtime integration.
- Fresh-worktree baseline: 315 tests, 2 failures and 1 error in V11 fixture validation.
- Root cause: fixture files are forced to LF while manifest byte counts and SHA-256 values were generated from CRLF bytes.

## Decisions

- V13 closes V12 contracts before adding broader model families.
- Public baseline uses a fixed, license-verified snapshot; current three-row fixture is synthetic and cannot count as the baseline.
- Activation uses relative grouped baselines plus calibration and replay gates.

## Queue

| Slice | Status | Evidence |
|---|---|---|
| Deterministic fixture baseline | complete | `tests.test_v11_visualization_fixtures`: 4 tests OK |
| Leakage-safe training snapshot | complete | 15 focused tests; 39 aggregate tests OK |
| Grouped model evaluation | complete | 4 evaluator tests + 3 sklearn-extra tests; schema instance OK |
| Eleven-artifact closure | complete | 4 new round-trips; 37 artifact/repository/read tests OK |
| Runtime/read-only diagnostics | complete | Offline dataset-import, model-evaluate, acquisition-replay, and read-only aggregate implemented |
| Public snapshot and replay | complete | CC0 source verified; 24-row descriptive snapshot; replay 3 tests; qLogNEHVI 2 bo-extra tests |
| Full verification and docs | complete | Default: 343 tests OK; ML extra: 9 tests OK; BO extra: 5 tests OK; V12/V13 docs updated |

## Pitfalls

- `uv run` creates `uv.lock`; remove it after verification.
- Do not touch unrelated changes in the main worktree.
- A passing default suite does not prove optional ML/BO paths.
- On Windows without MSVC, BoTorch emits a compiler warning and uses its valid but slower pure-Python qLogEHVI kernel.
