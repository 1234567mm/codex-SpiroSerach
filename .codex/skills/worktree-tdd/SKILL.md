---
name: worktree-tdd
description: Use when implementing or changing repository code in an isolated branch, before writing implementation code, especially when tests, schemas, artifacts, adapters, or frontend behavior may change.
---

# Worktree TDD

Use this skill for implementation work that should be isolated, tested, and easy to merge.

This is a functional workflow skill. It is not tied to any roadmap, phase, or plan file.

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
4. Write or update the smallest failing test that captures the intended behavior.
5. Run that targeted test and confirm it fails for the expected reason.
6. Implement the smallest passing change.
7. Run the targeted test again, then the full test gate.

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

## Completion Evidence

Report branch, worktree path, test commands/results, commit SHA if committed, `git status --short --branch`, and `git rev-list --left-right --count main...origin/main`.

