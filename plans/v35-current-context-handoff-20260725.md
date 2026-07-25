# V35 Current Context Handoff

Date: 2026-07-25
Branch: `codex-v35-data-source-p0`
Current HEAD at handoff creation: `d400016c0ff8c7664ba8726c31c7e5497e334d2b`

## Goal

Continue V35 without reducing the data-source or scientific architecture scope:
move deterministic runtime and operator workflows toward Go plus TypeScript,
keep Python as the scientific/ML bridge until parity evidence exists, and
preserve provider/review/scoring/artifact trust boundaries.

## Current State

The latest committed slice restores persisted NOMAD workflow task execution
state. The active dirty slice adds AtomReasonX workflow task handoff status so
operators can distinguish local queued tasks, ledger-admitted tasks,
current-session execution snapshots, restored persisted snapshots, and
review-blocked snapshots. A hook-visibility follow-up is also in progress so
context-budget checks visibly run through hygiene/pre-commit.

Start SHA for the dirty slice is `d400016c0ff8c7664ba8726c31c7e5497e334d2b`.

## Decisions

- Use `handoff_source` in TypeScript task summaries to distinguish
  `current_session_execution` from `restored_snapshot`; do not infer restore
  state from the mere presence of an execution report.
- Keep the workflow task handoff status UI-only. It must not add provider cache,
  SQLite, scoring, review-promotion, or experiment writers.
- Context preservation must happen before automatic compaction pressure. The
  executable rule is now a 70% proactive warning and an 80% hard handoff gate
  when `SPIRO_CONTEXT_USAGE_PERCENT` or `-ContextUsagePercent` is supplied.
- Hooks cannot read Codex's private context counter by themselves. A runner,
  wrapper, or manual command must pass the measured percentage into
  `scripts/check-context-budget.ps1`; hygiene/pre-commit then makes the check
  visible and fail-closed at the hard threshold.

## Files Changed

- `frontend/atomreasonx/src/components/WorkflowView.tsx`: adds workflow task
  handoff state classification and labels.
- `frontend/atomreasonx/src/contracts/types.ts`: adds task `handoff_source`.
- `frontend/atomreasonx/src/adapters/workflow-task-execution-adapter.ts`: marks
  projected execution reports as current-session snapshots.
- `frontend/atomreasonx/src/adapters/workflow-task-restore-adapter.ts`: accepts
  only restored-snapshot provenance and normalizes restored tasks.
- `frontend/atomreasonx/src/__tests__/contracts.test.ts`: adds contract/UI
  coverage for queued, admitted, current-session, restored, and review-blocked
  states.
- `scripts/check-agent-hygiene.ps1`: prints successful context-budget hook
  output so the hook does not look silent.
- `scripts/check-context-budget.ps1`: adds a 70% proactive warning band while
  keeping the 80% hard handoff gate.
- `tests/test_agent_hygiene_script.ps1` and
  `tests/test_context_budget_script.ps1`: cover visible hook execution and the
  proactive context warning.
- `.codex/skills/context-handoff/SKILL.md`, `docs/project-hooks.md`, and
  `plans/v35-execution-status-and-next-slices.md`: record the executable
  context-budget rule and test-deduplication policy.

## Tests

Already passed earlier in this dirty slice before the latest context-budget
warning edit:

- `npm.cmd test` in `frontend/atomreasonx`: 53 tests passed.
- `npm.cmd run build` in `frontend/atomreasonx`: passed.
- `$env:PYTHONPATH='src'; .\.venv\Scripts\python.exe -m unittest tests.test_atomreasonx_contracts -v`: 31 tests passed outside sandbox.
- `git diff --check`: passed.
- `scripts/check-agent-hygiene.ps1`: passed before the hook-output visibility
  follow-up.
- `Test-Path uv.lock`: `False`.

Required reruns before commit:

- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/test_context_budget_script.ps1`
- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File tests/test_agent_hygiene_script.ps1`
- `powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-agent-hygiene.ps1 -RepositoryRoot (git rev-parse --show-toplevel)`
- `git diff --check`
- `Test-Path uv.lock`

Rerun `npm.cmd test` and `npm.cmd run build` only if frontend files changed
again after their fresh pass; the current hook-only edits do not invalidate
the existing frontend evidence.

## Remaining Work

1. Verify the updated context-budget scripts and hygiene output.
2. Review the full final diff for boundary issues and test duplication.
3. Stage the owned files and commit the current slice, likely as
   `feat: distinguish workflow task handoff states`.
4. Continue V35 toward the next data-source closure slice: PubChemQC full
   snapshot policy, Materials Cloud record-specific import, or NOMAD
   closure/review promotion gates before any cache/SQLite/scoring writers.

Next concrete action: run focused PowerShell hook tests, hygiene, whitespace
check, and `uv.lock` check; then stage and commit if clean.

## Pitfalls

- Sandboxed `.venv\Scripts\python.exe` may fail with a local uv trampoline
  permission error; use the already-approved escalated Python command only
  when Python contract tests are actually needed.
- Do not copy external repository code wholesale. Use `openai/codex`,
  `esengine/DeepSeek-Reasonix`, and `tufeiping/api-for-cherrystudio` as
  architecture references unless exact license/source parity review is in the
  slice.
- Do not treat context-budget docs as enforcement. Enforcement is the script
  path through hygiene/pre-commit plus an explicit context percentage input.
- Do not rerun broad gates reflexively after bounded hook/doc edits; keep the
  hard scientific/source-integrity/authorization boundaries covered.
