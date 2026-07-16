# T25-01 Supported Runtime Profile

Source plan: `plans/v25-production-hardening-and-reproducible-release-spec.md`

## What To Build

Add a deterministic supported-runtime/deployment profile that records default
runtime expectations, optional extras, excluded external services, and supported
entry points.

## Acceptance Criteria

- Default profile is machine-readable and manifest-discoverable if emitted.
- Optional `ml` and `bo` extras remain explicitly optional.
- No new external service, credential, or lab-dispatch dependency is introduced.
- CLI/read-only/viewer entry points are identified without changing behavior.

## Blocked By

None.

## Verification

Run the focused runtime-profile tests plus artifact contract tests if a new
artifact kind is added.

## Status

Planned.
