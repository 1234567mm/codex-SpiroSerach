# V23 Controlled Review And Recompute Command Plane Spec

## Problem Statement

Review events and recompute markers exist, and V19–V22 made the read plane
manifest-native and auditable. The project still lacks an authorized command
plane for review decisions and recompute requests. A stale, duplicate, or
unauthorized action must not silently mutate state.

## Evidence and Constraints

- Source roadmap: `plans/v20-v25-integrated-delivery-roadmap.md`, section 5.5.
- V23 is programmatically after V20, V21, and V22; those versions are merged to
  `main`.
- Current review write logic is fixture-style in `src/spirosearch/review_runtime.py`.
- MCP registry already has write-tool idempotency primitives in
  `src/spirosearch/mcp/registry.py`, but V23 needs domain command contracts.
- Read-only surfaces must remain separate from command tools.
- `pipeline.py` still emits a legacy non-canonical manifest path; V23 must add
  guardrails so command-plane work cannot accidentally target the legacy path.

## Solution

Add a bounded command-plane layer for review decisions and recompute requests:

1. Define typed `ActionRequest` and `ActionResult` contracts.
2. Require actor, role, reason, idempotency key, expected source run/hash, and
   optimistic concurrency preconditions.
3. Register command tools separately from read-only tools and APIs.
4. Produce append-only audit events and manifest-discovered outputs; old runs
   stay immutable.
5. Model retry, rejection, conflict, timeout, cancellation, and partial failure.
6. Expose frontend command states: confirmation, pending, success, conflict, and
   failure.
7. Verify authorization, replay, stale command, and end-to-end behavior.

## User Stories

- As a curator, I can resolve or reject a review item only when authorized and
  when the source run/hash still matches my reviewed context.
- As an operator, I can request recompute from accepted review events and see a
  deterministic job status instead of hidden mutation.
- As a reader, I can still use read-only APIs and MCP tools without any write
  capability.
- As an auditor, I can attribute every accepted command to an actor, role,
  reason, idempotency key, source run, and output artifact.

## Implementation Decisions

- Command output is append-only: new events, markers, action logs, or new run
  artifacts are written; existing run artifacts are not modified in place.
- Read-only registry and command registry are separate constructors.
- Idempotency replays return the original `ActionResult`; idempotency conflicts
  fail closed.
- Stale expected run/hash and optimistic concurrency mismatches produce
  structured conflicts, not partial writes.
- Legacy `pipeline.py` output is blocked or clearly marked non-commandable
  before any command-plane action can target it.

## Dependency Graph

```text
T23-01 command-plane preconditions and legacy guardrails
  |
  v
T23-02 ActionRequest / ActionResult contracts
  |
  v
T23-03 authorization, idempotency, and preconditions
  |
  v
T23-04 separate command registry and MCP tools
  |
  v
T23-05 append-only audit outputs and recompute job status
  |
  v
T23-06 frontend command states
  |
  v
T23-07 security, replay, and end-to-end closure
```

## Testing Decisions

- Contract/schema tests cover action requests, results, audit events, and job
  statuses.
- Runtime tests cover accepted, rejected, stale, duplicate, conflict, timeout,
  cancellation, and partial-failure paths.
- Registry tests prove read-only tools stay write-free and command tools require
  authorization plus idempotency.
- Viewer tests cover confirmation/pending/success/conflict/failure states from
  manifest-discovered artifacts.
- Final V23 gate runs the full test suite on `main` after merge.

## Out of Scope

- Provider execution.
- Model training.
- Experiment dispatch.
- Direct mutation from a read endpoint.
- Scientific validation beyond V22 accepted artifacts.

## Further Notes

V24 may consume V23 command outputs, but V23 does not start active-learning or
lab handoff behavior.
