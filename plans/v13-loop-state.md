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
| Grouped model evaluation | in_progress | |
| Eleven-artifact closure | pending | |
| Runtime/read-only diagnostics | pending | |
| Public snapshot and replay | pending | |
| Full verification and docs | pending | |

## Pitfalls

- `uv run` creates `uv.lock`; remove it after verification.
- Do not touch unrelated changes in the main worktree.
- A passing default suite does not prove optional ML/BO paths.
