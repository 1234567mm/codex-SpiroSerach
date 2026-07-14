---
name: to-spec
description: Use when the user asks to turn the current conversation, research finding, or approved proposal into a SpiroSearch implementation specification.
---

# To Spec

Synthesize the established conversation and current repository state. Do not reopen settled questions; use `grilling` first when consequential decisions are still unresolved.

## Workflow

1. Read the relevant plans, durable glossary/ADRs, and repository contracts. Use `codebase-memory-mcp` for code structure and existing test seams.
2. Prefer existing test seams and state the evidence, review, artifact, and scoring boundaries affected. Plans remain planning artifacts, not executable authority.
3. Draft a spec with: Problem Statement, Evidence and Constraints, Solution, User Stories, Implementation Decisions, Testing Decisions, Out of Scope, and Further Notes.
4. Default to a versioned local draft at `plans/<topic>-spec.md` when the topic yields an unambiguous new filename. Do not overwrite an existing plan without explicit authority.
5. Publish to GitHub Issues or another external tracker only when the user explicitly identifies the target and authorizes that external write. Otherwise report the local path and leave publication pending.

Use domain terminology precisely. Avoid stale file-by-file prescriptions; identify contracts, seams, and observable behavior instead.

## Upstream Basis

Adapted from `mattpocock/skills` at commit `66898f60e8c744e269f8ce06c2b2b99ce7660d5f`, `skills/engineering/to-spec/SKILL.md`.
