# T20-04: Produce Traceable Candidate And Evidence Deltas

- Status: pending
- Size: large
- Owner role: artifact and project-read-model owner
- Source plan: `plans/v20-manifest-native-run-evolution-and-decision-audit-spec.md`
- Blocked by: T20-02, T20-03

## What To Build

Generate a schema-valid backend delta for two validated runs. Cover candidate
appearance/disappearance, screening-status transitions, evidence eligibility,
blocker transitions, artifact capability changes, and compatibility-gated
score/rank changes. Expose the result through the project read surface.

## Acceptance Criteria

- Every delta records both run IDs, both manifest hashes, comparison-policy
  version, generation time, and reason codes.
- Persisted deltas are declared by a deterministic project-index comparison
  entry with path, schema, hash, and byte metadata.
- Candidate joins use declared stable IDs or explicit identity mappings only.
- Added, removed, and eligibility-changed evidence is keyed by evidence ID.
- Opened/resolved blockers retain review-item identity and do not infer review
  closure from absence alone.
- Incompatible score/rank dimensions contain no misleading numeric delta.
- Reordering source records does not change semantic output.
- An unavailable optional artifact produces a local capability delta rather
  than a project-wide failure.

## Verification

- Run deterministic and permutation-invariance delta tests.
- Run explicit identity, missing artifact, blocker, evidence, and incompatible
  score/rank cases.
- Run project repository and read-only API round-trip tests.
- Validate generated JSON against the run-delta schema.
