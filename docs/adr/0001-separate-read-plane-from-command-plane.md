# ADR 0001: Separate The Read Plane From The Command Plane

- Status: Accepted
- Date: 2026-07-14
- Scope: V19 and later screening, project-evolution, review, recompute, and experiment workflows

## Context

SpiroSearch already exposes manifest-backed artifacts through
`JsonArtifactRepository`, `ReadOnlyRunAPI`, and static viewer inputs. Future
versions also need project-level run comparison, human review writeback,
recompute, and experiment handoff.

Allowing a read surface to trigger those actions would blur provenance, make a
page load capable of changing scientific state, and make it difficult to prove
which input, reviewer, policy version, or run produced a decision.

## Decision

1. Run artifacts are immutable execution snapshots. A read operation never
   modifies a run directory or silently refreshes provider, scoring, review, or
   model state.
2. V19 and V20 are read-plane releases. Their browser, repository, REST-style,
   and MCP read surfaces may load, validate, compare, and explain artifacts,
   but they do not submit actions.
3. Project-level indexes and deltas reference immutable run manifests. They do
   not replace `run-manifest.json` as the source of truth for an individual
   run.
4. A command plane may be introduced only through a later explicit version.
   Commands use typed action requests with actor, idempotency key, expected
   source run/version, authorization context, and declared output effects.
5. A successful command creates auditable events, markers, or a new run. It
   never rewrites an old run to make history appear current.
6. Read and command controls may appear in one product shell, but they use
   separate adapters, endpoints/tool registries, permissions, tests, and visual
   confirmation states.

## Alternatives Considered

### Let The Viewer Write Review Events Directly

Rejected because it makes a static diagnostic surface an authority boundary,
weakens idempotency and concurrency handling, and risks accidental mutation
during inspection.

### Keep All Mutations As Ad Hoc CLI Operations

Rejected as the permanent design because it cannot provide a consistent
authorization, precondition, audit, and status contract. CLI adapters may
remain, but they must call the same command-plane contracts.

### Store Mutable Project State Inside The Latest Run

Rejected because the meaning of an immutable run would change over time and
cross-run comparison would no longer be reproducible.

## Consequences

- V20 can add project indexes and run comparison without taking on command
  authorization or job orchestration.
- Review and recompute UX is deferred until command contracts exist.
- Every mutation produces a new auditable fact or run, increasing storage but
  preserving reproducibility.
- Frontend components must distinguish observed run state, derived comparison
  state, and pending command state.
- V23 or another explicitly approved command-plane version must define
  concurrency, authorization, idempotency, and failure recovery before any
  write control is enabled.
