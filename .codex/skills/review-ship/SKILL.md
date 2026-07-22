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

If code, schema, runtime, or artifact behavior changed, run the full test gate:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

If the change is documentation-only, verify the relevant markdown files and diff
instead of forcing an unrelated unit-test run.

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
- Scoring paths that read raw provider payloads or provider confidence.
- Unrelated docs, cache, output, or dependency churn.

Read the full relevant diff before commenting. Do not flag issues already addressed in the diff. Prefer fix-first handling: apply obvious mechanical fixes directly, but ask before risky, architectural, destructive, or judgment-heavy changes.

For high-risk diffs, add an adversarial pass: look for edge cases, race conditions, security holes, resource leaks, failure modes, silent data corruption, swallowed errors, and trust-boundary violations.

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
