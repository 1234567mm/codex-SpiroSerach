---
name: context-handoff
description: Use when saving, restoring, compressing, or handing off work context across long sessions, worktrees, branches, compaction, or agent changes.
---

# Context Handoff

Use this skill when the user asks to save progress, restore context, resume work, compress context, or hand work to another agent.

## Save Context

Gather:

```powershell
git rev-parse --show-toplevel
git branch --show-current
git status --short --branch
git diff --stat
git diff --cached --stat
git log --oneline -8 --decorate
git worktree list
git rev-list --left-right --count main...origin/main
```

Summarize:

- Current goal.
- Worktree path and branch.
- Completed commits.
- Files changed and why.
- Tests run, exact commands, and results.
- Remaining work in priority order.
- Known pitfalls or open questions.

If gstack `/context-save` is available, use its checkpoint convention:

```text
%USERPROFILE%\.gstack\projects\<project-slug>\checkpoints\
```

Saved context files are append-only. Never overwrite or delete existing checkpoints. Include branch name, timestamp, modified files, decisions, tests, remaining work, and pitfalls.

## Restore Context

Before continuing restored work, run:

```powershell
git status --short --branch
git rev-list --left-right --count main...origin/main
git worktree list
git log --oneline -8 --decorate
```

Then read the latest saved context and relevant changed files before editing.

Restore should search across branches by default. "Most recent" means the filename timestamp prefix (`YYYYMMDD-HHMMSS`), not filesystem modification time.

## Handoff Shape

```markdown
## Goal

## Current State

## Decisions

## Files Changed

## Tests

## Remaining Work

## Pitfalls
```

## Pitfalls To Preserve

- Current shell directory may not be the repository root.
- Generated files can appear after test commands.
- Full-test success in a feature worktree does not prove merged `main`.
- Do not silently expand scope during resume.
- If the saved context came from another branch, state that before continuing.
