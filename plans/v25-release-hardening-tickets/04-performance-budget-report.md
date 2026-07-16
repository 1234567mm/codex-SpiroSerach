# T25-04 Performance Budget Report

Source plan: `plans/v25-production-hardening-and-reproducible-release-spec.md`

## What To Build

Add deterministic performance budgets and measured fixture results for
representative artifact repository reads, project/run summary generation, and
viewer payload sizes.

## Acceptance Criteria

- Budgets are explicit and conservative.
- Measurements use deterministic local fixtures.
- Failures produce diagnostics rather than hidden warnings.
- Browser/viewer checks remain read-only and manifest-path driven.

## Blocked By

T25-01 for supported workflow scope.

## Verification

Run focused performance-budget tests and viewer tests if viewer fixture behavior
changes.

## Status

Planned.
