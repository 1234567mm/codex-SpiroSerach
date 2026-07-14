---
name: domain-modeling
description: Use when defining or correcting SpiroSearch terminology, evidence semantics, domain boundaries, or a durable architecture decision.
---

# Domain Modeling

Maintain a precise shared language for this repository. This skill changes the domain model; merely reading existing vocabulary does not trigger it.

## Rules

- Prefer established terms such as `ProviderResponse`, canonical evidence, lineage, review item, `EvidenceQualityPolicy`, and `ScoringView` when they match the meaning.
- Challenge overloaded or contradictory terms with a concrete scenario. Missing, ambiguous, or conflicting evidence must remain review/blocking state, never a ranking conclusion.
- When code behavior is relevant, verify it through `codebase-memory-mcp` before recording a conclusion.
- Create `docs/domain-glossary.md` only when a term is resolved. Keep it implementation-free: term, definition, inclusions, exclusions, and related terms.
- Create an ADR under `docs/adr/NNNN-<slug>.md` only for a hard-to-reverse, non-obvious tradeoff with meaningful alternatives. Include context, decision, alternatives, consequences, and status.
- Do not treat a plan, checkpoint, provider payload, or model output as a glossary or an architectural decision.

Record durable documentation only after the relevant decision is agreed and the edit is within the user's authority.

## Upstream Basis

Adapted from `mattpocock/skills` at commit `66898f60e8c744e269f8ce06c2b2b99ce7660d5f`, `skills/engineering/domain-modeling/SKILL.md`.
