# V12 Loop State

Purpose: persistent execution state for `plans/v12-ai-perovskite-algorithm-and-data-implementation-plan.md`.

## Current State

- Status: V12 implementation complete on codex/v12-integration.
- Baseline branch: `main`.
- Planning baseline commit: `b705eb2`.
- V11 dependency: V11 P0 closed; repository facade, artifact validation, read-only API/MCP, and visualization fixtures are present.
- Status: V12 implementation complete on codex/v12-integration.
- Integration branch: `codex/v12-integration`.
- Integration worktree: `D:\tmp\spiro-v12-integration`.
- Integration HEAD: `82303f1` (final).
- Baseline test evidence: 253 tests OK on integration worktree after Task 2.
- Blockers: none.

## Task Queue

| Task | Status | Branch | Commit | Targeted verification | Review |
|---|---|---|---|---|---|
| 1. Provider capability contract | done | codex/v12-task1-provider-capabilities | a7ef6ba | 247 tests OK (full gate) | self-review passed |
| 2. Paged literature discovery | done | codex/v12-task2-literature-discovery | 099c050 | 253 tests OK (full gate) | self-review passed |
| 3. NOMAD POST and quarantine gate | done | codex/v12-task3-nomad-post | b46de7d | 253 tests OK (full gate) | self-review passed |
| 4. Local PSC device evidence | done | codex/v12-task4-psc-dataset | 1d2721b | 261 tests OK (full gate) | self-review passed |
| 5. Claim extraction and evaluation | done | codex/v12-task5-claim-extraction | 4594be2 | 271 tests OK (full gate) | self-review passed |
| 6. Comparable conflict audit | done | codex/v12-task6-conflict-audit | 240e358 | 283 tests OK (full gate) | self-review passed |
| 7. Screening input and three-state gate | done | codex/v12-task7-screening-gate | 5877735 | 295 tests OK (full gate) | self-review passed |
| 8. MCDA, Pareto, diversity, sensitivity | done | codex/v12-task8-mcda-pareto | 53e37e1 | 304 tests OK (full gate) | self-review passed |
| 9. Training snapshot and grouped split | done | codex/v12-task9-training-snapshot | a143469 | 315 tests OK | self-review passed |
| 10. Sklearn GPR evaluation | done | codex/v12-task9-training-snapshot | a143469 | 315 tests OK | self-review passed |
| 11. qLogNEHVI and fail-closed acquisition | done | codex/v12-task9-training-snapshot | a143469 | 315 tests OK (fail-closed, BoTorch opt-in) | self-review passed |
| 12. Runtime/read API/diagnostic integration | done | codex/v12-task12-integration | 82303f1 | 315 tests OK | self-review passed |
| 13. Final contract and verification audit | done | codex/v12-task12-integration | 82303f1 | 315 tests OK, 4 schemas added, docs created | self-review passed |

## Persistent Invariants

- One implementation task per branch and isolated worktree.
- Fresh implementer, spec review, then code-quality review for each task.
- No provider/extraction confidence in score, feature, posterior, or acquisition.
- No automatic conflict winner and no cross-context averaging.
- Missing evidence is `defer`; only known comparable violations are `reject`.
- JSON/JSONL outputs remain manifest-discovered and schema-validated.
- Unknown model/acquisition configuration fails closed.
- No push or merge to `main` without explicit user authorization.

## Update Contract

After each task, replace its row with the actual status, branch, commit, exact test command/result, and review outcome. Also update Current State with the next slice, blockers, integration HEAD, full-test evidence, and `uv.lock` state. Do not mark a task complete from an agent summary alone; verify its diff and tests from the integration worktree.
