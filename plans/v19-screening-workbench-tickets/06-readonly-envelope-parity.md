# T19-06: Normalize Exported Read-Only Envelopes With Bundle Parity

- Status: pending
- Size: large
- Owner role: read-only adapter and contract owner
- Source plan: `plans/v19-manifest-native-screening-workbench-plan.md`
- Blocked by: T19-05

## What To Build

Add a `ReadonlyEnvelopeAdapter` for explicitly imported JSON exports of
`v11.readonly_api.envelope.v1`. Normalize available and unavailable envelopes
into the same `RunDataStore` representation used by the relative-path bundle
adapter. This is file import only; do not add an HTTP server, browser-to-MCP
transport, or live backend call.

## Acceptance Criteria

- The adapter preserves `status`, `severity`, `surface`, `artifact_kind`,
  `read_only`, `run_id`, `source`, payload metadata/schema validation, records
  or data, and unavailable reasons without weakening them.
- Non-read-only envelopes, unknown schema versions, mixed run IDs, conflicting
  duplicate kinds, and incoherent manifest/envelope metadata fail closed.
- Available JSON and JSONL envelopes normalize to the same observable artifact
  shape as the equivalent manifest bundle.
- Degraded/invalid/unavailable envelopes keep their authoritative status even
  when their imported JSON parses locally.
- Candidate and diagnostic projections are transport-independent: the same
  fixture produces equivalent triage groups, selected-candidate detail, and
  panel states from bundle and envelope inputs.
- No adapter invokes repository validation, providers, scoring, review,
  recompute, experiment, or external network services.

## Verification

- Generate or freeze exported read-only envelope fixtures from the committed
  manifest run and validate them against
  `schemas/readonly-api-envelope.schema.json`.
- Add parity tests comparing normalized store/projection outputs for bundle and
  envelope modes, including unavailable dependencies and mixed-run rejection.
- Run `tests.test_artifact_viewer`, `tests.test_readonly_api`,
  `tests.test_artifact_repository`, and `tests.test_provider_schemas`.
