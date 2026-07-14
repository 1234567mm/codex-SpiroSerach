# T20-03: Enforce Versioned Run Compatibility

- Status: pending
- Size: medium
- Owner role: artifact and project-read-model owner
- Source plan: `plans/v20-manifest-native-run-evolution-and-decision-audit-spec.md`
- Blocked by: T20-01

## What To Build

Implement a versioned compatibility policy that classifies run pairs as
`comparable`, `partially_comparable`, or `non_comparable` by dimension. Expose
the result through a read-only comparison envelope and a minimal frontend
diagnostic renderer using the V19 adapter/store conventions.

## Acceptance Criteria

- Schema, screening policy, scoring formula/weights, target profile, dataset
  snapshot, candidate-pool semantics, and identity versions have declared
  comparison rules.
- Every prohibited comparison returns stable machine-readable reason codes.
- Score and rank deltas are unavailable when their required dimensions are
  incompatible.
- Raw values shown side by side carry an explicit non-comparable label.
- Missing version metadata fails closed rather than assuming compatibility.
- The browser does not duplicate the compatibility algorithm.

## Verification

- Run table-driven compatibility tests for every declared dimension.
- Run read-only envelope schema tests.
- Run the focused viewer renderer test with comparable, partial, and
  non-comparable fixtures.
- Confirm no scoring or policy function is called by the frontend/read path.
