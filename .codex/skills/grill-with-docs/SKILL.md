---
name: grill-with-docs
description: Use when the user wants to rigorously refine an experiment, implementation, or architecture decision and capture only the resulting durable glossary or ADR records.
---

# Grill With Docs

Use `grilling` to resolve decisions one at a time and `domain-modeling` to keep terminology and architecture records coherent.

## Workflow

1. Establish the proposal, current evidence, non-negotiable repository boundaries, and success criteria.
2. Run the grilling loop. Discover facts from the repository before asking; ask only one decision question at a time.
3. After confirmation, update the glossary only for newly resolved domain terms and write an ADR only when its reversibility, surprise, and tradeoff thresholds are all met.
4. Link the durable records from the resulting spec or plan when appropriate. Do not create records for tentative ideas, routine implementation details, or transient session context.

The user retains decision authority. This skill sharpens and records decisions; it does not authorize implementation, external publication, or changes to provider/scoring trust boundaries.

## Upstream Basis

Adapted from `mattpocock/skills` at commit `66898f60e8c744e269f8ce06c2b2b99ce7660d5f`, `skills/engineering/grill-with-docs/SKILL.md`.
