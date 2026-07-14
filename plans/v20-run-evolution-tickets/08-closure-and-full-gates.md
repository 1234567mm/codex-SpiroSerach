# T20-08: Close Browser, Migration, Artifact, And Full Gates

- Status: pending
- Size: medium
- Owner role: verification/release owner
- Source plan: `plans/v20-manifest-native-run-evolution-and-decision-audit-spec.md`
- Blocked by: T20-05, T20-06, T20-07

## What To Build

Produce the final V20 closure fixture and evidence, migration/read policy,
browser verification, focused contract gates, full repository gate, and
repository-hygiene review. This ticket fixes only defects required to meet the
V20 acceptance criteria; it does not add adjacent features.

## Acceptance Criteria

- The committed closure fixture contains two valid runs, one compatible
  comparison, one non-comparable dimension, and local degraded states.
- Project index, compatibility, delta, repository, API, frontend, and fixture
  contracts all validate together.
- Old V19 single-run bundles remain readable or have an explicit migration
  policy.
- Real-browser nested input, keyboard, responsive, and stale-state scenarios
  pass.
- Full default tests pass; applicable optional gates pass when touched.
- No generated project outputs, private data, `uv.lock`, caches, or local
  envelopes are committed.
- The final diff passes domain, artifact, scientific-claim, read/write,
  security, and product audits.

## Verification

- Run all new V20 focused suites.
- Run existing run-artifact, artifact-repository, artifact-validation,
  read-only API, and artifact-viewer suites.
- Run the repository full test gate.
- Run browser verification against the closure fixture.
- Run agent/repository hygiene checks and inspect the complete diff.

