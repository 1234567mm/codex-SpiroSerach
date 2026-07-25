---
name: context-handoff
description: Use when saving, restoring, compressing, or handing off work context across long sessions, worktrees, branches, compaction, or agent changes.
---

# Context Handoff

Use this skill when the user asks to save progress, restore context, resume work, compress context, or hand work to another agent.

## Pairing

- Use after `review-ship` when handing off completed work.
- Use during interrupted debugging or implementation when the next agent needs
  exact branch, worktree, and verification state.
- Global context or compression skills may help compact the text, but the
  repository return contract still defines what must be preserved.
- Use proactively when conversation/context usage reaches about 70% and the work
  is still active. Finish any command already needed for correctness, then save
  a concise handoff before continuing. Treat 80% context usage as the hard gate,
  not as the first reminder.

## Context Budget Trigger

At 70% context usage, save or refresh a concise handoff while there is still
enough room to preserve decisions, evidence, pitfalls, and next actions. At 80%
context usage, a repository handoff under `docs/` or `plans/` is required
before continuing through the hook/hygiene gate.

1. Capture current git state, changed files, commands already run, and the next
   concrete action.
2. Record durable lessons in the relevant project skill or plan when they affect
   future workflow, such as test deduplication, gate selection, external
   architecture reference policy, linker/build pitfalls, or trust-boundary
   rules.
   User-provided official APIs, datasets, and open-source repositories are
   mandatory handoff material when they shape implementation; include their URLs
   and whether the next step is direct migration, adapter alignment, or local
   reimplementation due to license/terms or boundary constraints.
3. Apply the quality-preserving test budget from `worktree-tdd` and
   `review-ship`: keep tests that prove behavior, contracts, source integrity,
   authorization, fail-closed scientific data, and secret/path boundaries; merge
   or avoid tests that only duplicate the same assertion at the same layer.
4. Do not reduce scope, skip required gates, or mark work complete merely
   because context is high. The handoff preserves quality; it does not replace
   verification.

Executable guard: `scripts/check-context-budget.ps1` is called by
`scripts/check-agent-hygiene.ps1`, and the repository pre-commit hook delegates
to hygiene when Git `core.hooksPath` points at `.githooks`. Hygiene verifies
that hook configuration so this rule does not remain documentation-only. With
no context percentage supplied, it verifies the static guardrails remain
configured. When an agent or wrapper can measure context, set
`SPIRO_CONTEXT_USAGE_PERCENT` or pass `-ContextUsagePercent`; at 80 or above,
also set `SPIRO_CONTEXT_HANDOFF_PATH` or pass `-HandoffPath` to a repository
handoff under `docs/` or `plans/`. At 70-79, the checker emits a visible
proactive warning so the handoff can be saved before automatic compaction is
near.

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
Test-Path uv.lock
```

Summarize:

- Current goal.
- Worktree path and branch.
- Start SHA.
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

When the handoff captures durable project lessons rather than only transient
resume state, write a repository archive under `docs/` or a next-wave plan
under `plans/`. Keep raw chat logs out of version control; summarize decisions,
commands, results, pitfalls, and remaining work.

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

## Start SHA

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
- Shared filesystem visibility is not shared edit authority.
