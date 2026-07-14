# T20-01: Freeze The Project Evolution Contract And Two-Run Fixture

- Status: pending
- Size: medium
- Owner role: artifact and project-read-model owner
- Source plan: `plans/v20-manifest-native-run-evolution-and-decision-audit-spec.md`
- Blocked by: V19 authoritative `screening_input_view` and normalized run-store contract

## What To Build

Define the project-run-index, run-compatibility, and run-delta observable
contracts and freeze a minimal two-run fixture. The fixture must include one
unchanged candidate, one status transition, one evidence change, one blocker
change, and one deliberately incompatible comparison dimension.

Close the contract through schema validation, project-relative path rules,
manifest hashes, declared identifiers, and fixture tests. Do not implement the
full repository or frontend in this ticket.

## Acceptance Criteria

- Project ID, run ID, manifest hash, predecessor relation, comparison-policy
  version, candidate ID, and reason-code semantics are unambiguous.
- Unsafe paths, duplicate run IDs, conflicting hashes, and mixed project IDs
  fail closed.
- The fixture contains two individually valid manifest-backed runs.
- The incompatible dimension cannot be represented as an ordinary numeric
  delta.
- Existing run manifests remain authoritative and unchanged.
- No new contract permits fuzzy candidate, material, paper, name, or formula
  joins.

## Verification

- Run the new schema/fixture contract tests.
- Run `tests.test_run_artifacts` and `tests.test_provider_schemas`.
- Validate both fixture run directories with the existing artifact validator.
- Confirm the project fixture contains no generated outputs, private data, or
  unlicensed scientific payloads.
