# T20-05: Prove Project Bundle And Read-Envelope Parity

- Status: pending
- Size: medium
- Owner role: artifact and project-read-model owner
- Source plan: `plans/v20-manifest-native-run-evolution-and-decision-audit-spec.md`
- Blocked by: T20-02, T20-03

## What To Build

Add exported read-only project envelopes for inventory and compatibility results,
then normalize raw project bundles and exported envelopes into the same
observable project state. Preserve authority, availability, severity, source
run, and validation metadata.

## Acceptance Criteria

- Bundle and envelope inputs produce equivalent run inventory and comparison
  state for the approved fixture.
- Envelope import preserves status, severity, surface, project/run IDs,
  read-only flag, payload metadata, and unavailable reasons.
- Mixed project IDs, duplicate surfaces, conflicting run hashes, and stale
  comparison sources are rejected.
- Importing an envelope never contacts a live MCP/HTTP service.
- A failed envelope panel cannot erase successfully loaded project state.

## Verification

- Run bundle/envelope parity tests over the same fixture.
- Run malformed, mixed-project, duplicate, stale, and unavailable-envelope
  cases.
- Run the existing read-only API and envelope schema suites.
- Prove read-only registry separation remains intact.
