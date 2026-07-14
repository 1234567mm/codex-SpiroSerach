---
name: grilling
description: Use when the user asks to grill, stress-test, or challenge an experiment plan, architectural decision, or other consequential proposal before action.
---

# Grilling

Resolve decisions before implementation or publication. Inspect repository facts first; ask the user only about choices that cannot be discovered locally.

## Flow

1. State the decision under review, constraints, and current evidence.
2. Ask one high-leverage question at a time and give a recommended answer with its tradeoff.
3. Cover success criteria, data/evidence quality, failure modes, validation, ownership, reversibility, and excluded scope.
4. Summarize agreed decisions and unresolved risks. Do not implement, publish, or create durable records until the user confirms the shared understanding.

For code-backed claims, use `codebase-memory-mcp` before asking. Treat plans as context, not authority.

## Upstream Basis

Adapted from `mattpocock/skills` at commit `66898f60e8c744e269f8ce06c2b2b99ce7660d5f`, `skills/productivity/grilling/SKILL.md`.
