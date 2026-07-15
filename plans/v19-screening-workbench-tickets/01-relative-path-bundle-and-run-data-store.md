# T19-01: Add The Relative-Path Bundle And Atomic RunDataStore Tracer

- Status: pending
- Size: large
- Owner role: frontend data-boundary owner
- Source plan: `plans/v19-manifest-native-screening-workbench-plan.md`
- Blocked by: V19 Backend P0 (`b28c393`) integrated on `main`

## What To Build

Replace the viewer's basename-oriented mutable input path with a manifest-first
`RelativePathBundleAdapter` and an atomic `RunDataStore`. Keep transport and
normalization logic independent from DOM rendering. A successful tracer loads
the committed V13 manifest bundle, resolves exact manifest-relative paths,
commits one coherent run store, and renders one candidate row/detail plus the
artifact diagnostics inventory.

The bundle adapter may use `File.webkitRelativePath` or another explicit
relative-path input supplied by the caller, but it must never invent a basename
fallback for a nested manifest path. Preserve the existing dependency-free
HTML/CSS/JavaScript delivery model.

## Acceptance Criteria

- The adapter indexes files by their exact normalized relative paths and
  resolves artifacts only through `run-manifest.json` declarations.
- The run-level commit minimum is a parseable manifest with unique kinds, safe
  exact paths, consistent manifest/artifact `run_id` metadata, and available
  `canonical_evidence` whose present records contain unique non-empty
  `candidate_id` values. An empty records array (`candidate_count = 0`) is a
  coherent empty run, consistent with the canonical schema.
- Duplicate manifest artifact kinds, duplicate relative paths, unsafe paths,
  a missing/unavailable run-level minimum, and artifact metadata whose `run_id`
  conflicts with the manifest fail closed with structured local diagnostics.
- Parsing and normalization occur in a pending store; visible state changes
  only after the run-level minimum is coherent.
- A failed replacement does not mutate the last committed store. If a prior
  run exists, the UI explicitly says the new load failed and that the prior
  `run_id` remains displayed; it never presents prior candidates/diagnostics as
  belonging to the failed input. With no prior run, the UI remains empty/error.
- `RunDataStore` exposes manifest metadata, normalized artifacts, availability,
  parse diagnostics, and an immutable/snapshot-style read interface.
- The tracer uses authoritative `screening_input_view` data and does not call
  providers, scoring, review, recompute, validation, or experiment writers.
- The V13 fixture produces one selectable candidate row and a manifest-backed
  artifact diagnostics inventory without hard-coded output filenames.

## Verification

- Add focused Node/DOM tests for nested relative paths, no basename fallback,
  duplicate kinds/paths, mixed run IDs, the frozen run-level minimum, and
  atomic replacement with an explicitly retained prior `run_id`.
- Run `tests.test_artifact_viewer` and `tests.test_v13_diagnostic_fixture`.
- Exercise real directory selection in a browser and confirm the committed V13
  fixture loads from nested manifest-relative paths.
