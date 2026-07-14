# T20-02: Deliver A Project-Index Vertical Tracer

- Status: pending
- Size: large
- Owner role: artifact and project-read-model owner
- Source plan: `plans/v20-manifest-native-run-evolution-and-decision-audit-spec.md`
- Blocked by: T20-01

## What To Build

Implement one end-to-end tracer from two immutable run manifests through an
explicit project-index builder, validator, project repository, and one
read-only inventory surface. The builder is an explicit offline operation;
inventory reads must not scan directories or rewrite the index.

## Acceptance Criteria

- Index output is deterministic for the same ordered inputs.
- Project-relative paths are containment-checked and do not fall back to
  basenames.
- Every run entry is resolved and validated through its own run repository.
- One invalid run degrades locally and does not hide other valid runs.
- Read output follows the existing read-only envelope status/severity style.
- Repeated reads produce no filesystem, provider, scoring, review, or model
  writes.
- The two-run fixture is observable through the new inventory surface.

## Verification

- Run the new builder, validator, repository, and inventory tracer tests.
- Run `tests.test_artifact_repository`, `tests.test_readonly_api`, and
  `tests.test_artifact_validation`.
- Compare directory timestamps/hashes before and after read calls to prove
  side-effect freedom.
