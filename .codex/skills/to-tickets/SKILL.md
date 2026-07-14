---
name: to-tickets
description: Use when the user asks to split an approved SpiroSearch plan or specification into independently verifiable implementation tickets with explicit blockers.
---

# To Tickets

Turn an approved plan or spec into narrow, end-to-end tracer bullets. Refresh repository facts before trusting an older planning artifact.

## Workflow

1. Read the source plan/spec, relevant contracts, durable decisions, and current Git state. Use `codebase-memory-mcp` if ticket scope depends on code structure.
2. Make each ticket independently demoable or verifiable. Cover the necessary vertical path across contracts, runtime behavior, artifacts, frontend/read models, and tests without creating layer-only tickets.
3. State blockers explicitly. Handle wide mechanical refactors as expand, migration batches, and contract; keep each green where possible.
4. Present the proposed dependency graph for user approval before writing tickets.
5. With approval and no configured external tracker, write one file per ticket under `plans/<feature>-tickets/<NN>-<slug>.md`. Each file must include source plan, what to build, acceptance criteria, blocked-by, verification, and status.
6. Create remote issues only with an explicit tracker target and external-write authorization. Never infer a tracker, modify a parent issue, or duplicate an existing ticket.

Work the unblocked frontier using `worktree-tdd`, one isolated implementation slice at a time.

## Upstream Basis

Adapted from `mattpocock/skills` at commit `66898f60e8c744e269f8ce06c2b2b99ce7660d5f`, `skills/engineering/to-tickets/SKILL.md`.
