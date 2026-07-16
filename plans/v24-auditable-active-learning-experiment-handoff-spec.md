# V24 Auditable Active Learning And Experiment Handoff Spec

Source: `plans/v20-v25-integrated-delivery-roadmap.md`, section 5.6.

## Problem Statement

SpiroSearch has active-learning, acquisition, posterior, experiment-ledger, and
MCP components, but they are not yet joined to closed scientific gates, V23
command outputs, or project-level run history. V24 must make one offline or
partner-assisted round reproducible from input artifacts through observation
integration without bypassing review or model activation policy.

## Evidence and Constraints

- V22 model/data closure artifacts may disable models; V24 must consume that
  disabled state instead of reinterpreting raw metrics.
- V23 command outputs are audited facts; V24 may consume them, but not raw
  command payloads or viewer state.
- Existing V4 active-learning and experiment ledger code is the compatibility
  seam for recommendations, posterior updates, and experiment observations.
- Read-only surfaces remain read-only. V24 must not add direct robot/lab
  control, autonomous spending, molecule generation, or unapproved
  multi-objective optimization.

## Solution

Add an auditable offline loop layer that:

1. admits or blocks V24 rounds from V22 closure and V23 command-state artifacts;
2. records project-level loop state with predecessor run, candidate pool,
   training snapshot, model evaluation, acquisition policy, budget, and ledger;
3. emits deterministic recommendation and experiment-request artifacts;
4. exports human-approved experiment handoff packets and validates observation
   imports;
5. projects observations into evidence/review paths with lineage;
6. enforces replay, budget, duplicate-candidate, stale-model, and leakage
   controls;
7. exposes project evolution views for round efficiency, decisions, and
   model-state changes;
8. emits stop/continue reports based on discovery efficiency and scientific
   gates.

## User Stories

- As an operator, I can see why a round is admitted or blocked before any
  recommendation or handoff is produced.
- As a project reviewer, I can replay a round and verify candidate selection,
  budget use, model state, and predecessor lineage.
- As an experiment partner, I can receive a human-approved handoff packet and
  submit observations that validate before entering evidence.
- As a downstream reader, I can inspect stop/continue decisions without relying
  on mutable UI state.

## Implementation Decisions

- V24 artifacts are manifest-discovered and schema-backed.
- V24 consumes only closure/read-model artifacts, not provider payloads or
  command request bodies.
- Experiment handoff is export/import only; no live dispatch.
- Observation projection routes incomplete or ambiguous observations to review
  rather than silently making them scoring-eligible.

## Testing Decisions

- Each ticket gets focused tests at the contract seam it changes.
- V24 closure runs the V24 focused suite and then the repository full gate once
  after main merge.

## Out of Scope

- Direct robot/lab control.
- Autonomous spend authorization.
- Molecule generation.
- New model families or unapproved multi-objective optimization.

## Further Notes

V24 should leave V25 with reproducible artifacts, migration/security questions,
and release hardening as the remaining production concerns.
