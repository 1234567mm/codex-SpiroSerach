# T19-03: Add Contract-Backed Candidate Detail Projections

- Status: pending
- Size: large
- Owner role: frontend explanation and diagnostics owner
- Source plan: `plans/v19-manifest-native-screening-workbench-plan.md`
- Blocked by: T19-02

## What To Build

Add selected-candidate detail with Overview, Explanation, Diagnostics, and
Paper Evidence tabs. Build pure detail projections from the run store before
rendering. Overview shows identity, backend screening state/codes, coverage,
availability, and separate recommendation context. Explanation shows frozen
screening components, eligible `ScoringView` evidence, explicit evidence IDs,
quality/provenance, and optional acquisition context. Diagnostics shows
blocking reviews, matching review events, review summary, recompute markers,
provider lineage, artifact/schema status, and contradictions.

The Paper Evidence tab is gated: without an explicit backend candidate-to-paper
join, it explains that literature is available only at run/DOI scope.

## Acceptance Criteria

- Every displayed value retains its artifact kind and identifier/source in the
  projection or rendered explanation.
- Only policy-admitted `ScoringView` facts are described as eligible scoring
  evidence; raw provider payload/confidence is never substituted.
- Screening components and weighted utility are displayed as backend output,
  not recomputed by the frontend.
- Review events join through full `(review_item_id, target_type, target_id)`
  identity; wrong-target events remain audit diagnostics and do not appear as
  applied closure.
- Recompute markers are displayed as observed immutable artifacts, never as an
  action the viewer can execute.
- Missing, ambiguous, or contradictory joins degrade only the affected detail
  section and produce an explicit diagnostic.
- Tab controls expose correct roles, selected state, focus behavior, and
  keyboard activation.

## Verification

- Add projection/render tests for eligible evidence, components, blockers,
  wrong-target events, recompute markers, contradictions, and missing joins.
- Add keyboard tests for tab focus and activation.
- Run `tests.test_artifact_viewer`, `tests.test_scoring_view`,
  `tests.test_review_runtime`, and `tests.test_v13_diagnostic_fixture`.
