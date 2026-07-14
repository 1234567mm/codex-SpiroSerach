# T20-06: Add Atomic ProjectStore And Run Selection

- Status: pending
- Size: large
- Owner role: frontend/product owner
- Source plan: `plans/v20-manifest-native-run-evolution-and-decision-audit-spec.md`
- Blocked by: T20-02, T20-03; T20-01 fixture may be used for an early UI tracer

## What To Build

Extend the V19 frontend state model with an atomic `ProjectStore`, explicit
project input adapters, a run timeline, run selector, and two-run comparison
selection. Reuse V19 run stores and selectors rather than reparsing artifacts.

## Acceptance Criteria

- A project is parsed and validated into a new store before replacing visible
  state.
- Failed loads clear pending state without leaving stale project/run content.
- Exact project-relative and manifest-relative paths are preserved.
- Selecting runs does not mutate their normalized run stores.
- The selector exposes validation and compatibility status before comparison.
- Keyboard operation, focus order, escaping, and empty/loading/error states are
  covered.
- No frontend framework or build tool is added without separately approved
  evidence.

## Verification

- Run frontend store, adapter, atomic replacement, and selector tests.
- Run bundle input tests in a real browser, including nested paths.
- Run existing V19 artifact-viewer regression tests.
- Verify no basename fallback or stale content after a failed replacement.
