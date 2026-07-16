# T25-06 Reproducibility Bundle And Release Checklist

Source plan: `plans/v25-production-hardening-and-reproducible-release-spec.md`

## What To Build

Add the final reproducibility bundle, release fixture, and signed checklist
stub tying together V25 release profile, migration, security, performance, and
recovery evidence.

## Acceptance Criteria

- A clean checkout can reproduce the supported workflow from documented inputs.
- Release checklist references exact commands and artifact evidence.
- Final checklist does not claim external scientific validation beyond V22.
- Full gate passes once on final main integration.

## Blocked By

T25-01 through T25-05.

## Verification

Run focused reproducibility/checklist tests, then final full unittest gate after
main merge.

## Status

Planned.
