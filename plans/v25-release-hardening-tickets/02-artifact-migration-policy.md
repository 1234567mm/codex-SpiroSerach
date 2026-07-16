# T25-02 Artifact Migration And Backward-Read Policy

Source plan: `plans/v25-production-hardening-and-reproducible-release-spec.md`

## What To Build

Add a V25 migration policy/readiness report for supported artifact schema
versions, backward-read behavior, unsupported versions, and migration blockers.

## Acceptance Criteria

- Supported schema versions are explicit.
- Unsupported or missing schema metadata fails closed with diagnostics.
- Existing manifest/repository readers remain the source of truth.
- No schema relaxation is used to make invalid fixtures pass.

## Blocked By

T25-01 for release profile naming/version context.

## Verification

Run focused migration-policy tests and `tests.test_run_artifacts`.

## Status

Planned.
