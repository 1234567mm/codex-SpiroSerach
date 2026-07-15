# V21 Candidate Evidence Identity Closure Spec

Status: local implementation spec  
Source: `plans/v20-v25-integrated-delivery-roadmap.md` V21 charter  
Upstream gate: V20 closed on `main` at `ef45752`

## Problem Statement

SpiroSearch can now render authoritative single-run candidate state and compare immutable runs, but candidate-to-paper/evidence associations still need an explicit identity closure layer. V18 literature artifacts carry DOI, source asset, chunk, and extracted-claim identity; screening and V20 evolution use candidate, material, and use-instance identity. Product surfaces must not attach papers to candidates by display name, formula, title, or fuzzy similarity.

V21 introduces a versioned candidate identity registry and candidate-evidence-link artifact so every displayed candidate-paper association traces to an accepted link record, while proposed, ambiguous, conflicting, merged, or split identities route to review/blocking diagnostics.

## Evidence and Constraints

- Providers still emit facts and lineage only; they do not emit recommendations, verdicts, or ranking decisions.
- Link confidence is diagnostic only. It cannot promote a proposed link to accepted, make evidence scoring-eligible, or bypass `EvidenceQualityPolicy`.
- Read-only and frontend surfaces must discover artifacts through manifests/project indexes, not filename guessing or directory scans.
- Old runs remain immutable. Identity changes are surfaced through V20 history/projections rather than rewriting old run artifacts.
- Deterministic DOI/InChIKey/material normalization may create proposals, never automatic scientific truth.
- Unresolved identity is blocking for candidate-paper display and cannot affect scoring.

## Solution

Add two manifest-native artifacts:

1. `candidate-identity-registry.json`: stable candidate identities, aliases, material IDs, use instances, source identities, merge/split lineage, diagnostics, and reviewer state.
2. `candidate-evidence-links.jsonl`: versioned candidate-to-evidence/paper links with link basis, confidence category, reviewer state, lineage, evidence IDs, paper/source IDs, and blocking review IDs.

Add deterministic proposal helpers that normalize explicit DOI/InChIKey/material/use-instance fields into link proposals. Proposed links remain non-accepted until reviewer state allows display. Add repository/read-only envelopes, V19/V20 projections, and viewer tabs that show accepted candidate paper links and degrade locally for proposed/blocked/conflicting links.

## User Stories

- As a reviewer, I can see why a candidate-paper link is accepted, proposed, blocked, or conflicting.
- As a product user, I only see candidate paper tabs when the link is explicitly accepted.
- As an auditor, I can trace each displayed association to versioned link records and source evidence IDs.
- As a run-history reader, I can see identity changes without old runs being rewritten.

## Implementation Decisions

- Use manifest artifacts rather than a live service or database.
- Keep V21 read-plane first; no command-plane review writes yet.
- Treat merge/split history as explicit records on the registry, not implicit ID replacement.
- Store proposal basis and normalized keys for diagnostics, but do not let confidence become authority.
- Reuse `JsonArtifactRepository`, `ReadOnlyRunAPI`, V20 project envelopes, and frontend `RunDataStore`/`ProjectStore` seams.

## Testing Decisions

- Schema tests validate the registry and link artifacts and reject unsupported reviewer/link states.
- Repository/read-only tests prove manifest-only reads and fail-closed unavailable envelopes.
- Proposal tests prove deterministic normalization and proposed-only output.
- Projection/viewer tests prove accepted-only candidate paper display and diagnostics for unresolved identity.
- Full gate remains `$env:PYTHONPATH='src'; uv run python -m unittest discover tests -v`.

## Out of Scope

- Knowledge graph infrastructure.
- Fuzzy production joins.
- External validation claims.
- Review command plane writes.
- Scoring eligibility changes.
- Provider execution or paper ingestion side effects.

## Further Notes

V21 should be delivered as seven tracer tickets under `plans/v21-identity-closure-tickets/`. Each ticket must preserve V20 read-plane behavior and avoid creating a parallel candidate identity system outside manifests and read-only projections.
