# T20-07: Render Candidate History And Project Diagnostics

- Status: pending
- Size: large
- Owner role: frontend/product owner
- Source plan: `plans/v20-manifest-native-run-evolution-and-decision-audit-spec.md`
- Blocked by: T20-04, T20-06

## What To Build

Render candidate status, evidence, blocker, score/rank, artifact, and model
changes from backend deltas. Add project-level diagnostics for invalid,
unavailable, duplicate, unsafe, stale, or non-comparable inputs.

## Acceptance Criteria

- Candidate history is keyed only by declared candidate identity.
- Status transitions display backend source, codes, and source run IDs.
- Evidence and blocker changes preserve their declared IDs and lineage.
- Score/rank changes render only when compatibility permits them.
- Missing/invalid optional panels degrade locally and clear stale content.
- Identity ambiguity is shown as blocked/unavailable, never guessed.
- Responsive, keyboard, focus, escaping, and screen-reader labels are covered.

## Verification

- Run candidate-history projection and renderer tests for every delta type.
- Run ambiguous identity, incompatible score, missing artifact, and stale-state
  tests.
- Exercise the workflow with keyboard-only and representative narrow/wide
  browser widths.
- Run HTML escaping and unsafe-path regression tests.

