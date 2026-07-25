---
name: review-ship
description: Use before merging, pushing, deleting worktrees, claiming completion, or handing off a completed implementation slice.
---

# Review Ship

Use this skill before saying a code change is complete.

## Pairing

- Use after `worktree-tdd`, `contract-debugging`, or `artifact-validation`.
- Optional global review or verification skills can strengthen the review, but
  they do not replace the repository gates below.

## Pre-Ship Gate

```powershell
git status --short --branch
git diff --stat
git diff --cached --stat
Test-Path uv.lock
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/check-agent-hygiene.ps1 -RepositoryRoot (git rev-parse --show-toplevel)
```

If `uv.lock` exists and is not intentional:

```powershell
Remove-Item -LiteralPath uv.lock
```

If code, schema, runtime, or artifact behavior changed and this is the first
completion gate for the slice, run the full test gate:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

If a fresh full gate already passed and the only later changes are fixes for
specific review findings, use targeted reverification instead of reflexively
rerunning every expensive suite. The targeted set must include:

- the regression or focused test that proves the fixed finding;
- the package/frontend/schema/artifact gate directly owning the changed files;
- `git diff --check`, `Test-Path uv.lock`, and hygiene before commit.

Rerun the full gate when the fix changes a shared boundary, modifies generated
contract shape, touches scoring/provider/cache/SQLite writers, alters dependency
or build configuration, invalidates the previous full-gate diff, or when the
impact cannot be bounded in one sentence.

If the change is documentation-only, verify the relevant markdown files and diff
instead of forcing an unrelated unit-test run.

## Pre-Commit Optimization

Before staging, classify the final diff:

- docs/skills/process only: `git diff --check`, hygiene, and any skill/frontmatter
  validation are sufficient unless executable examples changed.
- Go deterministic runtime: focused Go package plus owning CLI/script gate.
- TypeScript UI/runtime projection: Vitest focused suite plus build when types
  or bundle-visible code changed.
- Rust/Tauri bridge or packaging: wrapper-based Rust/Tauri gate from
  `atomreasonx-tauri-msvc`; separate app build evidence from WiX/MSI evidence.
- Python science/ML/provider behavior: focused Python tests plus optional ML/BO
  gates when those modules are touched.

State the class in the completion report. This is a quality-preserving budget,
not permission to skip a required gate.

## Review Focus

Check the diff for:

- Trust-boundary violations.
- Schema changes without tests.
- Generated artifacts missing from manifests.
- Cache/index readers that no longer match writers.
- Missing review or error path for incomplete data.
- Frontend assumptions about hard-coded output names.
- Frontend command adapters importing read-only artifact APIs.
- AtomReasonX package-lock entries without package versions.
- AtomReasonX Tauri/Rust changes without `atomreasonx-tauri-msvc` checks or
  without a precise note when WiX MSI bundling is the only remaining blocker.
- Scoring paths that read raw provider payloads or provider confidence.
- Unrelated docs, cache, output, or dependency churn.
- Test churn that duplicates existing coverage without proving a new behavior,
  contract, boundary, or faster local failure.

Read the full relevant diff before commenting. Do not flag issues already addressed in the diff. Prefer fix-first handling: apply obvious mechanical fixes directly, but ask before risky, architectural, destructive, or judgment-heavy changes.

For high-risk diffs, add an adversarial pass: look for edge cases, race conditions, security holes, resource leaks, failure modes, silent data corruption, swallowed errors, and trust-boundary violations.

## Test Review

Keep completion quality high while avoiding test bloat:

- Prefer focused behavior or contract tests over broad source-string sentinels.
- Keep source-string sentinels only for dangerous imports, command bridges,
  schema-version drift, allowlist drift, or forbidden writer/read boundary
  crossings.
- Consolidate repeated secret/path leak checks behind a shared helper or one
  boundary-level assertion when possible.
- Do not remove tests covering scientific admissibility, provenance,
  source-manifest integrity, closure readiness, authorization, or fail-closed
  behavior unless an equal or stronger test replaces them.
- When omitting broad gates, state the exact prior evidence and why the current
  diff cannot affect omitted layers.

## Stage-End Learning

When a completed slice changes how future agents should work, update a durable
repository skill or governance note before the final commit. Good candidates:

- repeated verification pitfalls or faster equivalent gates;
- new trust-boundary rules for Go/TypeScript/Python/Rust;
- external reference absorption decisions;
- generated-file, linker, packaging, or platform-specific traps;
- test deduplication rules that keep the same assurance with fewer checks.

Keep these notes concise and operational. Do not archive raw chat logs or
commit narrative history that future agents cannot act on.

## Review-Fix Verification Record

Before committing after a review fix, record the validation decision:

- previous broad gate evidence: command, result, and commit/diff it covered;
- review finding fixed: file paths and behavior touched;
- targeted reruns: exact commands and results;
- omitted broad gates: why they are still covered or irrelevant.

Do not use targeted reverification to shrink the goal. It is only a scheduling
optimization when prior broad evidence remains valid for unchanged surfaces.

## Merge Checklist

If merging a worktree branch:

1. Confirm feature branch tests pass.
2. Return to the main worktree.
3. Confirm `main` state:

```powershell
git status --short --branch
git rev-list --left-right --count main...origin/main
```

4. Confirm the target worktree is the real `main` worktree before merging.
5. Merge the feature branch.
6. Run the full test gate again on `main` when behavior changed.
7. For docs-only integration, rerun a diff/status sanity check on `main`.
8. Remove generated files if present.
9. Push only after local `main` is verified.
10. Remove the temporary worktree and local feature branch.

## Completion Report

Include changed files summary, test command/result, commit SHA or "not committed", whether `uv.lock` exists, current branch/worktree status, and `main...origin/main` count.

Do not claim tests passed without fresh output from this turn.

Never push after code changes without fresh verification evidence. If tests fail, stop and report the failure instead of continuing the ship flow.
