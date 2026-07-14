# T19-02: Build The Candidate-First Screening Workspace

- Status: pending
- Size: large
- Owner role: frontend projection and workflow owner
- Source plan: `plans/v19-manifest-native-screening-workbench-plan.md`
- Blocked by: T19-01

## What To Build

Add a pure `CandidateProjection` over the committed `RunDataStore` and make the
candidate triage workspace the primary view. Valid `screening_input_view` rows
are the only authority for triage status. The unique canonical
`records[*].candidate_id` set is the fallback candidate universe only when a
screening row is missing or the screening artifact is unavailable/invalid; in
that case the affected canonical candidate is `insufficient-data`. Join only
through explicit `candidate_id`, canonical material/use-instance mappings,
declared evidence IDs, review IDs, and manifest metadata. Add deterministic
search, status filters, sorting, selection, blocker counts, evidence coverage, lineage
availability, and optional recommendation context.

Map backend screening state mechanically: `pass -> continue`,
`defer -> review`, and `reject -> reject`. Use `insufficient-data` when an
explicitly keyed candidate exists but its screening record is absent, invalid,
unknown, contradictory, or unavailable.

## Acceptance Criteria

- The workspace starts from authoritative `screening_input_view` records and
  never computes screening eligibility, score weights, review closure, or
  scientific thresholds in JavaScript.
- A canonical candidate with no usable screening row is retained as
  `insufficient-data`; a screening-only candidate outside the canonical
  universe is reported as an identity contradiction and cannot become
  `continue`, `review`, or `reject`.
- `continue`, `review`, and `reject` are traceable to the exact backend status;
  `insufficient-data` includes a source/reason diagnostic.
- Recommendation rank/score remains separate context and cannot promote a
  deferred or rejected candidate.
- `candidate_id` is the candidate join anchor; `candidate_id == material_id` is
  never assumed without the canonical mapping.
- Duplicate candidate IDs, conflicting material/use-instance mappings, missing
  screening rows, and unjoinable evidence/review references are visible and
  fail closed rather than being guessed.
- `screening_input_view`, scoring/review closure, recommendations/acquisition,
  provider lineage, paper artifacts, and imported validation are panel-local
  capabilities after the manifest/canonical run-level minimum commits; their
  absence or invalidity degrades the relevant candidates/panels without
  inventing data.
- Search, filters, and sorting are deterministic and preserve the selected
  candidate when it remains visible.
- The artifact table remains available as secondary diagnostics rather than
  the landing workflow.

## Verification

- Add projection tests for all four UI groups, explicit identity mapping,
  conflicts, missing screening rows, and recommendation separation.
- Add interaction tests for search, filters, stable sorting, selection, and
  empty results.
- Run `tests.test_artifact_viewer`, `tests.test_screening_policy`, and
  `tests.test_v13_diagnostic_fixture`.
