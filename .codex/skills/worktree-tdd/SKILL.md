---
name: worktree-tdd
description: Use when implementing or changing repository code in an isolated branch, before writing implementation code, especially when tests, schemas, artifacts, adapters, or frontend behavior may change.
---

# Worktree TDD

Use this skill for implementation work that should be isolated, tested, and easy to merge.

This is a functional workflow skill. It is not tied to any roadmap, phase, or plan file.

## Pairing

- Use `codebase-memory-mcp` first when you still need discovery or impact
  analysis.
- Global planning or TDD skills may help shape the work, but this repository's
  governance, boundaries, and test gates still control execution.
- Documentation-only edits usually do not need this skill unless they are part
  of a larger behavior change or require isolated integration.

## Repository Defaults

- Repository root: `D:\1-QRS\qorder_pr\codex-SpiroSerach`
- Temporary worktree root: `D:\tmp`
- Main branch: `main`
- Full test gate:

```powershell
$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v
```

## Flow

1. Confirm root, branch, and sync state:

```powershell
git rev-parse --show-toplevel
git branch --show-current
git status --short --branch
git rev-list --left-right --count main...origin/main
```

2. For non-trivial implementation work, create a branch worktree:

```powershell
git worktree add D:\tmp\<repo>-<topic> -b codex/<topic> main
```

3. Run a baseline test in the worktree.
4. Read the governing contract before editing:
   provider boundary, scoring boundary, review path, artifact contract, or
   frontend fixture as applicable.
5. Write or update the smallest failing test that captures the intended behavior.
6. Run that targeted test and confirm it fails for the expected reason.
7. Implement the smallest passing change.
8. Run the targeted test again, then the full test gate.

## Design Rules

- Think before coding. Do not start with a broad refactor when a bounded patch
  is enough.
- Keep the change surgical. Do not widen scope because neighboring code looks
  untidy.
- Prefer existing seams, adapters, and manifests over new side paths or hidden
  fallback logic.
- If the change touches providers, scoring, review, or artifacts, verify the
  trust boundary explicitly before coding.

## Test Discipline

- A test that never failed proves less than it appears to prove.
- For bug fixes, add a regression test that reproduces the bug first.
- For schema or artifact changes, add a contract test before changing emitters.
- For frontend behavior, add or update the existing frontend-oriented test first.

## Generated Files

After `uv run`, check for generated files:

```powershell
Test-Path uv.lock
```

Remove `uv.lock` unless the task explicitly changes repository dependency policy:

```powershell
Remove-Item -LiteralPath uv.lock
```

For AtomReasonX frontend work, prefer Windows-safe npm commands:

```powershell
Set-Location frontend/atomreasonx
npm.cmd test
npm.cmd run build
```

If npm reports `Invalid Version`, inspect `package-lock.json` for package
entries without `version`; regenerate the lockfile with `npm.cmd install` only
when dependency verification is in scope.

## Completion Evidence

Report branch, worktree path, test commands/results, commit SHA if committed, `git status --short --branch`, and `git rev-list --left-right --count main...origin/main`.

