# T25-03 Security Audit Report

Source plan: `plans/v25-production-hardening-and-reproducible-release-spec.md`

## What To Build

Add a deterministic security audit report covering path handling, payload
validation, secrets, command authorization, idempotency, immutable old runs, and
audit-log attribution.

## Acceptance Criteria

- Path traversal and absolute-output assumptions are reported as failures.
- Secret-like values are not copied into release artifacts.
- V23 command authorization/idempotency semantics are cited as release evidence.
- Read-only surfaces remain side-effect free.

## Blocked By

T25-01 for release profile context.

## Verification

Run focused security-report tests and V23 command/viewer security tests when the
report references those surfaces.

## Status

Planned.
