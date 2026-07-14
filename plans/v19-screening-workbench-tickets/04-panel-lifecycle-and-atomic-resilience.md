# T19-04: Add Panel Lifecycles And Atomic Failure Resilience

- Status: pending
- Size: large
- Owner role: frontend reliability and diagnostics owner
- Source plan: `plans/v19-manifest-native-screening-workbench-plan.md`
- Blocked by: T19-03

## What To Build

Introduce `DiagnosticProjection` and panel-local lifecycle states: `idle`,
`loading`, `available`, `empty`, `degraded`, `invalid`, and `unavailable`.
Preserve imported repository validation as authoritative while clearly
labelling browser parse/path checks as local diagnostics. Ensure load attempts
use a pending store and cannot leak partially parsed or stale content into the
committed workspace.

## Acceptance Criteria

- Each artifact/candidate panel owns its lifecycle, reason, severity, and
  source; one optional failure does not erase an otherwise coherent run.
- Run-level manifest failure, missing/unavailable canonical candidate universe,
  duplicate kinds, unsafe paths, or mixed run IDs rejects the pending run
  atomically. A prior committed run may remain only with an explicit banner
  naming its `run_id` and the failed replacement; no partial new-run data or
  ambiguous stale content is displayed.
- JSONL failures report the exact relative path and line number.
- Missing optional artifacts render `unavailable` or `empty` according to their
  declared capability; they are not silently treated as valid empty data.
- Imported validation/envelope status is not overwritten by a browser-local
  parse success.
- Load generations or equivalent guards prevent an older asynchronous picker
  read from replacing a newer committed run.
- Rendering continues to HTML-escape artifact values, diagnostics, paths, and
  unavailable reasons.

## Verification

- Add tests for all lifecycle states, optional degradation, malformed JSONL,
  unsafe paths, interleaved load attempts, and stale-content clearing.
- Add a regression test proving a failed second load retains the first run only
  as an explicitly identified committed `run_id` and cannot display it as if
  the second run succeeded.
- Run `tests.test_artifact_viewer`, `tests.test_artifact_validation`, and
  `tests.test_readonly_api`.
